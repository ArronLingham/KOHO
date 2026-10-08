"""Exact-cent account and transfer operations in a local SQLite database."""

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .storage import MAX_CENTS, _connection, _initialize, _write_transaction


class MoneyError(Exception):
    """Base class for business/input errors."""


class InvalidInput(MoneyError):
    """A request uses an unsupported type or value."""


class AccountNotFound(MoneyError):
    """An account identifier has no stored account."""


class InsufficientFunds(MoneyError):
    """The sender cannot cover a new transfer."""


class BalanceOverflow(MoneyError):
    """The recipient's resulting balance would exceed the storage range."""


class TransferConflict(MoneyError):
    """A committed transfer identifier is reused with different details."""


@dataclass(frozen=True)
class Account:
    account_id: int
    starting_balance_cents: int
    balance_cents: int


@dataclass(frozen=True)
class TransferReceipt:
    sequence: int
    transfer_id: str
    sender_id: int
    recipient_id: int
    amount_cents: int


def _receipt(row: sqlite3.Row) -> TransferReceipt:
    return TransferReceipt(
        row["sequence"], row["transfer_id"], row["sender_id"],
        row["recipient_id"], row["amount_cents"],
    )


def _validate_integer(value: object, field: str, minimum: int) -> None:
    # bool is an int subclass, so isinstance(value, int) is insufficient.
    if type(value) is not int or not minimum <= value <= MAX_CENTS:
        raise InvalidInput(f"{field} must be an integer between {minimum} and {MAX_CENTS}")


def _validate_transfer_id(value: object) -> None:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise InvalidInput("transfer_id must be a nonblank string without NUL characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise InvalidInput("transfer_id must contain valid UTF-8 text") from error


class MoneyService:
    """Money in a local database file; each operation owns its connection."""

    def __init__(self, database_path: str | Path) -> None:
        if str(database_path) in ("", ":memory:"):
            raise InvalidInput("database_path must be a local database file path")
        self._database_path = Path(database_path).resolve()
        _initialize(self._database_path)

    def open_account(self, starting_balance_cents: int) -> Account:
        _validate_integer(starting_balance_cents, "starting_balance_cents", minimum=0)
        with _connection(self._database_path) as connection:
            with _write_transaction(connection):
                row = connection.execute(
                    "INSERT INTO accounts (starting_balance_cents, balance_cents) "
                    "VALUES (?, ?) RETURNING account_id",
                    (starting_balance_cents, starting_balance_cents),
                ).fetchone()
                account_id = row["account_id"]
        return Account(account_id, starting_balance_cents, starting_balance_cents)

    def get_balance(self, account_id: int) -> int:
        _validate_integer(account_id, "account_id", minimum=1)
        with _connection(self._database_path) as connection:
            row = connection.execute(
                "SELECT balance_cents FROM accounts WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        if row is None:
            raise AccountNotFound(f"Account {account_id} does not exist")
        return row["balance_cents"]

    def transfer(
        self, transfer_id: str, sender_id: int, recipient_id: int, amount_cents: int,
    ) -> TransferReceipt:
        _validate_transfer_id(transfer_id)
        _validate_integer(sender_id, "sender_id", minimum=1)
        _validate_integer(recipient_id, "recipient_id", minimum=1)
        _validate_integer(amount_cents, "amount_cents", minimum=1)

        with _connection(self._database_path) as connection:
            with _write_transaction(connection):
                existing = connection.execute(
                    "SELECT * FROM transfers WHERE transfer_id = ?", (transfer_id,),
                ).fetchone()
                if existing is not None:
                    receipt = _receipt(existing)
                    if (receipt.sender_id, receipt.recipient_id, receipt.amount_cents) != (
                        sender_id, recipient_id, amount_cents,
                    ):
                        raise TransferConflict("transfer_id already has different details")
                else:
                    receipt = self._apply_transfer(
                        connection, transfer_id, sender_id, recipient_id, amount_cents,
                    )
        # Both a new transfer and a replay must leave the transaction successfully.
        return receipt

    @staticmethod
    def _apply_transfer(
        connection: sqlite3.Connection, transfer_id: str,
        sender_id: int, recipient_id: int, amount_cents: int,
    ) -> TransferReceipt:
        if sender_id == recipient_id:
            raise InvalidInput("sender_id and recipient_id must be different")
        accounts = {
            row["account_id"] for row in connection.execute(
                "SELECT account_id FROM accounts WHERE account_id IN (?, ?)",
                (sender_id, recipient_id),
            )
        }
        for account_id in (sender_id, recipient_id):
            if account_id not in accounts:
                raise AccountNotFound(f"Account {account_id} does not exist")

        debit = connection.execute(
            "UPDATE accounts SET balance_cents = balance_cents - ? "
            "WHERE account_id = ? AND balance_cents >= ?",
            (amount_cents, sender_id, amount_cents),
        )
        if debit.rowcount != 1:
            raise InsufficientFunds("Sender balance is insufficient")

        credit = connection.execute(
            "UPDATE accounts SET balance_cents = balance_cents + ? "
            "WHERE account_id = ? AND balance_cents <= ?",
            (amount_cents, recipient_id, MAX_CENTS - amount_cents),
        )
        if credit.rowcount != 1:
            raise BalanceOverflow("Recipient balance would exceed the maximum")

        row = connection.execute(
            "INSERT INTO transfers (transfer_id, sender_id, recipient_id, amount_cents) "
            "VALUES (?, ?, ?, ?) RETURNING *",
            (transfer_id, sender_id, recipient_id, amount_cents),
        ).fetchone()
        return _receipt(row)

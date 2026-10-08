"""The public account operations. Transfers are a later implementation stage."""

from dataclasses import dataclass
from pathlib import Path

from .storage import MAX_CENTS, _connection, _initialize, _write_transaction


class MoneyError(Exception):
    """Base class for business/input errors."""


class InvalidInput(MoneyError):
    """A request uses an unsupported type or value."""


class AccountNotFound(MoneyError):
    """An account identifier has no stored account."""


@dataclass(frozen=True)
class Account:
    account_id: int
    starting_balance_cents: int
    balance_cents: int


def _validate_integer(value: object, field: str, minimum: int) -> None:
    # bool is an int subclass, so isinstance(value, int) is insufficient.
    if type(value) is not int or not minimum <= value <= MAX_CENTS:
        raise InvalidInput(f"{field} must be an integer between {minimum} and {MAX_CENTS}")


class MoneyService:
    """Accounts in a local database file; each operation owns its connection."""

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

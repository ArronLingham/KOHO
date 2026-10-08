from decimal import Decimal
import sqlite3

import pytest

from move_money import AccountNotFound, InvalidInput, MAX_CENTS, MoneyService
from move_money.storage import _connection, _write_transaction


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "accounts.db"


@pytest.fixture
def service(database_path):
    return MoneyService(database_path)


@pytest.mark.parametrize("amount", [0, 1, 10_000, MAX_CENTS])
def test_open_account_preserves_exact_starting_balance(service, amount):
    account = service.open_account(amount)

    assert type(account.account_id) is int
    assert account.account_id > 0
    assert account.starting_balance_cents == amount
    assert account.balance_cents == amount
    assert service.get_balance(account.account_id) == amount
    assert type(service.get_balance(account.account_id)) is int


@pytest.mark.parametrize(
    "amount",
    [-1, MAX_CENTS + 1, 1.0, "100", True, False, None, Decimal("1"), 1 + 0j],
)
def test_invalid_starting_balance_creates_no_account(service, database_path, amount):
    with pytest.raises(InvalidInput, match="starting_balance_cents"):
        service.open_account(amount)

    with _connection(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0


def test_multiple_accounts_have_distinct_balances(service):
    first = service.open_account(123)
    second = service.open_account(456)

    assert first.account_id != second.account_id
    assert service.get_balance(first.account_id) == 123
    assert service.get_balance(second.account_id) == 456


def test_reopening_preserves_accounts_and_allows_another_creation(service, database_path):
    first = service.open_account(10_001)
    reopened = MoneyService(database_path)
    second = reopened.open_account(0)

    assert reopened.get_balance(first.account_id) == 10_001
    assert reopened.get_balance(second.account_id) == 0
    assert first.account_id != second.account_id


def test_missing_account_has_a_domain_error(service):
    with pytest.raises(AccountNotFound):
        service.get_balance(1)


@pytest.mark.parametrize("account_id", [0, -1, MAX_CENTS + 1, True, False, 1.0, "1", None])
def test_invalid_account_id_is_rejected_even_when_account_one_exists(service, account_id):
    account = service.open_account(100)
    assert account.account_id == 1

    with pytest.raises(InvalidInput, match="account_id"):
        service.get_balance(account_id)


@pytest.mark.parametrize("field", ["starting_balance_cents", "balance_cents"])
@pytest.mark.parametrize("value", [-1, 1.5, "not-an-integer", None])
def test_database_rejects_invalid_money_even_without_service_validation(
    service, database_path, field, value
):
    account = service.open_account(100)
    with _connection(database_path) as connection:
        # field comes from this fixed test parameter list, never caller input.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                f"UPDATE accounts SET {field} = ? WHERE account_id = ?",
                (value, account.account_id),
            )

    assert service.get_balance(account.account_id) == 100
    with _connection(database_path) as connection:
        row = connection.execute("SELECT * FROM accounts").fetchone()
        assert row["starting_balance_cents"] == 100


def test_database_rejects_arithmetic_overflow(service, database_path):
    account = service.open_account(MAX_CENTS)
    with _connection(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE accounts SET balance_cents = balance_cents + 1 WHERE account_id = ?",
                (account.account_id,),
            )
    assert service.get_balance(account.account_id) == MAX_CENTS


def test_connection_settings_are_explicit(service, database_path):
    with _connection(database_path) as connection:
        assert connection.autocommit is True
        assert connection.in_transaction is False
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA read_uncommitted").fetchone()[0] == 0
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5_000


def test_write_transaction_rolls_back_on_exception(service, database_path):
    with _connection(database_path) as connection:
        with pytest.raises(RuntimeError, match="injected failure"):
            with _write_transaction(connection):
                connection.execute(
                    "INSERT INTO accounts (starting_balance_cents, balance_cents) VALUES (100, 100)"
                )
                raise RuntimeError("injected failure")
        assert connection.in_transaction is False

    with _connection(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0


def test_separate_connection_sees_account_only_after_commit(service, database_path):
    with _connection(database_path) as writer, _connection(database_path) as reader:
        with _write_transaction(writer):
            writer.execute(
                "INSERT INTO accounts (starting_balance_cents, balance_cents) VALUES (100, 100)"
            )
            assert reader.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
        assert reader.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 1


@pytest.mark.parametrize("database_path", ["", ":memory:"])
def test_service_requires_a_database_file(database_path):
    with pytest.raises(InvalidInput, match="database_path"):
        MoneyService(database_path)

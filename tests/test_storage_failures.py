"""Real SQLite failure paths for the existing account/transaction foundation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier

import pytest

from move_money import InvalidInput
from move_money.storage import _connection, _write_transaction


def _balances(database_path):
    with _connection(database_path) as connection:
        return [tuple(row) for row in connection.execute(
            "SELECT account_id, starting_balance_cents, balance_cents "
            "FROM accounts ORDER BY account_id"
        ).fetchall()]


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_multiple_writes_roll_back_together_on_error_or_interruption(
    service, database_path, exception_type
):
    sender = service.open_account(200)
    recipient = service.open_account(0)
    before = _balances(database_path)

    with _connection(database_path) as connection:
        with pytest.raises(exception_type):
            with _write_transaction(connection):
                connection.execute(
                    "UPDATE accounts SET balance_cents = balance_cents - 100 WHERE account_id = ?",
                    (sender.account_id,),
                )
                connection.execute(
                    "UPDATE accounts SET balance_cents = balance_cents + 100 WHERE account_id = ?",
                    (recipient.account_id,),
                )
                raise exception_type("injected interruption")
        assert connection.in_transaction is False

    assert _balances(database_path) == before


def test_begin_lock_timeout_runs_no_write_body_and_propagates_error(service, database_path):
    account = service.open_account(100)
    body_entered = False

    with _connection(database_path) as holder, _connection(database_path) as contender:
        contender.execute("PRAGMA busy_timeout = 20")
        with _write_transaction(holder):
            holder.execute(
                "UPDATE accounts SET balance_cents = 75 WHERE account_id = ?",
                (account.account_id,),
            )
            with pytest.raises(sqlite3.OperationalError) as failure:
                with _write_transaction(contender):
                    body_entered = True
                    contender.execute("UPDATE accounts SET balance_cents = balance_cents + 1")
            assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
            assert body_entered is False
            assert contender.in_transaction is False

    assert service.get_balance(account.account_id) == 75


def test_busy_commit_rolls_back_prior_writes_and_connection_can_be_reused(service, database_path):
    account = service.open_account(100)
    statements = []

    with _connection(database_path) as reader, _connection(database_path) as writer:
        assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        writer.execute("PRAGMA busy_timeout = 20")
        writer.set_trace_callback(statements.append)
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM accounts").fetchall()

        with pytest.raises(sqlite3.OperationalError) as failure:
            with _write_transaction(writer):
                writer.execute(
                    "UPDATE accounts SET balance_cents = 50 WHERE account_id = ?",
                    (account.account_id,),
                )

        assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
        assert "COMMIT" in statements
        assert "ROLLBACK" in statements
        assert writer.in_transaction is False
        reader.execute("ROLLBACK")
        assert writer.execute("SELECT balance_cents FROM accounts").fetchone()[0] == 100

        with _write_transaction(writer):
            writer.execute(
                "UPDATE accounts SET balance_cents = 101 WHERE account_id = ?",
                (account.account_id,),
            )

    assert service.get_balance(account.account_id) == 101


def test_failed_multirow_statement_leaves_no_partial_balance_changes(service, database_path):
    service.open_account(10)
    service.open_account(0)
    before = _balances(database_path)

    with _connection(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE accounts SET balance_cents = balance_cents - 5")

    assert _balances(database_path) == before


def test_strict_storage_conversion_does_not_replace_public_input_validation(service, database_path):
    with pytest.raises(InvalidInput):
        service.open_account("100")

    # SQLite STRICT columns permit lossless coercion; the public API forbids it.
    with _connection(database_path) as connection:
        connection.execute(
            "INSERT INTO accounts (starting_balance_cents, balance_cents) VALUES (?, ?)",
            ("100", "100"),
        )
        row = connection.execute(
            "SELECT balance_cents, typeof(balance_cents) FROM accounts"
        ).fetchone()
        assert tuple(row) == (100, "integer")


def test_coordinated_account_creation_keeps_ids_unique_and_opening_totals_exact(
    service, database_path
):
    amounts = [0, 1, 2, 3, 100, 101, 10_000, 10_001]
    start = Barrier(len(amounts), timeout=5)

    def create(amount):
        start.wait()
        # open_account creates its connection inside this worker thread.
        return service.open_account(amount)

    with ThreadPoolExecutor(max_workers=len(amounts)) as workers:
        futures = [workers.submit(create, amount) for amount in amounts]
        accounts = [future.result(timeout=10) for future in futures]

    assert len({account.account_id for account in accounts}) == len(amounts)
    rows = _balances(database_path)
    expected = sorted(
        (account.account_id, amount, amount) for account, amount in zip(accounts, amounts)
    )
    assert rows == expected
    assert sum(balance for _, _, balance in rows) == sum(amounts)


@pytest.mark.parametrize("commit_before_exit", [False, True])
def test_process_exit_preserves_only_committed_account_writes(
    service, database_path, commit_before_exit
):
    service.open_account(123)
    script = """
import os
from pathlib import Path
import sys
from move_money.storage import _connection, _write_transaction

with _connection(Path(sys.argv[1])) as connection:
    with _write_transaction(connection):
        connection.execute(
            "INSERT INTO accounts (starting_balance_cents, balance_cents) VALUES (777, 777)"
        )
        if sys.argv[2] == "uncommitted":
            os._exit(17)
    os._exit(17)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(database_path),
         "committed" if commit_before_exit else "uncommitted"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 17, result.stderr
    rows = _balances(database_path)
    assert [balance for _, _, balance in rows] == ([123, 777] if commit_before_exit else [123])
    assert all(opening == balance for _, opening, balance in rows)
    with _connection(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

"""Narrow test-only fault injection against real SQLite transfer transactions."""

from contextlib import contextmanager
import sqlite3

import pytest

from move_money import HistoryEntry, MoneyService
import move_money.service as service_module
import move_money.storage as storage_module
from move_money.storage import _connection, _write_transaction


def _state(database_path):
    with _connection(database_path) as connection:
        return (
            [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")],
            [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")],
        )


@pytest.mark.parametrize("phase,trigger_clause", [
    ("after-debit", "BEFORE UPDATE OF balance_cents ON accounts WHEN NEW.account_id = 2"),
    ("after-credit", "BEFORE INSERT ON transfers"),
    ("after-record-insert", "AFTER INSERT ON transfers"),
], ids=["after-debit", "after-credit", "after-record-insert"])
def test_transfer_failure_rolls_back_balances_record_and_key(
    service, database_path, phase, trigger_clause,
):
    sender = service.open_account(100)
    recipient = service.open_account(25)
    before = _state(database_path)
    with _connection(database_path) as connection:
        connection.execute(
            f"CREATE TRIGGER injected_failure {trigger_clause} "
            "BEGIN SELECT RAISE(ABORT, 'injected transfer failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected transfer failure"):
        service.transfer("retryable", sender.account_id, recipient.account_id, 75)
    assert _state(database_path) == before
    assert service.get_history(sender.account_id) == service.get_history(recipient.account_id) == []

    with _connection(database_path) as connection:
        connection.execute("DROP TRIGGER injected_failure")
    receipt = service.transfer("retryable", sender.account_id, recipient.account_id, 75)
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [25, 100]
    assert len(_state(database_path)[1]) == 1
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]


def test_transfer_commit_failure_rolls_back_all_writes_and_key(
    service, database_path, monkeypatch,
):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    before = _state(database_path)
    statements = []
    original_connection = service_module._connection

    @contextmanager
    def traced_connection(path):
        with original_connection(path) as connection:
            connection.set_trace_callback(statements.append)
            yield connection

    monkeypatch.setattr(service_module, "_connection", traced_connection)
    monkeypatch.setattr(storage_module, "LOCK_TIMEOUT_SECONDS", 0.02)
    with _connection(database_path) as reader:
        assert reader.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM accounts").fetchall()
        try:
            with pytest.raises(sqlite3.OperationalError) as failure:
                service.transfer("commit-retry", sender.account_id, recipient.account_id, 75)
            assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
            assert sum(statement.startswith("UPDATE accounts") for statement in statements) == 2
            assert any(statement.startswith("INSERT INTO transfers") for statement in statements)
            assert "COMMIT" in statements
            assert "ROLLBACK" in statements
        finally:
            reader.execute("ROLLBACK")
    assert _state(database_path) == before
    receipt = service.transfer("commit-retry", sender.account_id, recipient.account_id, 75)
    assert receipt.sequence == 1
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [25, 75]
    assert len(_state(database_path)[1]) == 1


def test_committed_transfer_with_discarded_response_replays_after_reopen(service, database_path):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    # Simulate the caller losing the receipt after a successful commit; no network is involved.
    service.transfer("lost-response", sender.account_id, recipient.account_id, 100)
    committed = _state(database_path)
    reopened = MoneyService(database_path)
    receipt = reopened.transfer("lost-response", sender.account_id, recipient.account_id, 100)
    assert (receipt.sequence, receipt.transfer_id, receipt.sender_id,
            receipt.recipient_id, receipt.amount_cents) == committed[1][0]
    assert _state(database_path) == committed
    assert len(reopened.get_history(sender.account_id)) == len(reopened.get_history(recipient.account_id)) == 1


def test_transfer_begin_timeout_preserves_balances_and_retry_key(service, database_path, monkeypatch):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    before = _state(database_path)
    monkeypatch.setattr(storage_module, "LOCK_TIMEOUT_SECONDS", 0.02)
    with _connection(database_path) as holder:
        with _write_transaction(holder):
            with pytest.raises(sqlite3.OperationalError) as failure:
                service.transfer("busy-retry", sender.account_id, recipient.account_id, 75)
            assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
    assert _state(database_path) == before
    receipt = service.transfer("busy-retry", sender.account_id, recipient.account_id, 75)
    assert receipt.sequence == 1
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [25, 75]
    assert len(_state(database_path)[1]) == 1

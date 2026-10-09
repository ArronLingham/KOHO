"""Narrow test-only fault injection against real SQLite transfer transactions."""

from money_helpers import cents, dollars
from decimal import Decimal

from contextlib import contextmanager
import sqlite3

import pytest

from move_money import HistoryEntry, MoneyService, TransferReceipt
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
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(25))
    before = _state(database_path)
    with _connection(database_path) as connection:
        connection.execute(
            f"CREATE TRIGGER injected_failure {trigger_clause} "
            "BEGIN SELECT RAISE(ABORT, 'injected transfer failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected transfer failure"):
        service.transfer("retryable", sender.account_id, recipient.account_id, dollars(75))
    assert _state(database_path) == before
    assert service.get_history(sender.account_id) == service.get_history(recipient.account_id) == []

    with _connection(database_path) as connection:
        connection.execute("DROP TRIGGER injected_failure")
    receipt = service.transfer("retryable", sender.account_id, recipient.account_id, dollars(75))
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [dollars(25), dollars(100)]
    assert len(_state(database_path)[1]) == 1
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]


def test_transfer_commit_failure_rolls_back_all_writes_and_key(
    service, database_path, monkeypatch,
):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
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
                service.transfer("commit-retry", sender.account_id, recipient.account_id, dollars(75))
            assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
            assert sum(statement.startswith("UPDATE accounts") for statement in statements) == 2
            assert any(statement.startswith("INSERT INTO transfers") for statement in statements)
            assert "COMMIT" in statements
            assert "ROLLBACK" in statements
        finally:
            reader.execute("ROLLBACK")
    assert _state(database_path) == before
    receipt = service.transfer("commit-retry", sender.account_id, recipient.account_id, dollars(75))
    assert receipt.sequence == 1
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [dollars(25), dollars(75)]
    assert len(_state(database_path)[1]) == 1


def test_committed_transfer_with_discarded_response_replays_after_reopen(service, database_path):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    # Simulate the caller losing the receipt after a successful commit; no network is involved.
    service.transfer("lost-response", sender.account_id, recipient.account_id, dollars(100))
    committed = _state(database_path)
    reopened = MoneyService(database_path)
    receipt = reopened.transfer("lost-response", sender.account_id, recipient.account_id, dollars(100))
    assert (receipt.sequence, receipt.transfer_id, receipt.sender_id,
            receipt.recipient_id, cents(receipt.amount_dollars)) == committed[1][0]
    assert _state(database_path) == committed
    assert len(reopened.get_history(sender.account_id)) == len(reopened.get_history(recipient.account_id)) == 1


def test_transfer_begin_timeout_preserves_balances_and_retry_key(service, database_path, monkeypatch):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    before = _state(database_path)
    monkeypatch.setattr(storage_module, "LOCK_TIMEOUT_SECONDS", 0.02)
    with _connection(database_path) as holder:
        with _write_transaction(holder):
            with pytest.raises(sqlite3.OperationalError) as failure:
                service.transfer("busy-retry", sender.account_id, recipient.account_id, dollars(75))
            assert failure.value.sqlite_errorcode == sqlite3.SQLITE_BUSY
    assert _state(database_path) == before
    receipt = service.transfer("busy-retry", sender.account_id, recipient.account_id, dollars(75))
    assert receipt.sequence == 1
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [dollars(25), dollars(75)]
    assert len(_state(database_path)[1]) == 1


@pytest.mark.parametrize("exception_type", [RuntimeError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("phase", ["after-debit", "after-credit", "after-record"])
def test_interruption_after_completed_transfer_statement_restores_state_and_key(
    service, database_path, monkeypatch, exception_type, phase,
):
    service.open_account(dollars(100))
    service.open_account(dollars(0))
    before = _state(database_path)
    original_connection = service_module._connection
    checkpoints = []
    statement_prefix = {
        "after-debit": "UPDATE accounts SET balance_cents = balance_cents -",
        "after-credit": "UPDATE accounts SET balance_cents = balance_cents +",
        "after-record": "INSERT INTO transfers",
    }[phase]

    class InterruptingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, statement, parameters=()):
            cursor = self.connection.execute(statement, parameters)
            if statement.startswith(statement_prefix):
                if phase == "after-record":
                    # Complete RETURNING before inspecting the actual inserted row.
                    assert cursor.fetchone() is not None
                    cursor.close()
                checkpoints.append((
                    self.connection.in_transaction,
                    [tuple(row) for row in self.connection.execute("SELECT * FROM accounts ORDER BY account_id")],
                    [tuple(row) for row in self.connection.execute("SELECT * FROM transfers ORDER BY sequence")],
                ))
                raise exception_type("injected after completed statement")
            return cursor

    @contextmanager
    def instrumented_connection(path):
        with original_connection(path) as connection:
            yield InterruptingConnection(connection)

    with monkeypatch.context() as patch:
        patch.setattr(service_module, "_connection", instrumented_connection)
        with pytest.raises(exception_type, match="injected after completed statement"):
            service.transfer("interrupted", 1, 2, dollars(75))

    assert checkpoints == [(
        True,
        [(1, 100, 25), (2, 0, 0 if phase == "after-debit" else 75)],
        [(1, "interrupted", 1, 2, 75)] if phase == "after-record" else [],
    )]
    assert _state(database_path) == before
    assert service.get_history(1) == service.get_history(2) == []
    receipt = service.transfer("interrupted", 1, 2, dollars(75))
    assert receipt == TransferReceipt(1, "interrupted", 1, 2, dollars(75))
    assert _state(database_path) == ([(1, 100, 25), (2, 0, 75)], [(1, "interrupted", 1, 2, 75)])
    assert service.get_history(1) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(2) == [HistoryEntry(receipt, "incoming")]


@pytest.mark.parametrize("boundary", ["credit", "record"])
def test_sqlite_interrupt_restores_complete_state_and_retry_key(
    service, database_path, monkeypatch, boundary,
):
    service.open_account(dollars(100))
    service.open_account(dollars(0))
    existing = service.transfer("existing", 1, 2, dollars(5))
    before = _state(database_path)
    original_connection = service_module._connection
    checkpoints, progress_calls, active_after_failure = [], [], []
    prefix = {
        "credit": "UPDATE accounts SET balance_cents = balance_cents +",
        "record": "INSERT INTO transfers",
    }[boundary]

    def interrupt():
        progress_calls.append(boundary)
        return 1

    class InterruptingConnection:
        def __init__(self, connection):
            self.connection = connection

        def __getattr__(self, name):
            return getattr(self.connection, name)

        def execute(self, statement, parameters=()):
            selected = statement.startswith(prefix)
            if selected:
                checkpoints.append((
                    self.connection.in_transaction,
                    [tuple(row) for row in self.connection.execute(
                        "SELECT * FROM accounts ORDER BY account_id")],
                    [tuple(row) for row in self.connection.execute(
                        "SELECT * FROM transfers ORDER BY sequence")],
                ))
                # Interrupt SQLite's actual execution, rather than raising a Python exception.
                self.connection.set_progress_handler(interrupt, 1)
            try:
                return self.connection.execute(statement, parameters)
            finally:
                if selected:
                    self.connection.set_progress_handler(None, 0)

    @contextmanager
    def instrumented_connection(path):
        with original_connection(path) as connection:
            try:
                yield InterruptingConnection(connection)
            finally:
                active_after_failure.append(connection.in_transaction)

    with monkeypatch.context() as patch:
        patch.setattr(service_module, "_connection", instrumented_connection)
        with pytest.raises(sqlite3.OperationalError) as failure:
            service.transfer("interrupted", 1, 2, dollars(75))
        assert failure.value.sqlite_errorcode == sqlite3.SQLITE_INTERRUPT
        assert failure.value.sqlite_errorname == "SQLITE_INTERRUPT"

    assert progress_calls and set(progress_calls) == {boundary}
    assert checkpoints == [(
        True,
        [(1, 100, 20), (2, 0, 5 if boundary == "credit" else 80)],
        [(1, "existing", 1, 2, 5)],
    )]
    assert active_after_failure == [False]
    assert _state(database_path) == before
    reopened = MoneyService(database_path)
    assert reopened.get_history(1) == [HistoryEntry(existing, "outgoing")]
    assert reopened.get_history(2) == [HistoryEntry(existing, "incoming")]
    receipt = reopened.transfer("interrupted", 1, 2, dollars(75))
    assert receipt == TransferReceipt(2, "interrupted", 1, 2, dollars(75))
    committed = (
        [(1, 100, 20), (2, 0, 80)],
        [(1, "existing", 1, 2, 5), (2, "interrupted", 1, 2, 75)],
    )
    assert _state(database_path) == committed
    assert reopened.get_history(1) == [HistoryEntry(r, "outgoing") for r in (existing, receipt)]
    assert reopened.get_history(2) == [HistoryEntry(r, "incoming") for r in (existing, receipt)]
    assert reopened.transfer("interrupted", 1, 2, dollars(75)) == receipt
    assert _state(database_path) == committed


def test_sqlite_full_during_record_insertion_restores_state_and_key(service, database_path, monkeypatch):
    service.open_account(dollars(100))
    service.open_account(dollars(0))
    before = _state(database_path)
    original_connection = service_module._connection
    statements = []
    failed_connections = []

    @contextmanager
    def limited_connection(path):
        with original_connection(path) as connection:
            pages = connection.execute("PRAGMA page_count").fetchone()[0]
            connection.execute(f"PRAGMA max_page_count = {pages}")
            connection.set_trace_callback(statements.append)
            try:
                yield connection
            finally:
                failed_connections.append(connection.in_transaction)

    # This valid key needs more pages than the existing schema has allocated.
    key = "large-key-" + "x" * 100_000
    with monkeypatch.context() as patch:
        patch.setattr(service_module, "_connection", limited_connection)
        with pytest.raises(sqlite3.OperationalError) as failure:
            service.transfer(key, 1, 2, dollars(75))
        assert failure.value.sqlite_errorcode == sqlite3.SQLITE_FULL

    assert sum(statement.startswith("UPDATE accounts") for statement in statements) == 2
    assert any(statement.startswith("INSERT INTO transfers") for statement in statements)
    assert failed_connections == [False]
    assert _state(database_path) == before
    assert service.get_history(1) == service.get_history(2) == []
    receipt = service.transfer(key, 1, 2, dollars(75))
    assert receipt == TransferReceipt(1, key, 1, 2, dollars(75))
    assert _state(database_path) == ([(1, 100, 25), (2, 0, 75)], [(1, key, 1, 2, 75)])
    assert service.get_history(1) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(2) == [HistoryEntry(receipt, "incoming")]

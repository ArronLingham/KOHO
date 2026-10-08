"""Controlled overlapping attempts on independent, worker-owned SQLite connections."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event, local

import pytest

from move_money import HistoryEntry, InsufficientFunds, TransferConflict, TransferReceipt
import move_money.service as service_module
from move_money.storage import _connection


def _overlapping_attempts(monkeypatch, service, first_request, second_request):
    first_locked = Event()
    second_begin_attempted = Event()
    release_first = Event()
    worker_role = local()
    original_transaction = service_module._write_transaction

    @contextmanager
    def coordinated_transaction(connection):
        role = getattr(worker_role, "name", None)
        if role == "second":
            def trace(statement):
                if statement == "BEGIN IMMEDIATE":
                    second_begin_attempted.set()
            connection.set_trace_callback(trace)
        with original_transaction(connection):
            if role == "first":
                first_locked.set()
                if not release_first.wait(timeout=5):
                    raise TimeoutError("First worker was not released")
            yield

    monkeypatch.setattr(service_module, "_write_transaction", coordinated_transaction)

    def attempt(role, request):
        worker_role.name = role
        try:
            # transfer opens its connection here, in the worker that uses it.
            return service.transfer(*request)
        except (InsufficientFunds, TransferConflict) as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as workers:
        first = workers.submit(attempt, "first", first_request)
        try:
            assert first_locked.wait(timeout=5), "First worker never acquired its writer transaction"
            second = workers.submit(attempt, "second", second_request)
            assert second_begin_attempted.wait(timeout=5), "Second worker never attempted BEGIN"
            assert not first.done(), "First transaction should still be held"
            assert not second.done(), "Second writer must wait for the held transaction"
        finally:
            release_first.set()
        # Unexpected exceptions (including SQLite lock errors) propagate here.
        outcomes = [first.result(timeout=10), second.result(timeout=10)]
    return outcomes


def _transfer_rows(database_path):
    with _connection(database_path) as connection:
        return [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")]


@pytest.mark.parametrize("reverse", [False, True], ids=["b-first", "c-first"])
def test_competing_transfers_cannot_overspend(service, database_path, monkeypatch, reverse):
    a = service.open_account(10_000)
    b = service.open_account(0)
    c = service.open_account(0)
    requests = [
        ("to-b", a.account_id, b.account_id, 8000),
        ("to-c", a.account_id, c.account_id, 8000),
    ]
    if reverse:
        requests.reverse()
    outcomes = _overlapping_attempts(monkeypatch, service, *requests)
    receipts = [outcome for outcome in outcomes if isinstance(outcome, TransferReceipt)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, InsufficientFunds)]
    assert len(outcomes) == 2
    assert len(receipts) == len(failures) == 1
    balances = [service.get_balance(account.account_id) for account in (a, b, c)]
    assert balances[0] == 2000
    assert sorted(balances[1:]) == [0, 8000]
    assert sum(balances) == 10_000
    assert all(type(balance) is int and balance >= 0 for balance in balances)
    receipt = receipts[0]
    assert receipt == outcomes[0] == TransferReceipt(1, *requests[0])
    assert isinstance(outcomes[1], InsufficientFunds)
    assert _transfer_rows(database_path) == [
        (receipt.sequence, receipt.transfer_id, receipt.sender_id, receipt.recipient_id, 8000),
    ]
    assert service.get_history(a.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(receipt.recipient_id) == [HistoryEntry(receipt, "incoming")]
    loser = c if receipt.recipient_id == b.account_id else b
    assert service.get_history(loser.account_id) == []


def test_failed_first_writer_leaves_key_for_waiting_changed_payload(
    service, database_path, monkeypatch,
):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    outcomes = _overlapping_attempts(
        monkeypatch, service,
        ("reusable", sender.account_id, recipient.account_id, 101),
        ("reusable", sender.account_id, recipient.account_id, 100),
    )
    receipt = TransferReceipt(1, "reusable", sender.account_id, recipient.account_id, 100)
    assert len(outcomes) == 2
    assert isinstance(outcomes[0], InsufficientFunds)
    assert outcomes[1] == receipt
    with _connection(database_path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")] == [
            (sender.account_id, 100, 0), (recipient.account_id, 0, 100),
        ]
    assert _transfer_rows(database_path) == [(1, "reusable", sender.account_id, recipient.account_id, 100)]
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]


def test_concurrent_same_key_returns_one_receipt_and_moves_once(service, database_path, monkeypatch):
    a = service.open_account(10_000)
    b = service.open_account(0)
    request = ("same", a.account_id, b.account_id, 8000)
    outcomes = _overlapping_attempts(monkeypatch, service, request, request)
    assert all(isinstance(outcome, TransferReceipt) for outcome in outcomes)
    assert outcomes[0] == outcomes[1]
    assert [service.get_balance(a.account_id), service.get_balance(b.account_id)] == [2000, 8000]
    assert len(_transfer_rows(database_path)) == 1
    assert service.get_history(a.account_id) == [HistoryEntry(outcomes[0], "outgoing")]
    assert service.get_history(b.account_id) == [HistoryEntry(outcomes[0], "incoming")]


def test_concurrent_changed_payload_conflicts_without_second_movement(
    service, database_path, monkeypatch,
):
    a = service.open_account(10_000)
    b = service.open_account(0)
    c = service.open_account(0)
    outcomes = _overlapping_attempts(
        monkeypatch, service,
        ("identity", a.account_id, b.account_id, 8000),
        ("identity", a.account_id, c.account_id, 8000),
    )
    assert isinstance(outcomes[0], TransferReceipt)
    assert isinstance(outcomes[1], TransferConflict)
    assert [service.get_balance(account.account_id) for account in (a, b, c)] == [2000, 8000, 0]
    assert len(_transfer_rows(database_path)) == 1
    assert service.get_history(c.account_id) == []


def test_opposite_direction_transfers_both_finish_and_conserve_money(
    service, database_path, monkeypatch,
):
    a = service.open_account(10_000)
    b = service.open_account(5000)
    outcomes = _overlapping_attempts(
        monkeypatch, service,
        ("a-b", a.account_id, b.account_id, 8000),
        ("b-a", b.account_id, a.account_id, 3000),
    )
    assert all(isinstance(outcome, TransferReceipt) for outcome in outcomes)
    assert [service.get_balance(a.account_id), service.get_balance(b.account_id)] == [5000, 10_000]
    assert len(_transfer_rows(database_path)) == 2

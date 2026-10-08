"""Real spawned processes sharing one SQLite file, with bounded coordination."""

from contextlib import contextmanager
from multiprocessing import get_context
import os

from move_money import (
    HistoryEntry, InsufficientFunds, MAX_CENTS, MoneyService,
    TransferConflict, TransferReceipt,
)
import move_money.service as service_module
from move_money.storage import _connection


def _message(channel, expected, timeout=10):
    assert channel.poll(timeout), f"Timed out waiting for {expected}"
    message = channel.recv()
    assert message[0] == expected, f"Expected {expected}, received {message!r}"
    return message


def _transfer_worker(database_path, request, role, channel):
    try:
        service = MoneyService(database_path)
        original_transaction = service_module._write_transaction

        @contextmanager
        def coordinated_transaction(connection):
            if role == "second":
                def trace(statement):
                    if statement == "BEGIN IMMEDIATE":
                        channel.send(("begin-attempt", os.getpid()))
                connection.set_trace_callback(trace)
            with original_transaction(connection):
                if role == "first":
                    channel.send(("writer-held", os.getpid()))
                    _message(channel, "release")
                yield

        # Instrument only this child; the actual transaction implementation is retained.
        service_module._write_transaction = coordinated_transaction
        channel.send(("ready", os.getpid()))
        _message(channel, "start")
        try:
            outcome = service.transfer(*request)
        except (InsufficientFunds, TransferConflict) as error:
            outcome = error
        channel.send(("outcome", outcome))
    except BaseException as error:
        channel.send(("unexpected-error", type(error).__name__, str(error)))
        raise
    finally:
        channel.close()


def _cleanup(processes, channels):
    for process in processes:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
        if process.is_alive():
            process.kill()
            process.join(timeout=5)
    for channel in channels:
        channel.close()


def _overlapping_processes(database_path, first_request, second_request):
    context = get_context("spawn")
    channels = []
    processes = []
    try:
        for request, role in [(first_request, "first"), (second_request, "second")]:
            parent, child = context.Pipe()
            process = context.Process(
                target=_transfer_worker, args=(str(database_path), request, role, child),
            )
            process.start()
            child.close()
            channels.append(parent)
            processes.append(process)

        pids = [_message(channel, "ready")[1] for channel in channels]
        assert len(set(pids + [os.getpid()])) == 3
        assert pids == [process.pid for process in processes]
        channels[0].send(("start",))
        assert _message(channels[0], "writer-held")[1] == pids[0]
        channels[1].send(("start",))
        assert _message(channels[1], "begin-attempt")[1] == pids[1]
        assert all(process.is_alive() for process in processes)
        assert not any(channel.poll() for channel in channels), "A worker finished while the writer was held"
        channels[0].send(("release",))

        outcomes = [_message(channel, "outcome")[1] for channel in channels]
        for process in processes:
            process.join(timeout=10)
            assert not process.is_alive(), "Transfer process did not exit"
            assert process.exitcode == 0, f"Worker exited with {process.exitcode}"
        return outcomes
    finally:
        _cleanup(processes, channels)


def _assert_ledger(service, database_path, receipts):
    with _connection(database_path) as connection:
        accounts = [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")]
        transfers = [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    ordered = sorted(receipts, key=lambda receipt: receipt.sequence)
    assert transfers == [(r.sequence, r.transfer_id, r.sender_id, r.recipient_id, r.amount_cents)
                         for r in ordered]
    assert len({receipt.transfer_id for receipt in receipts}) == len(receipts)
    calculated = {account_id: opening for account_id, opening, _ in accounts}
    for receipt in receipts:
        assert type(receipt.amount_cents) is int and 1 <= receipt.amount_cents <= MAX_CENTS
        calculated[receipt.sender_id] -= receipt.amount_cents
        calculated[receipt.recipient_id] += receipt.amount_cents
    assert sum(balance for _, _, balance in accounts) == sum(opening for _, opening, _ in accounts)
    for account_id, _, balance in accounts:
        assert type(balance) is int and 0 <= balance <= MAX_CENTS
        assert balance == calculated[account_id] == service.get_balance(account_id)
        expected_history = [
            HistoryEntry(r, "outgoing" if r.sender_id == account_id else "incoming")
            for r in ordered if account_id in (r.sender_id, r.recipient_id)
        ]
        assert service.get_history(account_id) == expected_history


def test_separate_processes_competing_for_funds_cannot_overspend(
    service, database_path,
):
    a = service.open_account(10_000)
    b = service.open_account(0)
    c = service.open_account(0)
    outcomes = _overlapping_processes(
        database_path,
        ("process-b", a.account_id, b.account_id, 8000),
        ("process-c", a.account_id, c.account_id, 8000),
    )
    receipts = [outcome for outcome in outcomes if isinstance(outcome, TransferReceipt)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, InsufficientFunds)]
    assert len(outcomes) == 2
    assert len(receipts) == len(failures) == 1
    reopened = MoneyService(database_path)
    balances = [reopened.get_balance(account.account_id) for account in (a, b, c)]
    assert balances[0] == 2000
    assert sorted(balances[1:]) == [0, 8000]
    assert sum(balances) == 10_000
    _assert_ledger(reopened, database_path, receipts)


def test_separate_processes_same_key_move_once(service, database_path):
    a = service.open_account(10_000)
    b = service.open_account(0)
    request = ("process-same", a.account_id, b.account_id, 8000)
    outcomes = _overlapping_processes(database_path, request, request)
    assert all(isinstance(outcome, TransferReceipt) for outcome in outcomes)
    assert outcomes[0] == outcomes[1]
    reopened = MoneyService(database_path)
    assert [reopened.get_balance(a.account_id), reopened.get_balance(b.account_id)] == [2000, 8000]
    _assert_ledger(reopened, database_path, [outcomes[0]])


def test_separate_processes_changed_payload_conflicts(service, database_path):
    a = service.open_account(10_000)
    b = service.open_account(0)
    c = service.open_account(0)
    outcomes = _overlapping_processes(
        database_path,
        ("process-identity", a.account_id, b.account_id, 8000),
        ("process-identity", a.account_id, c.account_id, 8000),
    )
    assert isinstance(outcomes[0], TransferReceipt)
    assert isinstance(outcomes[1], TransferConflict)
    reopened = MoneyService(database_path)
    assert [reopened.get_balance(account.account_id) for account in (a, b, c)] == [2000, 8000, 0]
    _assert_ledger(reopened, database_path, [outcomes[0]])

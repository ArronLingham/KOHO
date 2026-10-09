"""Real spawned processes sharing one SQLite file, with bounded coordination."""

from money_helpers import cents, dollars
from decimal import Decimal

from contextlib import contextmanager
from multiprocessing import get_context
import os

import pytest

from move_money import (
    HistoryEntry, InsufficientFunds, MAX_CENTS, MoneyService,
    TransferConflict, TransferReceipt,
)
import move_money.service as service_module
import move_money.storage as storage_module
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
    assert transfers == [(r.sequence, r.transfer_id, r.sender_id, r.recipient_id, cents(r.amount_dollars))
                         for r in ordered]
    assert len({receipt.transfer_id for receipt in receipts}) == len(receipts)
    calculated = {account_id: opening for account_id, opening, _ in accounts}
    for receipt in receipts:
        assert type(receipt.amount_dollars) is Decimal and dollars(1) <= receipt.amount_dollars <= dollars(MAX_CENTS)
        calculated[receipt.sender_id] -= cents(receipt.amount_dollars)
        calculated[receipt.recipient_id] += cents(receipt.amount_dollars)
    assert sum(balance for _, _, balance in accounts) == sum(opening for _, opening, _ in accounts)
    for account_id, _, balance in accounts:
        assert type(balance) is int and 0 <= balance <= MAX_CENTS
        assert dollars(balance) == dollars(calculated[account_id]) == service.get_balance(account_id)
        expected_history = [
            HistoryEntry(r, "outgoing" if r.sender_id == account_id else "incoming")
            for r in ordered if account_id in (r.sender_id, r.recipient_id)
        ]
        assert service.get_history(account_id) == expected_history


@pytest.mark.parametrize("reverse", [False, True], ids=["b-first", "c-first"])
def test_separate_processes_competing_for_funds_cannot_overspend(
    service, database_path, reverse,
):
    a = service.open_account(dollars(10_000))
    b = service.open_account(dollars(0))
    c = service.open_account(dollars(0))
    requests = [
        ("process-b", a.account_id, b.account_id, dollars(8000)),
        ("process-c", a.account_id, c.account_id, dollars(8000)),
    ]
    if reverse:
        requests.reverse()
    outcomes = _overlapping_processes(database_path, *requests)
    receipts = [outcome for outcome in outcomes if isinstance(outcome, TransferReceipt)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, InsufficientFunds)]
    assert len(outcomes) == 2
    assert len(receipts) == len(failures) == 1
    assert receipts[0] == outcomes[0] == TransferReceipt(1, *requests[0])
    assert isinstance(outcomes[1], InsufficientFunds)
    reopened = MoneyService(database_path)
    balances = [reopened.get_balance(account.account_id) for account in (a, b, c)]
    assert balances[0] == dollars(2000)
    assert sorted(balances[1:]) == [dollars(0), dollars(8000)]
    assert sum(balances) == dollars(10_000)
    _assert_ledger(reopened, database_path, receipts)


def test_separate_processes_failed_first_writer_leaves_key_available(service, database_path):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    outcomes = _overlapping_processes(
        database_path,
        ("reusable", sender.account_id, recipient.account_id, dollars(101)),
        ("reusable", sender.account_id, recipient.account_id, dollars(100)),
    )
    receipt = TransferReceipt(1, "reusable", sender.account_id, recipient.account_id, dollars(100))
    assert len(outcomes) == 2
    assert isinstance(outcomes[0], InsufficientFunds)
    assert outcomes[1] == receipt
    reopened = MoneyService(database_path)
    assert [reopened.get_balance(sender.account_id), reopened.get_balance(recipient.account_id)] == [dollars(0), dollars(100)]
    _assert_ledger(reopened, database_path, [receipt])


def _initialization_worker(database_path, role, channel):
    try:
        original_transaction = storage_module._write_transaction

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

        # Initialization uses the storage module's transaction, before any service exists.
        storage_module._write_transaction = coordinated_transaction
        channel.send(("ready", os.getpid()))
        _message(channel, "start")
        MoneyService(database_path)
        channel.send(("initialized", os.getpid()))
    except BaseException as error:
        channel.send(("unexpected-error", type(error).__name__, str(error)))
        raise
    finally:
        channel.close()


def test_separate_processes_initialize_the_same_new_database(database_path):
    assert not database_path.exists()
    context = get_context("spawn")
    processes, channels = [], []
    try:
        for role in ("first", "second"):
            parent, child = context.Pipe()
            process = context.Process(target=_initialization_worker,
                                      args=(str(database_path), role, child))
            process.start()
            child.close()
            processes.append(process)
            channels.append(parent)
        pids = [_message(channel, "ready")[1] for channel in channels]
        assert len(set(pids + [os.getpid()])) == 3
        assert pids == [process.pid for process in processes]
        channels[0].send(("start",))
        assert _message(channels[0], "writer-held")[1] == pids[0]
        channels[1].send(("start",))
        assert _message(channels[1], "begin-attempt")[1] == pids[1]
        assert all(process.is_alive() for process in processes)
        assert not any(channel.poll() for channel in channels)
        channels[0].send(("release",))
        assert [_message(channel, "initialized")[1] for channel in channels] == pids
        for process in processes:
            process.join(timeout=10)
            assert not process.is_alive()
            assert process.exitcode == 0
    finally:
        _cleanup(processes, channels)

    service = MoneyService(database_path)
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    assert (sender.account_id, recipient.account_id) == (1, 2)
    receipt = service.transfer("initialized", 1, 2, dollars(75))
    assert receipt == TransferReceipt(1, "initialized", 1, 2, dollars(75))
    assert [service.get_balance(1), service.get_balance(2)] == [dollars(25), dollars(75)]
    _assert_ledger(service, database_path, [receipt])


@pytest.mark.parametrize("amounts,expected_cents", [
    pytest.param((dollars(8000), dollars(8000)), 8000, id="identical-decimal"),
    pytest.param((1, Decimal("1.00")), 100, id="integer-and-decimal"),
    pytest.param((0.10, Decimal("0.1000")), 10, id="float-and-scaled-decimal"),
])
@pytest.mark.parametrize("reverse", [False, True], ids=["first-representation", "second-representation"])
def test_separate_processes_same_key_move_once(
    service, database_path, amounts, expected_cents, reverse,
):
    a = service.open_account(dollars(10_000))
    b = service.open_account(dollars(0))
    requests = [("process-same", a.account_id, b.account_id, amount) for amount in amounts]
    if reverse:
        requests.reverse()
    outcomes = _overlapping_processes(database_path, *requests)
    receipt = TransferReceipt(1, "process-same", a.account_id, b.account_id, dollars(expected_cents))
    assert len(outcomes) == 2
    assert all(isinstance(outcome, TransferReceipt) for outcome in outcomes)
    assert outcomes[0] == outcomes[1] == receipt
    reopened = MoneyService(database_path)
    expected = (
        [(a.account_id, 10_000, 10_000 - expected_cents), (b.account_id, 0, expected_cents)],
        [(1, "process-same", a.account_id, b.account_id, expected_cents)],
    )
    with _connection(database_path) as connection:
        assert _database_state(connection) == expected
    _assert_ledger(reopened, database_path, [receipt])
    for request in requests:
        assert reopened.transfer(*request) == receipt
        with _connection(database_path) as connection:
            assert _database_state(connection) == expected
        _assert_ledger(reopened, database_path, [receipt])


def test_separate_processes_changed_payload_conflicts(service, database_path):
    a = service.open_account(dollars(10_000))
    b = service.open_account(dollars(0))
    c = service.open_account(dollars(0))
    outcomes = _overlapping_processes(
        database_path,
        ("process-identity", a.account_id, b.account_id, dollars(8000)),
        ("process-identity", a.account_id, c.account_id, dollars(8000)),
    )
    assert isinstance(outcomes[0], TransferReceipt)
    assert isinstance(outcomes[1], TransferConflict)
    reopened = MoneyService(database_path)
    assert [reopened.get_balance(account.account_id) for account in (a, b, c)] == [dollars(2000), dollars(8000), dollars(0)]
    _assert_ledger(reopened, database_path, [outcomes[0]])


def _database_state(connection):
    return (
        [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")],
        [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")],
    )


class _CheckpointConnection:
    """Child-only wrapper that forwards real SQL before pausing or exiting."""

    def __init__(self, connection, phase, channel):
        self._connection = connection
        self._phase = phase
        self._channel = channel

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def execute(self, statement, parameters=()):
        cursor = self._connection.execute(statement, parameters)
        debit = statement.startswith("UPDATE accounts SET balance_cents = balance_cents -")
        credit = statement.startswith("UPDATE accounts SET balance_cents = balance_cents +")
        record = statement.startswith("INSERT INTO transfers")
        selected = (
            (self._phase in ("after-debit", "pause-after-debit") and debit)
            or (self._phase == "after-credit" and credit)
            or (self._phase == "after-record" and record)
            or (self._phase == "after-commit" and statement == "COMMIT")
        )
        if selected:
            if record:
                # Finish the real RETURNING statement before inspecting/exiting.
                assert cursor.fetchone() is not None
                cursor.close()
            self._channel.send((
                "checkpoint", self._phase, os.getpid(), self._connection.in_transaction,
                _database_state(self._connection),
            ))
            if self._phase == "pause-after-debit":
                _message(self._channel, "release")
            else:
                # No Python finally blocks or graceful connection close run here.
                os._exit(17)
        return cursor


def _statement_worker(database_path, request, phase, channel):
    try:
        service = MoneyService(database_path)
        original_connection = service_module._connection

        @contextmanager
        def instrumented_connection(path):
            with original_connection(path) as connection:
                yield _CheckpointConnection(connection, phase, channel)

        service_module._connection = instrumented_connection
        receipt = service.transfer(*request)
        channel.send(("outcome", receipt))
    except BaseException as error:
        channel.send(("unexpected-error", type(error).__name__, str(error)))
        raise
    finally:
        channel.close()


@contextmanager
def _statement_child(database_path, request, phase):
    context = get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_statement_worker, args=(str(database_path), request, phase, child),
    )
    try:
        process.start()
        child.close()
        yield process, parent
    finally:
        child.close()
        _cleanup([process] if process.pid is not None else [], [parent])


@pytest.mark.parametrize("phase", ["after-debit", "after-credit", "after-record"])
def test_process_exit_during_transfer_restores_state_and_keeps_key_retryable(
    service, database_path, phase,
):
    sender = service.open_account(dollars(10_000))
    recipient = service.open_account(dollars(0))
    request = ("crash-retry", sender.account_id, recipient.account_id, dollars(8000))
    with _connection(database_path) as connection:
        before = _database_state(connection)
    with _statement_child(database_path, request, phase) as (process, channel):
        _, reached_phase, pid, active_transaction, child_state = _message(channel, "checkpoint")
        assert reached_phase == phase and pid == process.pid and pid != os.getpid()
        assert active_transaction is True
        assert [row[2] for row in child_state[0]] == [2000, 0 if phase == "after-debit" else 8000]
        assert child_state[1] == ([(1, *request[:3], cents(request[3]))] if phase == "after-record" else [])
        process.join(timeout=10)
        assert not process.is_alive()
        assert process.exitcode == 17

    reopened = MoneyService(database_path)
    with _connection(database_path) as connection:
        assert _database_state(connection) == before
    _assert_ledger(reopened, database_path, [])
    receipt = reopened.transfer(*request)
    assert receipt == TransferReceipt(1, *request)
    assert [reopened.get_balance(sender.account_id), reopened.get_balance(recipient.account_id)] == [dollars(2000), dollars(8000)]
    _assert_ledger(reopened, database_path, [receipt])


def test_process_exit_after_commit_before_response_replays_once(service, database_path):
    sender = service.open_account(dollars(10_000))
    recipient = service.open_account(dollars(0))
    request = ("committed-no-response", sender.account_id, recipient.account_id, dollars(8000))
    with _statement_child(database_path, request, "after-commit") as (process, channel):
        _, phase, pid, active_transaction, child_state = _message(channel, "checkpoint")
        assert phase == "after-commit" and pid == process.pid and pid != os.getpid()
        assert active_transaction is False
        assert [row[2] for row in child_state[0]] == [2000, 8000]
        assert child_state[1] == [(1, *request[:3], cents(request[3]))]
        process.join(timeout=10)
        assert not process.is_alive()
        assert process.exitcode == 17

    reopened = MoneyService(database_path)
    committed_receipt = TransferReceipt(1, *request)
    _assert_ledger(reopened, database_path, [committed_receipt])
    assert reopened.transfer(*request) == committed_receipt
    with _connection(database_path) as connection:
        assert _database_state(connection) == child_state
    _assert_ledger(reopened, database_path, [committed_receipt])


def test_separate_reader_cannot_see_debit_before_transfer_commits(service, database_path):
    sender = service.open_account(dollars(10_000))
    recipient = service.open_account(dollars(0))
    request = ("visible-after-commit", sender.account_id, recipient.account_id, dollars(8000))
    with _statement_child(database_path, request, "pause-after-debit") as (process, channel):
        _, phase, pid, active_transaction, child_state = _message(channel, "checkpoint")
        assert phase == "pause-after-debit" and pid == process.pid and pid != os.getpid()
        assert active_transaction is True
        assert [row[2] for row in child_state[0]] == [2000, 0]
        assert child_state[1] == []
        assert process.is_alive()
        # The child has really debited, but independent connections see committed state.
        assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [dollars(10_000), dollars(0)]
        _assert_ledger(service, database_path, [])
        channel.send(("release",))
        receipt = _message(channel, "outcome")[1]
        assert receipt == TransferReceipt(1, *request)
        process.join(timeout=10)
        assert not process.is_alive()
        assert process.exitcode == 0
    assert [service.get_balance(sender.account_id), service.get_balance(recipient.account_id)] == [dollars(2000), dollars(8000)]
    _assert_ledger(service, database_path, [receipt])

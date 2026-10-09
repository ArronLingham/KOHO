from money_helpers import cents, dollars
from decimal import Decimal
from contextlib import closing
import sqlite3

import pytest

from move_money import (
    AccountNotFound, BalanceOverflow, HistoryEntry, InsufficientFunds, InvalidInput, MAX_CENTS,
    MoneyService, TransferConflict, TransferReceipt,
)


def snapshot(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        return (
            connection.execute("SELECT * FROM accounts ORDER BY account_id").fetchall(),
            connection.execute("SELECT * FROM transfers ORDER BY sequence").fetchall(),
        )


def test_snapshot_closes_its_connection(service, database_path, monkeypatch):
    service.open_account(dollars(100))
    connections = []
    original_connect = sqlite3.connect

    def tracked_connect(*args, **kwargs):
        connection = original_connect(*args, **kwargs)
        connections.append(connection)
        return connection

    try:
        with monkeypatch.context() as patch:
            patch.setattr(sqlite3, "connect", tracked_connect)
            assert snapshot(database_path) == ([(1, 100, 100)], [])
        assert len(connections) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            connections[0].execute("SELECT 1")
    finally:
        for connection in connections:
            connection.close()


@pytest.mark.parametrize("amount", [1, 123, 10_000, MAX_CENTS])
def test_transfer_moves_exact_cents_once(service, database_path, amount):
    sender = service.open_account(dollars(amount))
    recipient = service.open_account(dollars(0))
    receipt = service.transfer("payment", sender.account_id, recipient.account_id, dollars(amount))

    assert receipt == TransferReceipt(1, "payment", sender.account_id, recipient.account_id, dollars(amount))
    assert service.get_balance(sender.account_id) == dollars(0)
    assert service.get_balance(recipient.account_id) == dollars(amount)
    accounts, transfers = snapshot(database_path)
    assert sum(row[2] for row in accounts) == amount
    assert transfers == [(1, "payment", sender.account_id, recipient.account_id, amount)]
    assert all(type(row[2]) is int and 0 <= row[2] <= MAX_CENTS for row in accounts)


def test_ordinary_transfer_preserves_remaining_funds(service):
    sender = service.open_account(dollars(10_000))
    recipient = service.open_account(dollars(25))
    service.transfer("ordinary", sender.account_id, recipient.account_id, dollars(8000))
    assert service.get_balance(sender.account_id) == dollars(2000)
    assert service.get_balance(recipient.account_id) == dollars(8025)


@pytest.mark.parametrize("starting,amount", [(0, 1), (10_000, 10_001)])
def test_insufficient_funds_preserves_all_state(service, database_path, starting, amount):
    sender = service.open_account(dollars(starting))
    recipient = service.open_account(dollars(50))
    before = snapshot(database_path)
    with pytest.raises(InsufficientFunds):
        service.transfer("too-much", sender.account_id, recipient.account_id, dollars(amount))
    assert snapshot(database_path) == before


def test_recipient_overflow_rolls_back_debit(service, database_path):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(MAX_CENTS))
    before = snapshot(database_path)
    with pytest.raises(BalanceOverflow):
        service.transfer("overflow", sender.account_id, recipient.account_id, dollars(1))
    assert snapshot(database_path) == before


def test_recipient_can_reach_maximum_exactly(service):
    sender = service.open_account(dollars(1))
    recipient = service.open_account(dollars(MAX_CENTS - 1))
    service.transfer("last-cent", sender.account_id, recipient.account_id, dollars(1))
    assert service.get_balance(sender.account_id) == dollars(0)
    assert service.get_balance(recipient.account_id) == dollars(MAX_CENTS)


@pytest.mark.parametrize("sender_id,recipient_id", [(1, 999), (999, 1), (998, 999)])
def test_missing_accounts_preserve_state(service, database_path, sender_id, recipient_id):
    service.open_account(dollars(100))
    before = snapshot(database_path)
    with pytest.raises(AccountNotFound):
        service.transfer("missing", sender_id, recipient_id, dollars(1))
    assert snapshot(database_path) == before


def test_self_transfer_preserves_state(service, database_path):
    account = service.open_account(dollars(100))
    before = snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.transfer("self", account.account_id, account.account_id, dollars(1))
    assert snapshot(database_path) == before


def test_replay_returns_original_receipt_even_after_funds_change(service, database_path):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    other = service.open_account(dollars(0))
    original = service.transfer("stable", sender.account_id, recipient.account_id, dollars(100))
    service.transfer("spend-again", recipient.account_id, other.account_id, dollars(100))
    before = snapshot(database_path)

    reopened = MoneyService(database_path)
    assert reopened.transfer("stable", sender.account_id, recipient.account_id, dollars(100)) == original
    assert snapshot(database_path) == before


def test_replay_precedes_recipient_overflow_check(service, database_path):
    sender = service.open_account(dollars(1))
    recipient = service.open_account(dollars(0))
    funder = service.open_account(dollars(MAX_CENTS - 1))
    receipt = service.transfer("replay", sender.account_id, recipient.account_id, dollars(1))
    service.transfer("fill", funder.account_id, recipient.account_id, dollars(MAX_CENTS - 1))
    before = snapshot(database_path)

    assert MoneyService(database_path).transfer("replay", sender.account_id, recipient.account_id, dollars(1)) == receipt
    assert snapshot(database_path) == before


@pytest.mark.parametrize("payload,error", [
    (("reusable", 1, 999, dollars(1)), AccountNotFound),
    (("reusable", 1, 1, dollars(1)), InvalidInput),
    (("reusable", 1, 2, dollars(1)), BalanceOverflow),
])
def test_business_rejection_leaves_key_available_for_changed_payload(
    service, database_path, payload, error,
):
    service.open_account(dollars(100))
    service.open_account(dollars(MAX_CENTS))
    service.open_account(dollars(0))
    before = snapshot(database_path)
    with pytest.raises(error):
        service.transfer(*payload)
    assert snapshot(database_path) == before

    receipt = service.transfer("reusable", 2, 3, dollars(1))
    assert receipt == TransferReceipt(1, "reusable", 2, 3, dollars(1))
    assert snapshot(database_path) == (
        [(1, 100, 100), (2, MAX_CENTS, MAX_CENTS - 1), (3, 0, 1)],
        [(1, "reusable", 2, 3, 1)],
    )
    assert service.get_history(1) == []
    assert service.get_history(2) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(3) == [HistoryEntry(receipt, "incoming")]


@pytest.mark.parametrize("sender_id,recipient_id,amount", [
    (3, 2, 10), (1, 3, 10), (1, 2, 11), (999, 2, 10), (1, 999, 10), (1, 1, 10),
])
def test_changed_payload_conflicts_before_business_checks(
    service, database_path, sender_id, recipient_id, amount,
):
    service.open_account(dollars(100))
    service.open_account(dollars(0))
    service.open_account(dollars(0))
    service.transfer("identity", 1, 2, dollars(10))
    before = snapshot(database_path)
    with pytest.raises(TransferConflict):
        service.transfer("identity", sender_id, recipient_id, dollars(amount))
    assert snapshot(database_path) == before


def test_failed_attempt_does_not_consume_key(service, database_path):
    sender = service.open_account(dollars(0))
    recipient = service.open_account(dollars(0))
    funder = service.open_account(dollars(100))
    with pytest.raises(InsufficientFunds):
        service.transfer("try-again", sender.account_id, recipient.account_id, dollars(100))
    assert snapshot(database_path)[1] == []
    service.transfer("fund", funder.account_id, sender.account_id, dollars(100))
    receipt = service.transfer("try-again", sender.account_id, recipient.account_id, dollars(100))
    assert receipt.sequence == 2
    assert service.get_balance(recipient.account_id) == dollars(100)


def test_transfer_keys_are_exact_and_sql_parameters(service, database_path):
    sender = service.open_account(dollars(100))
    recipient = service.open_account(dollars(0))
    keys = [" key ", "key", "付款", "'; DROP TABLE accounts; --",
            "\u00e9", "e\u0301", "Payment", "payment"]
    receipts = [
        service.transfer(key, sender.account_id, recipient.account_id, dollars(1))
        for key in keys
    ]
    expected = (
        [(sender.account_id, 100, 92), (recipient.account_id, 0, 8)],
        [(sequence, key, sender.account_id, recipient.account_id, 1)
         for sequence, key in enumerate(keys, 1)],
    )
    # Check actual movement and persisted identity before testing replays.
    stored = snapshot(database_path)
    assert stored == expected
    assert receipts == [
        TransferReceipt(sequence, key, sender.account_id, recipient.account_id, dollars(1))
        for sequence, key in enumerate(keys, 1)
    ]
    reopened = MoneyService(database_path)
    assert [reopened.get_balance(sender.account_id), reopened.get_balance(recipient.account_id)] == [
        dollars(92), dollars(8),
    ]
    assert sum(row[2] for row in stored[0]) == 100
    sender_history = [HistoryEntry(receipt, "outgoing") for receipt in receipts]
    recipient_history = [HistoryEntry(receipt, "incoming") for receipt in receipts]
    assert reopened.get_history(sender.account_id) == sender_history
    assert reopened.get_history(recipient.account_id) == recipient_history
    for receipt in receipts:
        assert reopened.transfer(receipt.transfer_id, sender.account_id, recipient.account_id,
                                 dollars(1)) == receipt
        assert snapshot(database_path) == expected
        assert reopened.get_history(sender.account_id) == sender_history
        assert reopened.get_history(recipient.account_id) == recipient_history

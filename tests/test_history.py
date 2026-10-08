import pytest

from move_money import (
    AccountNotFound, HistoryEntry, InsufficientFunds, InvalidInput,
    MoneyService, TransferConflict,
)


def test_opening_funding_is_not_a_transfer(service):
    funded = service.open_account(100)
    empty = service.open_account(0)
    assert service.get_history(funded.account_id) == []
    assert service.get_history(empty.account_id) == []


def test_missing_account_history_is_an_error(service):
    with pytest.raises(AccountNotFound):
        service.get_history(1)


@pytest.mark.parametrize("account_id", [0, -1, True, False, "1", 1.0, None, 2**63])
def test_invalid_history_account_identifiers(service, account_id):
    service.open_account(100)
    with pytest.raises(InvalidInput):
        service.get_history(account_id)


def test_histories_are_ordered_canonical_and_reconcile_after_reopen(service, database_path):
    a = service.open_account(1000)
    b = service.open_account(100)
    c = service.open_account(0)
    unrelated = service.open_account(999)
    first = service.transfer("z-key", a.account_id, b.account_id, 50)
    second = service.transfer("a-key", b.account_id, c.account_id, 100)
    third = service.transfer("m-key", c.account_id, a.account_id, 25)

    service = MoneyService(database_path)
    assert service.get_history(a.account_id) == [
        HistoryEntry(first, "outgoing"), HistoryEntry(third, "incoming"),
    ]
    assert service.get_history(b.account_id) == [
        HistoryEntry(first, "incoming"), HistoryEntry(second, "outgoing"),
    ]
    assert service.get_history(c.account_id) == [
        HistoryEntry(second, "incoming"), HistoryEntry(third, "outgoing"),
    ]
    assert service.get_history(unrelated.account_id) == []
    assert [first.sequence, second.sequence, third.sequence] == [1, 2, 3]

    sightings = {}
    for account in (a, b, c, unrelated):
        entries = service.get_history(account.account_id)
        calculated = account.starting_balance_cents
        for entry in entries:
            calculated += entry.transfer.amount_cents * (1 if entry.direction == "incoming" else -1)
            sightings.setdefault(entry.transfer.transfer_id, []).append(entry)
        assert service.get_balance(account.account_id) == calculated
    assert set(sightings) == {"z-key", "a-key", "m-key"}
    for entries in sightings.values():
        assert sorted(entry.direction for entry in entries) == ["incoming", "outgoing"]
        assert entries[0].transfer == entries[1].transfer


def test_failed_conflicting_and_replayed_requests_add_no_history(service):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    with pytest.raises(InsufficientFunds):
        service.transfer("rejected", sender.account_id, recipient.account_id, 101)
    assert service.get_history(sender.account_id) == []
    assert service.get_history(recipient.account_id) == []

    receipt = service.transfer("accepted", sender.account_id, recipient.account_id, 100)
    for _ in range(3):
        assert service.transfer("accepted", sender.account_id, recipient.account_id, 100) == receipt
    with pytest.raises(TransferConflict):
        service.transfer("accepted", sender.account_id, recipient.account_id, 99)
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]


def test_repeated_one_cent_transfers_remain_exact(service):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    for index in range(100):
        service.transfer(f"cent-{index}", sender.account_id, recipient.account_id, 1)
    assert service.get_balance(sender.account_id) == 0
    assert service.get_balance(recipient.account_id) == 100
    outgoing = service.get_history(sender.account_id)
    incoming = service.get_history(recipient.account_id)
    assert len(outgoing) == len(incoming) == 100
    assert [entry.transfer for entry in outgoing] == [entry.transfer for entry in incoming]
    assert all(type(entry.transfer.amount_cents) is int and entry.transfer.amount_cents == 1
               for entry in outgoing)

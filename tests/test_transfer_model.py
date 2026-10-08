"""Sequential generated requests checked against a separate in-memory ledger."""

import random

import pytest

from move_money import (
    BalanceOverflow, HistoryEntry, InsufficientFunds, MAX_CENTS,
    MoneyService, TransferConflict, TransferReceipt,
)
from move_money.storage import _connection


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_generated_transfers_retries_and_conflicts_match_independent_ledger(
    service, database_path, seed,
):
    rng = random.Random(seed)
    opening = {}
    for amount in [10_000, 0, 0, MAX_CENTS, 1]:
        account = service.open_account(amount)
        opening[account.account_id] = amount
    balances = dict(opening)
    receipts = {}

    for step in range(80):
        if receipts and rng.randrange(3) == 0:
            expected = rng.choice(list(receipts.values()))
            if rng.randrange(2) == 0:
                actual = service.transfer(
                    expected.transfer_id, expected.sender_id,
                    expected.recipient_id, expected.amount_cents,
                )
                assert actual == expected
            else:
                changed_amount = 1 if expected.amount_cents != 1 else 2
                with pytest.raises(TransferConflict):
                    service.transfer(
                        expected.transfer_id, expected.sender_id,
                        expected.recipient_id, changed_amount,
                    )
        else:
            sender, recipient = rng.sample(list(balances), 2)
            amount = rng.choice([1, 8000, MAX_CENTS, rng.randrange(1, 12_001)])
            key = f"request-{step}"
            if balances[sender] < amount:
                with pytest.raises(InsufficientFunds):
                    service.transfer(key, sender, recipient, amount)
            elif balances[recipient] + amount > MAX_CENTS:
                with pytest.raises(BalanceOverflow):
                    service.transfer(key, sender, recipient, amount)
            else:
                expected = TransferReceipt(len(receipts) + 1, key, sender, recipient, amount)
                assert service.transfer(key, sender, recipient, amount) == expected
                balances[sender] -= amount
                balances[recipient] += amount
                receipts[key] = expected

        if step % 11 == 0:
            service = MoneyService(database_path)
        with _connection(database_path) as connection:
            accounts = [tuple(row) for row in connection.execute(
                "SELECT * FROM accounts ORDER BY account_id"
            )]
            records = [tuple(row) for row in connection.execute(
                "SELECT * FROM transfers ORDER BY sequence"
            )]
        assert accounts == [(account_id, opening[account_id], balance)
                            for account_id, balance in sorted(balances.items())]
        assert records == [(r.sequence, r.transfer_id, r.sender_id, r.recipient_id, r.amount_cents)
                           for r in receipts.values()]
        assert all(type(balance) is int and 0 <= balance <= MAX_CENTS for balance in balances.values())
        assert sum(balances.values()) == sum(opening.values())
        for account_id, balance in balances.items():
            expected_history = [
                HistoryEntry(r, "outgoing" if r.sender_id == account_id else "incoming")
                for r in receipts.values() if account_id in (r.sender_id, r.recipient_id)
            ]
            assert service.get_history(account_id) == expected_history
            assert service.get_balance(account_id) == balance

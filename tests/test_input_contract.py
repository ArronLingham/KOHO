"""Adversarial public inputs and reproducible account request sequences."""

from decimal import Decimal
from fractions import Fraction
import random

import pytest

from move_money import InvalidInput, MAX_CENTS, MoneyService
from move_money.storage import _connection


class IntSubclass(int):
    pass


class ConvertibleToInteger:
    def __int__(self):
        return 1

    def __index__(self):
        return 1


_INVALID_VALUES = [
    ("numeric-string", "100"),
    ("zero-string", "0"),
    ("negative-string", "-1"),
    ("decimal-string", "1.0"),
    ("exponent-string", "1e2"),
    ("empty-string", ""),
    ("whitespace-string", " 100 "),
    ("signed-string", "+100"),
    ("unicode-digits", "١٠٠"),
    ("huge-integer-string", str(10**100)),
    ("sql-looking-string", "1; DROP TABLE accounts; --"),
    ("bytes", b"1"),
    ("bytearray", bytearray(b"1")),
    ("true", True),
    ("false", False),
    ("whole-float", 1.0),
    ("zero-float", 0.0),
    ("negative-float", -1.0),
    ("fractional-float", 0.01),
    ("nan", float("nan")),
    ("positive-infinity", float("inf")),
    ("negative-infinity", float("-inf")),
    ("decimal", Decimal("1")),
    ("decimal-nan", Decimal("NaN")),
    ("fraction", Fraction(1, 1)),
    ("complex", 1 + 0j),
    ("none", None),
    ("list", [1]),
    ("tuple", (1,)),
    ("dictionary", {"amount": 1}),
    ("set", {1}),
    ("object", object()),
    ("integer-subclass", IntSubclass(1)),
    ("integer-conversion-object", ConvertibleToInteger()),
    ("negative-cent", -1),
    ("below-signed-storage-range", -(2**63) - 1),
    ("above-maximum", MAX_CENTS + 1),
    ("huge-positive-integer", 10**100),
    ("huge-negative-integer", -(10**100)),
]
_INVALID_INPUTS = [pytest.param(value, id=name) for name, value in _INVALID_VALUES]


def _snapshot(database_path):
    with _connection(database_path) as connection:
        return [
            tuple(row)
            for row in connection.execute(
                "SELECT account_id, starting_balance_cents, balance_cents "
                "FROM accounts ORDER BY account_id"
            ).fetchall()
        ]


@pytest.mark.parametrize("amount", _INVALID_INPUTS)
def test_invalid_opening_preserves_every_existing_account(service, database_path, amount):
    service.open_account(0)
    service.open_account(10_000)
    service.open_account(MAX_CENTS)
    before = _snapshot(database_path)

    with pytest.raises(InvalidInput):
        service.open_account(amount)

    assert _snapshot(database_path) == before


@pytest.mark.parametrize("account_id", _INVALID_INPUTS)
def test_invalid_lookup_preserves_state_and_never_coerces_to_account_one(
    service, database_path, account_id
):
    account = service.open_account(10_000)
    assert account.account_id == 1
    before = _snapshot(database_path)

    with pytest.raises(InvalidInput):
        service.get_balance(account_id)

    assert _snapshot(database_path) == before


def _full_snapshot(database_path):
    with _connection(database_path) as connection:
        return (
            [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")],
            [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")],
        )


@pytest.mark.parametrize("transfer_id", ["invalid", "existing"], ids=["new-key", "committed-key"])
@pytest.mark.parametrize("field", ["sender_id", "recipient_id", "amount_cents"])
@pytest.mark.parametrize("value", _INVALID_INPUTS + [pytest.param(0, id="zero-integer")])
def test_invalid_transfer_fields_preserve_all_accounts_and_receipts(
    service, database_path, transfer_id, field, value,
):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    service.open_account(MAX_CENTS)
    service.transfer("existing", sender.account_id, recipient.account_id, 1)
    before = _full_snapshot(database_path)
    payload = dict(transfer_id=transfer_id, sender_id=sender.account_id,
                   recipient_id=recipient.account_id, amount_cents=1)
    payload[field] = value
    with pytest.raises(InvalidInput):
        service.transfer(**payload)
    assert _full_snapshot(database_path) == before


@pytest.mark.parametrize("account_id", _INVALID_INPUTS)
def test_invalid_history_lookup_preserves_all_state(service, database_path, account_id):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    service.transfer("existing", sender.account_id, recipient.account_id, 1)
    before = _full_snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.get_history(account_id)
    assert _full_snapshot(database_path) == before


class StringSubclass(str):
    pass


@pytest.mark.parametrize("key", [
    None, True, False, 1, 1.0, b"key", [], {}, object(), StringSubclass("key"),
    "", " ", "\t\n", "\u2003", "\x00", "key\x00suffix", "\ud800",
])
def test_invalid_transfer_keys_preserve_all_state(service, database_path, key):
    sender = service.open_account(100)
    recipient = service.open_account(0)
    before = _full_snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.transfer(key, sender.account_id, recipient.account_id, 1)
    assert _full_snapshot(database_path) == before


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_generated_request_sequences_match_an_independent_account_model(
    service, database_path, seed
):
    rng = random.Random(seed)
    expected = {}

    for step in range(60):
        action = rng.randrange(4)
        if action == 0 or not expected:
            amount = rng.choice([0, 1, MAX_CENTS - 1, MAX_CENTS, rng.randrange(MAX_CENTS + 1)])
            account = service.open_account(amount)
            assert account.account_id not in expected
            expected[account.account_id] = amount
        elif action == 1:
            _, invalid_amount = rng.choice(_INVALID_VALUES)
            with pytest.raises(InvalidInput):
                service.open_account(invalid_amount)
        elif action == 2:
            account_id = rng.choice(list(expected))
            assert service.get_balance(account_id) == expected[account_id]
        else:
            _, invalid_id = rng.choice(_INVALID_VALUES)
            with pytest.raises(InvalidInput):
                service.get_balance(invalid_id)

        if step % 9 == 0:
            service = MoneyService(database_path)

        rows = _snapshot(database_path)
        assert rows == [(account_id, amount, amount) for account_id, amount in sorted(expected.items())]
        assert all(type(balance) is int and 0 <= balance <= MAX_CENTS for _, _, balance in rows)
        # Sum in Python: many valid accounts can exceed SQLite's SUM integer range.
        assert sum(balance for _, _, balance in rows) == sum(expected.values())

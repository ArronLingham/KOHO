"""Adversarial dollar inputs, integer identifiers, and independent cent oracles."""

from decimal import Decimal
from fractions import Fraction
import random

import pytest

from money_helpers import dollars
from move_money import HistoryEntry, InvalidInput, MAX_CENTS, MAX_DOLLARS, MoneyService
from move_money.storage import _connection


class IntSubclass(int):
    pass


class DecimalSubclass(Decimal):
    pass


class FloatSubclass(float):
    pass


class ConvertibleToInteger:
    def __int__(self):
        return 1

    def __index__(self):
        return 1


_INVALID_ID_VALUES = [
    ("numeric-string", "100"), ("zero-string", "0"), ("negative-string", "-1"),
    ("decimal-string", "1.0"), ("exponent-string", "1e2"), ("empty-string", ""),
    ("whitespace-string", " 100 "), ("signed-string", "+100"),
    ("unicode-digits", "١٠٠"), ("huge-integer-string", str(10**100)),
    ("sql-looking-string", "1; DROP TABLE accounts; --"),
    ("bytes", b"1"), ("bytearray", bytearray(b"1")),
    ("true", True), ("false", False),
    ("whole-float", 1.0), ("zero-float", 0.0), ("negative-float", -1.0),
    ("fractional-float", 0.01), ("nan", float("nan")),
    ("positive-infinity", float("inf")), ("negative-infinity", float("-inf")),
    ("decimal", Decimal("1")), ("decimal-nan", Decimal("NaN")),
    ("fraction", Fraction(1, 1)), ("complex", 1 + 0j), ("none", None),
    ("list", [1]), ("tuple", (1,)), ("dictionary", {"amount": 1}), ("set", {1}),
    ("object", object()), ("integer-subclass", IntSubclass(1)),
    ("integer-conversion-object", ConvertibleToInteger()), ("negative-cent", -1),
    ("below-signed-storage-range", -(2**63) - 1),
    ("above-maximum", MAX_CENTS + 1), ("huge-positive-integer", 10**100),
    ("huge-negative-integer", -(10**100)),
]
_VALID_MONEY_NAMES = {"whole-float", "zero-float", "fractional-float", "decimal"}
_INVALID_MONEY_VALUES = [
    (name, value) for name, value in _INVALID_ID_VALUES if name not in _VALID_MONEY_NAMES
] + [
    ("negative-decimal", Decimal("-0.01")),
    ("fractional-cent", Decimal("0.001")),
    ("fractional-dollar-cent", Decimal("12.131")),
    ("signaling-nan", Decimal("sNaN")),
    ("decimal-infinity", Decimal("Infinity")),
    ("decimal-negative-infinity", Decimal("-Infinity")),
    ("decimal-overflow", Decimal("92233720368547758.08")),
    ("decimal-huge-exponent", Decimal("1E+999999")),
    ("decimal-tiny-exponent", Decimal("1E-999999")),
    ("float-fractional-cent", 12.131),
    ("float-arithmetic-artifact", 0.1 + 0.2),
    ("float-too-coarse", float(2**46)),
    ("decimal-from-float", Decimal(12.13)),
    ("decimal-subclass", DecimalSubclass("1.00")),
    ("float-subclass", FloatSubclass(1.00)),
]
_INVALID_IDS = [pytest.param(value, id=name) for name, value in _INVALID_ID_VALUES]
_INVALID_MONEY = [pytest.param(value, id=name) for name, value in _INVALID_MONEY_VALUES]


def _snapshot(database_path):
    with _connection(database_path) as connection:
        return [tuple(row) for row in connection.execute(
            "SELECT account_id, starting_balance_cents, balance_cents "
            "FROM accounts ORDER BY account_id"
        )]


def _full_snapshot(database_path):
    with _connection(database_path) as connection:
        return (
            [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")],
            [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")],
        )


@pytest.mark.parametrize("amount", _INVALID_MONEY)
def test_invalid_opening_preserves_every_existing_account(service, database_path, amount):
    recipient = service.open_account(0)
    sender = service.open_account(100)
    untouched = service.open_account(MAX_DOLLARS)
    receipt = service.transfer("existing", sender.account_id, recipient.account_id, 0.01)
    before = _full_snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.open_account(amount)
    assert _full_snapshot(database_path) == before
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]
    assert service.get_history(untouched.account_id) == []


@pytest.mark.parametrize("account_id", _INVALID_IDS)
def test_invalid_lookup_preserves_state_and_never_coerces_to_account_one(
    service, database_path, account_id,
):
    account = service.open_account(100)
    recipient = service.open_account(0)
    assert account.account_id == 1
    receipt = service.transfer("existing", account.account_id, recipient.account_id, 0.01)
    before = _full_snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.get_balance(account_id)
    assert _full_snapshot(database_path) == before
    assert service.get_history(account.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]


_INVALID_TRANSFER_FIELDS = [
    pytest.param(field, value, id=f"{name}-{field}")
    for field in ("sender_id", "recipient_id", "amount_dollars")
    for name, value in (
        _INVALID_MONEY_VALUES + [("zero-integer", 0), ("zero-decimal", Decimal("0.00")),
                                 ("zero-float", 0.0)]
        if field == "amount_dollars" else _INVALID_ID_VALUES + [("zero-integer", 0)]
    )
]


@pytest.mark.parametrize("transfer_id", ["invalid", "existing"], ids=["new-key", "committed-key"])
@pytest.mark.parametrize("field,value", _INVALID_TRANSFER_FIELDS)
def test_invalid_transfer_fields_preserve_all_accounts_and_receipts(
    service, database_path, transfer_id, field, value,
):
    sender = service.open_account(1)
    recipient = service.open_account(0)
    service.open_account(MAX_DOLLARS)
    service.transfer("existing", sender.account_id, recipient.account_id, 0.01)
    before = _full_snapshot(database_path)
    payload = dict(transfer_id=transfer_id, sender_id=sender.account_id,
                   recipient_id=recipient.account_id, amount_dollars=0.01)
    payload[field] = value
    with pytest.raises(InvalidInput):
        service.transfer(**payload)
    assert _full_snapshot(database_path) == before


@pytest.mark.parametrize("account_id", _INVALID_IDS)
def test_invalid_history_lookup_preserves_all_state(service, database_path, account_id):
    sender = service.open_account(1)
    recipient = service.open_account(0)
    service.transfer("existing", sender.account_id, recipient.account_id, 0.01)
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
    sender = service.open_account(1)
    recipient = service.open_account(0)
    before = _full_snapshot(database_path)
    with pytest.raises(InvalidInput):
        service.transfer(key, sender.account_id, recipient.account_id, 0.01)
    assert _full_snapshot(database_path) == before


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_generated_request_sequences_match_an_independent_account_model(
    service, database_path, seed,
):
    rng = random.Random(seed)
    expected = {}
    for step in range(60):
        action = rng.randrange(4)
        if action == 0 or not expected:
            amount = rng.choice([0, 1, MAX_CENTS - 1, MAX_CENTS, rng.randrange(MAX_CENTS + 1)])
            account = service.open_account(dollars(amount))
            assert account.account_id not in expected
            expected[account.account_id] = amount
        elif action == 1:
            _, invalid_amount = rng.choice(_INVALID_MONEY_VALUES)
            with pytest.raises(InvalidInput):
                service.open_account(invalid_amount)
        elif action == 2:
            account_id = rng.choice(list(expected))
            assert service.get_balance(account_id) == dollars(expected[account_id])
        else:
            _, invalid_id = rng.choice(_INVALID_ID_VALUES)
            with pytest.raises(InvalidInput):
                service.get_balance(invalid_id)
        if step % 9 == 0:
            service = MoneyService(database_path)
        rows = _snapshot(database_path)
        assert rows == [(account_id, amount, amount) for account_id, amount in sorted(expected.items())]
        assert all(type(balance) is int and 0 <= balance <= MAX_CENTS for _, _, balance in rows)
        assert sum(balance for _, _, balance in rows) == sum(expected.values())

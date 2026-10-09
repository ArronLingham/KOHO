"""Public dollar values checked against explicit monetary expectations."""

from decimal import Decimal, FloatOperation, Inexact, Rounded, localcontext
import random

import pytest

from money_helpers import cents
from move_money import HistoryEntry, InvalidInput, MAX_CENTS, MAX_DOLLARS, MoneyService, TransferReceipt
from move_money.service import _validate_dollars
from move_money.storage import _connection, _write_transaction


_ORACLE_BOUNDARIES = [
    Decimal("0"), Decimal("0.01"), Decimal("12.13"), Decimal("12.1300"),
    Decimal("1213E-2"), Decimal("1E+2"), Decimal("-0.01"), Decimal("0.001"),
    Decimal("-0.00"), Decimal("92233720368547758.06"), MAX_DOLLARS,
    Decimal("92233720368547758.08"),
]


def _rational_cent_oracle(value, minimum_cents):
    numerator, denominator = value.as_integer_ratio()
    scaled = numerator * 100
    if scaled % denominator:
        return None
    result = scaled // denominator
    return result if minimum_cents <= result <= MAX_CENTS else None


@pytest.fixture
def strict_decimal_context():
    with localcontext() as context:
        context.prec = 1
        context.Emax = 2
        context.Emin = -2
        for signal in context.traps:
            context.traps[signal] = True
        context.clear_flags()
        yield context


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_dollar_conversion_matches_independent_rational_oracle(seed, strict_decimal_context):
    rng = random.Random(seed)
    values = [
        Decimal((rng.randrange(2), tuple(int(digit) for digit in str(rng.randrange(10**20))),
                 rng.randrange(-8, 4)))
        for _ in range(250)
    ] + _ORACLE_BOUNDARIES
    # Four seeds * 262 values * two minima = 2,096 reproducible comparisons.
    for value in values:
        for minimum in (0, 1):
            expected = _rational_cent_oracle(value, minimum)
            if expected is None:
                with pytest.raises(InvalidInput):
                    _validate_dollars(value, "amount", minimum)
            else:
                actual = _validate_dollars(value, "amount", minimum)
                assert type(actual) is int
                assert actual == expected
            assert not any(strict_decimal_context.flags.values())


def _stored_state(database_path):
    with _connection(database_path) as connection:
        return (
            [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")],
            [tuple(row) for row in connection.execute("SELECT * FROM transfers ORDER BY sequence")],
        )


@pytest.mark.parametrize("value", _ORACLE_BOUNDARIES, ids=[
    "zero", "one-cent", "exact-cents", "trailing-zeros", "negative-exponent",
    "positive-exponent", "negative", "fractional-cent", "negative-zero",
    "maximum-minus-cent", "maximum", "above-maximum",
])
def test_public_operations_match_rational_oracle_under_strict_context(
    service, database_path, value, strict_decimal_context,
):
    sender = service.open_account(MAX_DOLLARS)
    recipient = service.open_account(0)
    expected_accounts = [(sender.account_id, MAX_CENTS, MAX_CENTS), (recipient.account_id, 0, 0)]
    expected_opening = _rational_cent_oracle(value, 0)
    if expected_opening is None:
        with pytest.raises(InvalidInput):
            service.open_account(value)
    else:
        account = service.open_account(value)
        assert cents(account.starting_balance_dollars) == cents(account.balance_dollars) == expected_opening
        assert cents(service.get_balance(account.account_id)) == expected_opening
        assert service.get_history(account.account_id) == []
        expected_accounts.append((account.account_id, expected_opening, expected_opening))
    assert _stored_state(database_path) == (expected_accounts, [])

    expected_transfer = _rational_cent_oracle(value, 1)
    if expected_transfer is None:
        with pytest.raises(InvalidInput):
            service.transfer("oracle", sender.account_id, recipient.account_id, value)
        assert _stored_state(database_path) == (expected_accounts, [])
        assert service.get_history(sender.account_id) == service.get_history(recipient.account_id) == []
    else:
        receipt = service.transfer("oracle", sender.account_id, recipient.account_id, value)
        assert receipt.sequence == 1 and receipt.transfer_id == "oracle"
        assert (receipt.sender_id, receipt.recipient_id) == (sender.account_id, recipient.account_id)
        assert cents(receipt.amount_dollars) == expected_transfer
        expected_accounts[:2] = [
            (sender.account_id, MAX_CENTS, MAX_CENTS - expected_transfer),
            (recipient.account_id, 0, expected_transfer),
        ]
        expected = (expected_accounts, [(1, "oracle", sender.account_id, recipient.account_id, expected_transfer)])
        assert _stored_state(database_path) == expected
        reopened = MoneyService(database_path)
        assert cents(reopened.get_balance(sender.account_id)) == MAX_CENTS - expected_transfer
        assert cents(reopened.get_balance(recipient.account_id)) == expected_transfer
        assert reopened.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
        assert reopened.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]
        assert reopened.transfer("oracle", sender.account_id, recipient.account_id, value) == receipt
        assert _stored_state(database_path) == expected
    assert not any(strict_decimal_context.flags.values())


@pytest.mark.parametrize("value,expected", [
    (12.13, Decimal("12.13")), (12.14, Decimal("12.14")),
    (0.29, Decimal("0.29")), (0.1, Decimal("0.10")),
    (0.2, Decimal("0.20")), (0.3, Decimal("0.30")),
    (12, Decimal("12.00")), (0, Decimal("0.00")),
    (Decimal("12.1300"), Decimal("12.13")),
    (Decimal("1213E-2"), Decimal("12.13")),
], ids=["12.13", "12.14", "0.29", "0.10", "0.20", "0.30", "integer", "zero",
        "trailing-zeros", "exponent"])
def test_numeric_dollar_inputs_preserve_exact_values(service, database_path, value, expected):
    account = service.open_account(value)
    assert account.starting_balance_dollars == account.balance_dollars == expected
    balance = service.get_balance(account.account_id)
    assert type(balance) is Decimal
    assert type(account.starting_balance_dollars) is Decimal
    assert type(account.balance_dollars) is Decimal
    assert balance == expected
    assert balance.as_tuple().exponent == -2
    assert MoneyService(database_path).get_balance(account.account_id) == expected


def test_plain_12_13_transfer_preserves_every_cent(service):
    sender = service.open_account(12.13)
    recipient = service.open_account(0)
    receipt = service.transfer("plain-dollars", sender.account_id, recipient.account_id, 12.12)
    assert receipt.amount_dollars == Decimal("12.12")
    assert type(receipt.amount_dollars) is Decimal
    assert service.get_balance(sender.account_id) == Decimal("0.01")
    assert service.get_balance(recipient.account_id) == Decimal("12.12")
    assert service.get_history(sender.account_id) == [HistoryEntry(receipt, "outgoing")]
    assert service.get_history(recipient.account_id) == [HistoryEntry(receipt, "incoming")]
    assert service.transfer("plain-dollars", sender.account_id, recipient.account_id,
                            Decimal("12.1200")) == receipt


def test_separate_float_inputs_add_up_exactly(service):
    sender = service.open_account(0.30)
    recipient = service.open_account(0)
    first = service.transfer("ten-cents", sender.account_id, recipient.account_id, 0.10)
    service.transfer("twenty-cents", sender.account_id, recipient.account_id, 0.20)
    assert service.get_balance(sender.account_id) == Decimal("0.00")
    assert service.get_balance(recipient.account_id) == Decimal("0.30")
    assert service.transfer("ten-cents", sender.account_id, recipient.account_id, 0.10) == first


@pytest.mark.parametrize("value", [1, 1.0, Decimal("1"), Decimal("1.0000")])
def test_same_dollar_value_replays_across_numeric_types_and_scales(service, value):
    sender = service.open_account(1)
    recipient = service.open_account(0)
    receipt = service.transfer("same-value", sender.account_id, recipient.account_id, 1)
    assert service.transfer("same-value", sender.account_id, recipient.account_id, value) == receipt
    assert receipt.amount_dollars == Decimal("1.00")
    assert len(service.get_history(sender.account_id)) == 1
    assert service.get_balance(sender.account_id) == Decimal("0.00")
    assert service.get_balance(recipient.account_id) == Decimal("1.00")


@pytest.mark.parametrize("precision", [1, 2, 6, 28])
def test_decimal_context_cannot_round_storage_conversion_or_receipts(service, precision):
    with localcontext() as context:
        context.prec = precision
        context.Emax = 2
        context.Emin = -2
        for signal in (Inexact, Rounded, FloatOperation):
            context.traps[signal] = True
        context.clear_flags()
        sender = service.open_account(0.01)
        recipient = service.open_account(Decimal("92233720368547758.06"))
        receipt = service.transfer("max-last-cent", sender.account_id, recipient.account_id,
                                   Decimal("0.010000"))
        assert service.get_balance(sender.account_id) == Decimal("0.00")
        assert service.get_balance(recipient.account_id) == MAX_DOLLARS
        assert receipt.amount_dollars == Decimal("0.01")
        assert service.transfer("max-last-cent", sender.account_id, recipient.account_id, 0.01) == receipt
        assert not any(context.flags.values())


@pytest.mark.parametrize("value", [Decimal("-0.00"), -0.0, Decimal("0E+999999"),
                                    Decimal("0E-999999")])
def test_zero_is_canonical_and_has_no_negative_sign(service, value):
    account = service.open_account(value)
    balance = service.get_balance(account.account_id)
    assert balance == Decimal("0.00")
    assert not balance.is_signed()
    assert balance.as_tuple().exponent == -2


def test_long_trailing_zeros_do_not_depend_on_integer_string_limits(service):
    value = Decimal("12.13" + "0" * 10_000)
    account = service.open_account(value)
    assert service.get_balance(account.account_id) == Decimal("12.13")


def test_float_resolution_limit_preserves_exact_decimal_alternative(service, database_path):
    coarse = float(2**46)
    with pytest.raises(InvalidInput, match="cent-sized differences"):
        service.open_account(coarse)
    with _connection(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0
    exact = Decimal(2**46)
    sender = service.open_account(exact)
    recipient = service.open_account(0)
    service.transfer("large-cent", sender.account_id, recipient.account_id, Decimal("0.01"))
    assert service.get_balance(sender.account_id) == Decimal("70368744177663.99")
    assert service.get_balance(recipient.account_id) == Decimal("0.01")


def test_float_below_resolution_limit_can_still_transfer_a_cent(service):
    sender = service.open_account(float(2**46 - 1))
    recipient = service.open_account(0)
    service.transfer("large-float-cent", sender.account_id, recipient.account_id, 0.01)
    assert service.get_balance(sender.account_id) == Decimal("70368744177662.99")
    assert service.get_balance(recipient.account_id) == Decimal("0.01")


def test_existing_cent_encoded_database_preserves_balances_and_retry_identity(database_path):
    service = MoneyService(database_path)
    # These are the unchanged rows produced by the former cent-based interface.
    with _connection(database_path) as connection, _write_transaction(connection):
        connection.execute("INSERT INTO accounts VALUES (1, 10000, 2000)")
        connection.execute("INSERT INTO accounts VALUES (2, 0, 8000)")
        connection.execute("INSERT INTO transfers VALUES (1, 'earlier-payment', 1, 2, 8000)")
    reopened = MoneyService(database_path)
    receipt = TransferReceipt(1, "earlier-payment", 1, 2, Decimal("80.00"))
    assert reopened.get_balance(1) == Decimal("20.00")
    assert reopened.get_balance(2) == Decimal("80.00")
    assert reopened.get_history(1) == [HistoryEntry(receipt, "outgoing")]
    assert reopened.get_history(2) == [HistoryEntry(receipt, "incoming")]
    assert reopened.transfer("earlier-payment", 1, 2, 80.0) == receipt
    with _connection(database_path) as connection:
        assert [tuple(row) for row in connection.execute("SELECT * FROM accounts ORDER BY account_id")] == [
            (1, 10000, 2000), (2, 0, 8000),
        ]
        assert [tuple(row) for row in connection.execute("SELECT * FROM transfers")] == [
            (1, "earlier-payment", 1, 2, 8000),
        ]
    assert service.get_balance(1) == Decimal("20.00")

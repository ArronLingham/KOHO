"""Independent cent-based test oracle for the public dollar interface."""

from decimal import Decimal


def dollars(cent_value: int) -> Decimal:
    assert type(cent_value) is int
    sign = "-" if cent_value < 0 else ""
    magnitude = abs(cent_value)
    return Decimal(f"{sign}{magnitude // 100}.{magnitude % 100:02d}")


def cents(dollar_value: Decimal) -> int:
    assert type(dollar_value) is Decimal and dollar_value.is_finite()
    numerator, denominator = dollar_value.as_integer_ratio()
    assert numerator * 100 % denominator == 0
    return numerator * 100 // denominator

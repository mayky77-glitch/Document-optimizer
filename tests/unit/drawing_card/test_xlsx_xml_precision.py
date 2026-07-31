"""Regression coverage for exact XML decimal serialization."""

from decimal import Decimal

import pytest

from report_processor.drawing_card.output.xlsx_xml import decimal_xml_text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("315093817.390000004"), "315093817.39"),
        (Decimal("1000000000000.001"), "1000000000000.001"),
        (Decimal("12.123456"), "12.123456"),
        (Decimal("0"), "0"),
        (Decimal("42"), "42"),
    ],
)
def test_decimal_xml_text_normalizes_only_binary_float_tails(
    value: Decimal, expected: str
) -> None:
    assert decimal_xml_text(value) == expected

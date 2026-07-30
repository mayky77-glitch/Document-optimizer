from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from report_processor.extraction import parse_decimal_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (123, Decimal("123")),
        (123.45, Decimal("123.45")),
        (Decimal("123.4500000000000000001"), Decimal("123.4500000000000000001")),
        ("123,45", Decimal("123.45")),
        ("1 234,56", Decimal("1234.56")),
        ("1\u00a0234,56", Decimal("1234.56")),
        ("1\u202f234,56", Decimal("1234.56")),
        ("-100,50", Decimal("-100.50")),
        ("0", Decimal("0")),
        (0, Decimal("0")),
        (-15, Decimal("-15")),
        ("-15,25", Decimal("-15.25")),
        ("+15.25", Decimal("15.25")),
    ],
)
def test_parse_valid_numbers(raw, expected):
    result = parse_decimal_value(raw)
    assert result.value == expected
    assert result.status == "OK"
    assert result.raw_value == raw


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "—",
    ],
)
def test_empty_markers_do_not_become_zero(raw):
    result = parse_decimal_value(raw)
    assert result.value is None
    assert result.status == "EMPTY"


@pytest.mark.parametrize(
    "raw",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        datetime(2026, 7, 1),
        date(2026, 7, 1),
        "1,234.56",
        "12 34,56",
        "12abc",
        "N/A",
        "#NAME?",
        [],
    ],
)
def test_invalid_numbers_are_rejected(raw):
    result = parse_decimal_value(raw)
    assert result.value is None
    assert result.status != "OK"


def test_text_numbers_can_be_disabled():
    result = parse_decimal_value("123", allow_text_numbers=False)
    assert result.value is None
    assert result.status == "TEXT_NUMBERS_DISABLED"

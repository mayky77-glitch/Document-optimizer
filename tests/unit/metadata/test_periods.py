from __future__ import annotations

import pytest

from report_processor.metadata.periods import (
    DocumentPeriod,
    extract_document_period,
    extract_period_from_path,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("КС-6а июль 2026.xlsx", "2026-07"),
        ("КС-6а ИЮЛЬ_2026.xlsx", "2026-07"),
        ("КС-6а 07.2026.xlsx", "2026-07"),
        ("КС-6а 07-2026.xlsx", "2026-07"),
        ("КС-6а 07_2026.xlsx", "2026-07"),
        ("КС-6а 2026-07.xlsx", "2026-07"),
        ("КС-6а 2026_07.xlsx", "2026-07"),
        ("КС-6а 2026.07.xlsx", "2026-07"),
        ("КС-6а июль 26.xlsx", "2026-07"),
        ("КС-6а 07.26.xlsx", "2026-07"),
        ("за июля 2026", "2026-07"),
        ("июль итог 2026", "2026-07"),
    ],
)
def test_extract_supported_periods(value: str, expected: str) -> None:
    result = extract_document_period(value)
    assert result.status == "OK"
    assert result.value is not None
    assert result.value.normalized == expected


def test_two_digit_year_pivot() -> None:
    assert extract_document_period("июль 69").value == DocumentPeriod(2069, 7)
    assert extract_document_period("июль 70").value == DocumentPeriod(1970, 7)


def test_full_date_uses_russian_day_month_year() -> None:
    result = extract_document_period("КС-6а от 07.08.2026.xlsx")
    assert result.value == DocumentPeriod(2026, 8)
    assert "PERIOD_DERIVED_FROM_FULL_DATE" in result.warnings


def test_multiple_periods_are_ambiguous() -> None:
    result = extract_document_period("июнь 2026 — июль 2026")
    assert result.status == "MULTIPLE_PERIOD_CANDIDATES"
    assert result.value is None
    assert result.candidates == (DocumentPeriod(2026, 6), DocumentPeriod(2026, 7))


def test_period_not_found_is_controlled() -> None:
    result = extract_document_period("КС-6а.xlsx")
    assert result.status == "PERIOD_NOT_FOUND"
    assert result.value is None


@pytest.mark.parametrize(
    "value",
    ["1006 (682)", "КС-2", "ред2", "этап 13.1", "версия 07", "позиция 2026"],
)
def test_false_positives_are_ignored(value: str) -> None:
    assert extract_document_period(value).value is None


def test_invalid_numeric_month() -> None:
    assert extract_document_period("13.2026").status == "INVALID_PERIOD"
    assert extract_document_period("2026-13").status == "INVALID_PERIOD"


def test_parent_path_fallback_and_confirmation() -> None:
    fallback = extract_period_from_path("2026-07/КС-6а.xlsx")
    assert fallback.value == DocumentPeriod(2026, 7)
    confirmed = extract_period_from_path("2026-07/КС-6а июль 2026.xlsx")
    assert confirmed.value == DocumentPeriod(2026, 7)
    assert "PERIOD_CONFIRMED_BY_PARENT_PATH" in confirmed.warnings


def test_parent_path_conflict_is_ambiguous() -> None:
    result = extract_period_from_path("2026-06/КС-6а июль 2026.xlsx")
    assert result.status == "MULTIPLE_PERIOD_CANDIDATES"
    assert result.value is None


def test_absolute_parent_path_is_not_used() -> None:
    result = extract_period_from_path("/Users/example/2026-06/КС-6а.xlsx")
    assert result.status == "PERIOD_NOT_FOUND"

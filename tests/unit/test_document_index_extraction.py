"""Unit checks for block 2 identifier extraction."""

import pytest

from report_processor.domain.statuses import IndexStatus, IndexWarning
from report_processor.identifiers import (
    document_indexes_equal,
    extract_document_index,
    extract_index_from_path,
)


@pytest.mark.parametrize("value", ["1006 (682)", "0001(002)", "１００６（６８２）"])
def test_extracts_strict_indexes_without_losing_leading_zeroes(value: str) -> None:
    result = extract_document_index(value)

    assert result.status == IndexStatus.OK.value
    assert result.value is not None


def test_marks_year_like_indexes_as_low_confidence() -> None:
    result = extract_document_index("2026 (7)")

    assert result.status == IndexStatus.LOW_CONFIDENCE_INDEX.value
    assert result.value is None
    assert IndexWarning.YEAR_LIKE_MAIN_INDEX.value in result.warnings


def test_multiple_indexes_are_ambiguous_and_loose_indexes_are_not_accepted() -> None:
    assert (
        extract_document_index("1006 (682) и 0842 (623)").status
        == IndexStatus.MULTIPLE_INDEX_CANDIDATES.value
    )
    assert extract_document_index("1006-682", allow_loose=True).value is None


def test_parent_path_can_confirm_a_filename_index() -> None:
    result = extract_index_from_path(
        r"C:\Документы\1006 (682)\1006 (682)_КС-2.xlsx", include_parent_parts=True
    )

    assert result.status == IndexStatus.OK.value
    assert result.value is not None
    assert result.value.normalized == "1006 (682)"
    assert IndexWarning.INDEX_CONFIRMED_BY_PARENT_PATH.value in result.warnings
    assert document_indexes_equal("1006(682)", result.value)

from __future__ import annotations

import pytest

from report_processor.metadata.revisions import extract_document_revision


@pytest.mark.parametrize(
    ("value", "number"),
    [
        ("ред2", 2),
        ("ред 2", 2),
        ("ред.2", 2),
        ("редакция 2", 2),
        ("rev2", 2),
        ("rev 2", 2),
        ("revision 2", 2),
        ("версия 3", 3),
        ("v3", 3),
    ],
)
def test_numeric_revision_formats(value: str, number: int) -> None:
    result = extract_document_revision(value)
    assert result.status == "OK"
    assert result.value is not None
    assert result.value.number == number


@pytest.mark.parametrize("value", ["итог", "финал", "final", "окончательный"])
def test_final_markers(value: str) -> None:
    assert extract_document_revision(value).value.is_final is True


@pytest.mark.parametrize("value", ["согл", "согласовано", "approved"])
def test_approved_markers(value: str) -> None:
    assert extract_document_revision(value).value.is_approved is True


@pytest.mark.parametrize("value", ["черновик", "draft", "предварительный", "рабочий"])
def test_draft_markers(value: str) -> None:
    assert extract_document_revision(value).value.is_draft is True


def test_copy_suffix_is_not_revision() -> None:
    result = extract_document_revision("копия (2)")
    assert result.status == "REVISION_NOT_FOUND"
    assert result.value is None


def test_conflicting_markers_are_reported() -> None:
    result = extract_document_revision("ред2 черновик финал")
    assert result.status == "CONFLICTING_VERSION_MARKERS"
    assert result.value is not None
    assert result.value.is_draft and result.value.is_final
    assert "CONFLICTING_VERSION_MARKERS" in result.warnings


def test_multiple_revision_numbers_are_ambiguous() -> None:
    result = extract_document_revision("ред2 revision 3")
    assert result.status == "MULTIPLE_REVISION_CANDIDATES"
    assert result.value is None

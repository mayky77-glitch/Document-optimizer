from __future__ import annotations

import pytest

from report_processor.identifiers.document_index import extract_document_index
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.metadata.periods import DocumentPeriod
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)
from report_processor.selection.models import SourceSelectionRequest
from report_processor.selection.selector import select_source_file

DEFAULT_PERIOD = DocumentPeriod(2026, 7)


def _request(
    *,
    preferred=("ks6a", "ks2"),
    target_period=DEFAULT_PERIOD,
    **kwargs,
) -> SourceSelectionRequest:
    values = {
        "target_index": extract_document_index("1006 (682)").value,
        "target_period": target_period,
        "preferred_document_types": preferred,
        "allowed_document_types": ("ks6a", "ks2"),
    }
    values.update(kwargs)
    return SourceSelectionRequest(**values)


def _select(entries, make_manifest, request=None):
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(make_manifest(entries))
    )
    return select_source_file(manifest, request or _request())


def test_one_exact_candidate(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026.xlsx"),
            make_entry("0842 (623)_КС-6а июль 2026.xlsx"),
        ],
        make_manifest,
    )
    assert result.status == "OK"
    assert result.selected.entry.filename.startswith("1006 (682)")


@pytest.mark.parametrize(
    ("preferred", "expected_marker"),
    [(("ks6a", "ks2"), "КС-6а"), (("ks2", "ks6a"), "КС-2")],
)
def test_document_type_priority_is_request_driven(
    preferred, expected_marker, make_entry, make_manifest
) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026.xlsx"),
            make_entry("1006 (682)_КС-2 июль 2026.xlsx"),
        ],
        make_manifest,
        _request(preferred=preferred),
    )
    assert expected_marker in result.selected.entry.filename


def test_exact_period_wins(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июнь 2026.xlsx"),
            make_entry("1006 (682)_КС-6а июль 2026.xlsx"),
        ],
        make_manifest,
    )
    assert "июль" in result.selected.entry.filename


def test_unknown_period_allowed_and_disallowed(make_entry, make_manifest) -> None:
    entries = [
        make_entry("1006 (682)_КС-6а.xlsx"),
        make_entry("1006 (682)_КС-2 июль 2026.xlsx"),
    ]
    allowed = _select(entries, make_manifest, _request(allow_unknown_period=True))
    disallowed = _select(entries, make_manifest, _request(allow_unknown_period=False))
    assert allowed.status == "OK"
    assert disallowed.status == "OK"
    assert "КС-2" in disallowed.selected.entry.filename


def test_higher_revision_wins(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026 ред1.xlsx"),
            make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx"),
        ],
        make_manifest,
    )
    assert "ред2" in result.selected.entry.filename


def test_large_revision_cannot_compensate_period_mismatch(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026 ред1.xlsx"),
            make_entry("1006 (682)_КС-6а июнь 2026 ред999.xlsx"),
        ],
        make_manifest,
    )
    assert "июль" in result.selected.entry.filename


def test_final_file_wins(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx"),
            make_entry("1006 (682)_КС-6а июль 2026 ред2 итог.xlsx"),
        ],
        make_manifest,
    )
    assert "итог" in result.selected.entry.filename


def test_equal_business_candidates_are_ambiguous(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry(
                "1006 (682)_КС-6а июль 2026 ред2.xlsx",
                file_id="a",
                relative_path="folder_a/1006 (682)_КС-6а июль 2026 ред2.xlsx",
            ),
            make_entry(
                "1006 (682)_КС-6а июль 2026 ред2.xlsx",
                file_id="b",
                relative_path="folder_b/1006 (682)_КС-6а июль 2026 ред2.xlsx",
            ),
        ],
        make_manifest,
    )
    assert result.status == "MULTIPLE_TOP_CANDIDATES"
    assert result.selected is None


def test_copy_is_rejected_by_default(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026.xlsx"),
            make_entry("1006 (682)_КС-6а июль 2026 (1).xlsx"),
        ],
        make_manifest,
    )
    assert result.selected.entry.filename.endswith("2026.xlsx")
    assert any("PROBABLE_COPY" in c.rejection_reasons for c in result.rejected)


def test_approved_beats_draft_by_default(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry("1006 (682)_КС-6а июль 2026 черновик.xlsx"),
            make_entry("1006 (682)_КС-6а июль 2026 согласовано.xlsx"),
        ],
        make_manifest,
    )
    assert "согласовано" in result.selected.entry.filename


def test_wrong_index_never_compensated(make_entry, make_manifest) -> None:
    result = _select(
        [make_entry("0842 (623)_КС-6а июль 2026 ред999 итог.xlsx")],
        make_manifest,
    )
    assert result.status == "INDEX_NOT_AVAILABLE"
    assert result.selected is None


def test_inner_zip_entry_can_be_selected(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry(
                "1006 (682)_КС-6а июль 2026.xlsx",
                relative_path="reports/1006 (682)_КС-6а июль 2026.xlsx",
                is_archive_entry=True,
            )
        ],
        make_manifest,
    )
    assert result.status == "OK"
    assert result.selected.entry.archive_path is not None


def test_zip_container_alone_is_not_source(make_entry, make_manifest) -> None:
    result = _select(
        [
            make_entry(
                "1006 (682)_КС-6а июль 2026.zip",
                document_type="ks6a",
                extension=".zip",
            )
        ],
        make_manifest,
    )
    assert result.status == "ALL_CANDIDATES_REJECTED"
    assert result.selected is None


def test_empty_allowed_types_is_controlled(make_entry, make_manifest) -> None:
    result = _select(
        [make_entry("1006 (682)_КС-6а июль 2026.xlsx")],
        make_manifest,
        _request(allowed_document_types=()),
    )
    assert result.status == "NO_ALLOWED_DOCUMENT_TYPES"

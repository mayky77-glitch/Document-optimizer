from report_processor.identifiers.document_index import extract_document_index
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.metadata.periods import DocumentPeriod
from report_processor.selection.filters import filter_source_candidates
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)
from report_processor.selection.models import SourceSelectionRequest


def _request(**kwargs) -> SourceSelectionRequest:
    defaults = {
        "target_index": extract_document_index("1006 (682)").value,
        "target_period": DocumentPeriod(2026, 7),
        "preferred_document_types": ("ks6a", "ks2"),
        "allowed_document_types": ("ks6a", "ks2"),
    }
    defaults.update(kwargs)
    return SourceSelectionRequest(**defaults)


def _enrich(manifest):
    return enrich_manifest_with_document_metadata(enrich_manifest_with_document_indexes(manifest))


def test_wrong_index_is_rejected_before_scoring(make_entry, make_manifest) -> None:
    manifest = _enrich(make_manifest([make_entry("0842 (623)_КС-6а июль 2026.xlsx")]))
    result = filter_source_candidates(manifest.entries, _request())
    assert not result.accepted
    assert "INDEX_MISMATCH" in result.rejected[0].rejection_reasons
    assert result.rejected[0].score_components == ()


def test_default_filters_reject_copy_draft_outdated_and_non_excel(
    make_entry, make_manifest
) -> None:
    entries = [
        make_entry("1006 (682)_КС-6а июль 2026 (1).xlsx"),
        make_entry("1006 (682)_КС-6а июль 2026 черновик.xlsx"),
        make_entry("1006 (682)_КС-6а июль 2026 неактуал.xlsx"),
        make_entry("1006 (682)_КС-6а июль 2026.pdf"),
    ]
    result = filter_source_candidates(_enrich(make_manifest(entries)).entries, _request())
    reasons = [set(candidate.rejection_reasons) for candidate in result.rejected]
    assert any("PROBABLE_COPY" in item for item in reasons)
    assert any("DRAFT_FILE" in item for item in reasons)
    assert any("PROBABLY_OUTDATED" in item for item in reasons)
    assert any("UNSUPPORTED_EXTENSION" in item for item in reasons)


def test_unknown_period_respects_explicit_flag(make_entry, make_manifest) -> None:
    manifest = _enrich(make_manifest([make_entry("1006 (682)_КС-6а.xlsx")]))
    allowed = filter_source_candidates(manifest.entries, _request(allow_unknown_period=True))
    rejected = filter_source_candidates(manifest.entries, _request(allow_unknown_period=False))
    assert len(allowed.accepted) == 1
    assert "UNKNOWN_PERIOD_NOT_ALLOWED" in rejected.rejected[0].rejection_reasons


def test_period_mismatch_is_hard_only_in_exact_mode(make_entry, make_manifest) -> None:
    manifest = _enrich(make_manifest([make_entry("1006 (682)_КС-6а июнь 2026.xlsx")]))
    soft = filter_source_candidates(manifest.entries, _request(require_exact_period=False))
    hard = filter_source_candidates(manifest.entries, _request(require_exact_period=True))
    assert len(soft.accepted) == 1
    assert "PERIOD_MISMATCH" in hard.rejected[0].rejection_reasons


def test_zip_container_rejected_but_inner_excel_allowed(make_entry, make_manifest) -> None:
    entries = [
        make_entry(
            "1006 (682)_КС-6а июль 2026.zip",
            document_type="ks6a",
            extension=".zip",
        ),
        make_entry(
            "1006 (682)_КС-6а июль 2026.xlsx",
            relative_path="inside/1006 (682)_КС-6а июль 2026.xlsx",
            is_archive_entry=True,
        ),
    ]
    result = filter_source_candidates(_enrich(make_manifest(entries)).entries, _request())
    assert len(result.accepted) == 1
    assert result.accepted[0].entry.is_archive_entry
    assert "UNSUPPORTED_EXTENSION" in result.rejected[0].rejection_reasons

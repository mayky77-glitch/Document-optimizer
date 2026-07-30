from report_processor.identifiers.document_index import extract_document_index
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.metadata.periods import DocumentPeriod
from report_processor.selection.filters import filter_source_candidates
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)
from report_processor.selection.models import SourceScoringConfig, SourceSelectionRequest
from report_processor.selection.scoring import score_source_candidate


def _candidate(filename, make_entry, make_manifest, request):
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(make_manifest([make_entry(filename)]))
    )
    return filter_source_candidates(manifest.entries, request).accepted[0]


def _request(preferred=("ks6a", "ks2"), **kwargs):
    values = {
        "target_index": extract_document_index("1006 (682)").value,
        "target_period": DocumentPeriod(2026, 7),
        "preferred_document_types": preferred,
        "allowed_document_types": ("ks6a", "ks2"),
    }
    values.update(kwargs)
    return SourceSelectionRequest(**values)


def test_each_score_has_components(make_entry, make_manifest) -> None:
    request = _request()
    candidate = _candidate(
        "1006 (682)_КС-6а июль 2026 ред2 финал согласовано.xlsx",
        make_entry,
        make_manifest,
        request,
    )
    scored = score_source_candidate(candidate, request, SourceScoringConfig())
    by_code = {component.code: component.points for component in scored.score_components}
    assert by_code == {
        "EXACT_INDEX_MATCH": 100,
        "EXACT_PERIOD_MATCH": 40,
        "PREFERRED_DOCUMENT_TYPE": 30,
        "NUMERIC_REVISION": 2,
        "FINAL_VERSION": 8,
        "APPROVED_VERSION": 6,
    }
    assert scored.score == sum(by_code.values())


def test_type_priority_follows_request(make_entry, make_manifest) -> None:
    ks2_request = _request(preferred=("ks2", "ks6a"))
    candidate = _candidate(
        "1006 (682)_КС-2 июль 2026.xlsx",
        make_entry,
        make_manifest,
        ks2_request,
    )
    scored = score_source_candidate(candidate, ks2_request, SourceScoringConfig())
    component = next(c for c in scored.score_components if c.code == "PREFERRED_DOCUMENT_TYPE")
    assert component.points == 30


def test_unknown_and_mismatched_periods_are_explained(make_entry, make_manifest) -> None:
    request = _request()
    unknown = score_source_candidate(
        _candidate("1006 (682)_КС-6а.xlsx", make_entry, make_manifest, request),
        request,
        SourceScoringConfig(),
    )
    mismatch = score_source_candidate(
        _candidate(
            "1006 (682)_КС-6а июнь 2026.xlsx",
            make_entry,
            make_manifest,
            request,
        ),
        request,
        SourceScoringConfig(),
    )
    assert any(c.code == "UNKNOWN_PERIOD" and c.points == -10 for c in unknown.score_components)
    assert any(c.code == "PERIOD_MISMATCH" and c.points == -40 for c in mismatch.score_components)


def test_conflicting_draft_final_does_not_receive_final_bonus(make_entry, make_manifest) -> None:
    request = _request(include_drafts=True)
    candidate = _candidate(
        "1006 (682)_КС-6а июль 2026 ред2 черновик финал.xlsx",
        make_entry,
        make_manifest,
        request,
    )
    scored = score_source_candidate(candidate, request, SourceScoringConfig())
    codes = {component.code for component in scored.score_components}
    assert "FINAL_VERSION" not in codes
    assert "DRAFT" in codes
    assert "CONFLICTING_VERSION_MARKERS" in scored.warnings

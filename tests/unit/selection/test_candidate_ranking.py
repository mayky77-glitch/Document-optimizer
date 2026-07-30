from datetime import UTC, datetime

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
from report_processor.selection.ranking import (
    rank_source_candidates,
    top_candidates_are_ambiguous,
)
from report_processor.selection.scoring import score_source_candidates


def test_ranking_is_deterministic_but_path_does_not_resolve_business_tie(
    make_entry, make_manifest
) -> None:
    entries = [
        make_entry(
            "1006 (682)_КС-6а июль 2026 ред2.xlsx",
            file_id="b",
            relative_path="folder_b/file.xlsx",
            modified_at=datetime(2026, 7, 2, tzinfo=UTC),
        ),
        make_entry(
            "1006 (682)_КС-6а июль 2026 ред2.xlsx",
            file_id="a",
            relative_path="folder_a/file.xlsx",
            modified_at=datetime(2026, 7, 1, tzinfo=UTC),
        ),
    ]
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(make_manifest(entries))
    )
    request = SourceSelectionRequest(
        target_index=extract_document_index("1006 (682)").value,
        target_period=DocumentPeriod(2026, 7),
        preferred_document_types=("ks6a", "ks2"),
        allowed_document_types=("ks6a", "ks2"),
    )
    filtered = filter_source_candidates(manifest.entries, request)
    ranked = rank_source_candidates(
        score_source_candidates(filtered.accepted, request, SourceScoringConfig())
    )
    assert [candidate.rank for candidate in ranked] == [1, 2]
    assert ranked[0].file_id == "b"
    assert top_candidates_are_ambiguous(ranked)

from dataclasses import asdict

from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)


def test_manifest_enrichment_is_non_mutating_and_idempotent(make_entry, make_manifest) -> None:
    entry = make_entry("1006 (682)_КС-6а июль 2026 ред2 финал.xlsx")
    manifest = make_manifest([entry])
    indexed = enrich_manifest_with_document_indexes(manifest)
    enriched = enrich_manifest_with_document_metadata(indexed)
    repeated = enrich_manifest_with_document_metadata(enriched)

    assert manifest.entries[0].document_period is None
    assert enriched.entries[0].document_period.normalized == "2026-07"
    assert enriched.entries[0].document_revision.number == 2
    assert enriched.entries[0].is_final is True
    assert asdict(enriched) == asdict(repeated)


def test_manifest_summary_is_extended(make_entry, make_manifest) -> None:
    manifest = make_manifest(
        [
            make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx"),
            make_entry("1006 (682)_КС-2.xlsx"),
        ]
    )
    enriched = enrich_manifest_with_document_indexes(manifest)
    enriched = enrich_manifest_with_document_metadata(enriched)
    assert enriched.summary.entries_with_period == 1
    assert enriched.summary.entries_without_period == 1
    assert enriched.summary.entries_with_revision == 1
    assert enriched.summary.files_by_period == {"2026-07": 1}

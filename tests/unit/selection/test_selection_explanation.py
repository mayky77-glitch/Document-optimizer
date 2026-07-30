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


def _request():
    return SourceSelectionRequest(
        target_index=extract_document_index("1006 (682)").value,
        target_period=DocumentPeriod(2026, 7),
        preferred_document_types=("ks6a", "ks2"),
        allowed_document_types=("ks6a", "ks2"),
    )


def test_success_explanation_uses_score_components(make_entry, make_manifest) -> None:
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(
            make_manifest([make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx")])
        )
    )
    result = select_source_file(manifest, _request())
    text = "\n".join(result.explanation)
    for component in result.selected.score_components:
        assert component.explanation in result.explanation
    assert "/redacted-fixture/source" not in text


def test_ambiguity_explanation_is_concrete(make_entry, make_manifest) -> None:
    entries = [
        make_entry(
            "1006 (682)_КС-6а июль 2026 ред2.xlsx",
            file_id="a",
            relative_path="a/file.xlsx",
        ),
        make_entry(
            "1006 (682)_КС-6а июль 2026 ред2.xlsx",
            file_id="b",
            relative_path="b/file.xlsx",
        ),
    ]
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(make_manifest(entries))
    )
    result = select_source_file(manifest, _request())
    text = "\n".join(result.explanation)
    assert "1006 (682)" in text
    assert "2026-07" in text
    assert "автоматический выбор запрещён" in text.lower()

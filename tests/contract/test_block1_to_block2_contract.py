"""Contract: block 2 enriches a block 1 manifest without rescanning it."""

from dataclasses import asdict
from pathlib import Path

from report_processor import build_file_manifest, load_manifest_json, save_manifest_json
from report_processor.identifiers.manifest_enricher import enrich_manifest_with_document_indexes


def test_enrichment_preserves_block1_provenance_and_round_trips(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "1006 (682)_КС-2.xlsx").write_bytes(b"xlsx-placeholder")
    (source / "nested").mkdir()
    (source / "nested" / "0842 (623)_СВВР.xlsx").write_bytes(b"xlsx-placeholder")
    (source / "~$temporary.xlsx").write_bytes(b"xlsx-placeholder")

    inventory = build_file_manifest(source)
    enriched = enrich_manifest_with_document_indexes(inventory)
    output = tmp_path / "enriched.json"
    save_manifest_json(enriched, output)
    restored = load_manifest_json(output)

    assert [entry.file_id for entry in enriched.entries] == [
        entry.file_id for entry in inventory.entries
    ]
    assert [entry.relative_path for entry in enriched.entries] == [
        entry.relative_path for entry in inventory.entries
    ]
    assert inventory.entries[0].document_index is None
    assert enriched.summary.entries_with_document_index == 2
    assert enriched.summary.files_by_document_index == {"0842 (623)": 1, "1006 (682)": 1}
    assert asdict(restored) == asdict(enriched)

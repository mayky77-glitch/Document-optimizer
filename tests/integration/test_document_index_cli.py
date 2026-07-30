"""End-to-end block 1 → block 2 command-line workflow."""

import hashlib
from pathlib import Path

from report_processor.cli import EXIT_OK, main
from report_processor.inventory.file_manifest import load_manifest_json


def test_inventory_and_extract_indexes_cli_leave_source_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workbook = source / "1006 (682)_КС-2.xlsx"
    workbook.write_bytes(b"xlsx-placeholder")
    before = hashlib.sha256(workbook.read_bytes()).hexdigest()
    inventory_path = tmp_path / "inventory.json"
    enriched_path = tmp_path / "enriched.json"

    assert main(["inventory", "--source", str(source), "--output", str(inventory_path)]) == EXIT_OK
    assert (
        main(
            [
                "extract-indexes",
                "--manifest",
                str(inventory_path),
                "--output",
                str(enriched_path),
                "--no-use-parent-paths",
            ]
        )
        == EXIT_OK
    )

    after = hashlib.sha256(workbook.read_bytes()).hexdigest()
    manifest = load_manifest_json(enriched_path)
    assert after == before
    assert manifest.summary.entries_with_document_index == 1
    assert manifest.entries[0].document_index is not None

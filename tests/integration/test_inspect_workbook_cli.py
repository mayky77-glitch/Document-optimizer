import json
from datetime import UTC, datetime
from pathlib import Path

from conftest import regular_entry
from report_processor.cli import main
from report_processor.domain.models import FileManifest
from report_processor.inventory.file_manifest import build_manifest_summary, save_manifest_json


def test_inspect_workbook_cli_and_json(tmp_path: Path, workbook_path: Path, capsys):
    entry = regular_entry(workbook_path)
    manifest = FileManifest(
        source_path=str(tmp_path),
        source_kind="directory",
        created_at=datetime.now(UTC),
        entries=[entry],
        summary=build_manifest_summary([entry], "directory"),
    )
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "inspection.json"
    save_manifest_json(manifest, manifest_path)

    code = main(
        [
            "inspect-workbook",
            "--manifest",
            str(manifest_path),
            "--file-id",
            entry.file_id,
            "--sheet",
            "Данные",
            "--cell",
            "A3",
            "--output",
            str(output_path),
            "--log-level",
            "WARNING",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "FORMULA_WITHOUT_CACHED_VALUE" in captured.out
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["status"] == "OK"
    assert report["cells"][0]["coordinate"] == "A3"

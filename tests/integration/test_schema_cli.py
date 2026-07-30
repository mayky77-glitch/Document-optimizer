import json
from pathlib import Path

from conftest import regular_entry
from report_processor.cli import main
from report_processor.inventory.file_manifest import file_manifest_entry_to_dict


def test_detect_schema_cli_from_selection(schema_workbook_path: Path, tmp_path: Path) -> None:
    selection = tmp_path / "selection.json"
    output = tmp_path / "schema.json"
    selection.write_text(
        json.dumps(
            {
                "selected": {
                    "entry": file_manifest_entry_to_dict(regular_entry(schema_workbook_path))
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "detect-schema",
            "--selection",
            str(selection),
            "--output",
            str(output),
            "--sheet",
            "КС-6а",
        ]
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert payload["source_file_id"] == schema_workbook_path.name
    assert payload["worksheets"][0]["sheet_type"] == "ks6a"


def test_cli_rejects_two_source_modes(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    code = main(
        [
            "detect-schema",
            "--manifest",
            str(tmp_path / "manifest.json"),
            "--file-id",
            "x",
            "--selection",
            str(tmp_path / "selection.json"),
            "--output",
            str(output),
        ]
    )
    assert code == 9

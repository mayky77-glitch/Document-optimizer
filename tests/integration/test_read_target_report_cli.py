"""CLI wiring contract for the read-only Block 9 command."""

from __future__ import annotations

import json
from pathlib import Path

from report_processor.cli import main


def test_read_target_report_cli_rejects_missing_required_source_arguments(tmp_path: Path) -> None:
    output = tmp_path / "target-report.json"

    try:
        main(["read-target-report", "--output", str(output)])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError(
            "read-target-report must require an explicit selected source and schema"
        )


def test_read_target_report_cli_emits_json_for_explicit_source(
    schema_workbook_path: Path, tmp_path: Path
) -> None:
    output = tmp_path / "target-report.json"
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"source_file_id": schema_workbook_path.name}), encoding="utf-8")

    code = main(
        [
            "read-target-report",
            "--source",
            str(schema_workbook_path),
            "--schema",
            str(schema),
            "--output",
            str(output),
        ]
    )

    assert code == 0
    assert (
        json.loads(output.read_text(encoding="utf-8"))["schema"]["version"]
        == "TargetReportSchema-9.0"
    )

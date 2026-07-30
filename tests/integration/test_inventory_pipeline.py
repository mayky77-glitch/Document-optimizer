"""Интеграционный сценарий блока 1 без чтения содержимого документов."""

import json
import zipfile
from pathlib import Path

from report_processor.cli import EXIT_OK, main


def test_zip_inventory_cli_pipeline(tmp_path: Path) -> None:
    archive_path = tmp_path / "input.zip"
    output_path = tmp_path / "output" / "manifest.json"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("КС-2/КС-2 июль.xlsx", b"placeholder")
        archive.writestr("СВВР/СВВР июль.csv", b"placeholder")
        archive.writestr("../../unsafe.xlsx", b"placeholder")

    result = main(
        [
            "inventory",
            "--source",
            str(archive_path),
            "--output",
            str(output_path),
            "--log-level",
            "ERROR",
        ]
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == EXIT_OK
    assert payload["summary"]["total_entries"] == 3
    assert payload["summary"]["files_by_document_marker"] == {"ks2": 1, "svvr": 1}
    assert payload["summary"]["unsafe_archive_entries"] == 1

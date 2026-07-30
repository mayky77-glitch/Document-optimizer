from __future__ import annotations

import json

from report_processor.cli import main
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.inventory.file_manifest import save_manifest_json
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)


def test_select_source_cli_success(tmp_path, make_entry, make_manifest, capsys) -> None:
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(
            make_manifest([make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx")])
        )
    )
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "selection.json"
    save_manifest_json(manifest, manifest_path)
    exit_code = main(
        [
            "select-source",
            "--manifest",
            str(manifest_path),
            "--index",
            "1006 (682)",
            "--period",
            "2026-07",
            "--preferred-types",
            "ks6a,ks2",
            "--allowed-types",
            "ks6a,ks2",
            "--json-output",
            str(output_path),
            "--log-level",
            "ERROR",
        ]
    )
    assert exit_code == 0
    assert "Выбран файл" in capsys.readouterr().out
    assert json.loads(output_path.read_text(encoding="utf-8"))["status"] == "OK"


def test_select_source_cli_ambiguity_exit_code(tmp_path, make_entry, make_manifest) -> None:
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(
            make_manifest(
                [
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
            )
        )
    )
    manifest_path = tmp_path / "manifest.json"
    save_manifest_json(manifest, manifest_path)
    exit_code = main(
        [
            "select-source",
            "--manifest",
            str(manifest_path),
            "--index",
            "1006 (682)",
            "--period",
            "2026-07",
            "--preferred-types",
            "ks6a,ks2",
            "--allowed-types",
            "ks6a,ks2",
            "--log-level",
            "ERROR",
        ]
    )
    assert exit_code == 3


def test_select_source_cli_invalid_period_exit_code(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "select-source",
            "--manifest",
            str(tmp_path / "missing.json"),
            "--index",
            "1006 (682)",
            "--period",
            "июль 2026",
            "--preferred-types",
            "ks6a,ks2",
            "--allowed-types",
            "ks6a,ks2",
            "--log-level",
            "ERROR",
        ]
    )
    assert exit_code == 4
    assert "Некорректный период" in capsys.readouterr().err

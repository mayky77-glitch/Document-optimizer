"""Тесты сборки и сохранения манифеста."""

import json
from pathlib import Path

import pytest

from report_processor.domain.exceptions import ManifestWriteError, SourceNotFoundError
from report_processor.inventory.file_manifest import build_file_manifest, save_manifest_json


def test_single_file_manifest(tmp_path: Path) -> None:
    source = tmp_path / "КС-2 июль.xlsx"
    source.write_bytes(b"content")

    manifest = build_file_manifest(source)

    assert manifest.source_kind == "file"
    assert manifest.summary.total_entries == 1
    assert manifest.entries[0].document_type == "ks2"
    assert manifest.entries[0].relative_path == source.name


def test_missing_source_is_controlled(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFoundError):
        build_file_manifest(tmp_path / "missing")


def test_save_json_preserves_cyrillic_and_dates(tmp_path: Path) -> None:
    source = tmp_path / "КС-6а.xlsx"
    source.write_bytes(b"data")
    output = tmp_path / "nested" / "manifest.json"

    manifest = build_file_manifest(source)
    save_manifest_json(manifest, output)
    text = output.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert "КС-6а.xlsx" in text
    assert payload["created_at"] == manifest.created_at.isoformat()
    assert payload["entries"][0]["modified_at"] == manifest.entries[0].modified_at.isoformat()
    assert output.parent.exists()


def test_save_json_can_replace_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "report.xlsx"
    source.write_bytes(b"data")
    output = tmp_path / "manifest.json"
    output.write_text("old", encoding="utf-8")

    save_manifest_json(build_file_manifest(source), output)

    assert json.loads(output.read_text(encoding="utf-8"))["source_kind"] == "file"


def test_failed_atomic_replace_keeps_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "report.xlsx"
    source.write_bytes(b"data")
    output = tmp_path / "manifest.json"
    output.write_text("previous", encoding="utf-8")

    def fail_replace(source_path: Path, target_path: Path) -> None:
        raise OSError(f"replace failed: {source_path} -> {target_path}")

    monkeypatch.setattr("report_processor.inventory.serialization.os.replace", fail_replace)

    with pytest.raises(ManifestWriteError):
        save_manifest_json(build_file_manifest(source), output)

    assert output.read_text(encoding="utf-8") == "previous"
    assert list(tmp_path.glob(".manifest.json.*.tmp")) == []


def test_summary_counts_all_document_markers(tmp_path: Path) -> None:
    source = tmp_path / "КС-2_КС-3_КС-6а.xlsx"
    source.write_bytes(b"content")

    manifest = build_file_manifest(source)

    assert manifest.summary.files_by_document_type == {"ks6a": 1}
    assert manifest.summary.files_by_document_marker == {"ks2": 1, "ks3": 1, "ks6a": 1}


def test_manifest_json_round_trip_preserves_models(tmp_path: Path) -> None:
    from dataclasses import asdict

    from report_processor.inventory.file_manifest import load_manifest_json

    source = tmp_path / "КС-2_КС-6а.xlsx"
    source.write_bytes(b"data")
    output = tmp_path / "manifest.json"
    original = build_file_manifest(source)

    save_manifest_json(original, output)
    restored = load_manifest_json(output)

    assert asdict(restored) == asdict(original)


def test_load_manifest_rejects_inconsistent_summary(tmp_path: Path) -> None:
    from report_processor.domain.exceptions import ManifestReadError
    from report_processor.inventory.file_manifest import load_manifest_json

    output = tmp_path / "manifest.json"
    output.write_text(
        '{"source_path":"x","source_kind":"file","created_at":"2026-01-01T00:00:00+00:00",'
        '"entries":[],"summary":{"total_entries":1,"total_size_bytes":0,'
        '"files_by_extension":{},"files_by_document_type":{},'
        '"files_by_document_marker":{},"temporary_files":0,"probable_copies":0,'
        '"probably_outdated_files":0,"unsafe_archive_entries":0,"warnings_count":0}}',
        encoding="utf-8",
    )

    with pytest.raises(ManifestReadError):
        load_manifest_json(output)

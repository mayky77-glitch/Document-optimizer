"""Контракт блока 1: файловый источник → FileManifest → JSON → FileManifest."""

from dataclasses import asdict
from pathlib import Path

import pytest

from report_processor import build_file_manifest, load_manifest_json, save_manifest_json
from report_processor.domain import (
    FileManifest,
    FileManifestEntry,
    ManifestReadError,
    ManifestSummary,
    StatusCode,
)


def test_public_manifest_contract_preserves_identity_and_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "КС-2_КС-6а.xlsx").write_bytes(b"xlsx-placeholder")
    (source / "nested").mkdir()
    (source / "nested" / "СВВР.csv").write_text("row", encoding="utf-8")

    first = build_file_manifest(source)
    second = build_file_manifest(source)
    output = tmp_path / "manifest.json"
    save_manifest_json(first, output)
    restored = load_manifest_json(output)

    assert isinstance(restored, FileManifest)
    assert isinstance(restored.summary, ManifestSummary)
    assert all(isinstance(entry, FileManifestEntry) for entry in restored.entries)
    assert [entry.file_id for entry in first.entries] == [entry.file_id for entry in second.entries]
    assert [entry.relative_path for entry in first.entries] == [
        entry.relative_path for entry in second.entries
    ]
    assert asdict(restored) == asdict(first)
    assert all(entry.source_root == str(source.resolve()) for entry in restored.entries)
    allowed_statuses = {StatusCode.OK.value, StatusCode.WARNING.value}
    assert all(entry.status in allowed_statuses for entry in restored.entries)
    combined = next(entry for entry in restored.entries if entry.filename.startswith("КС-2_КС-6а"))
    assert combined.document_markers == ["ks6a", "ks2"]


def test_public_manifest_contract_rejects_invalid_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "broken.json"
    manifest_path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ManifestReadError):
        load_manifest_json(manifest_path)

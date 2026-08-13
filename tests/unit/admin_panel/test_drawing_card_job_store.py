"""Contracts for the private, restart-safe drawing-card job manifest store."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import report_processor.admin_panel.drawing_card_job_store as drawing_card_job_store
from report_processor.admin_panel.drawing_card_job_store import (
    MANIFEST_CONTRACT,
    MANIFEST_FILENAME,
    DrawingCardJobStore,
)


def _manifest(**extra: object) -> dict[str, object]:
    return {
        "contract": MANIFEST_CONTRACT,
        "attempt": 1,
        "source_paths": ["sources/01-source.xlsx"],
        "output_path": "attempts/0001/drawing-card.xlsx",
        **extra,
    }


def test_round_trip_is_private_and_path_free_of_absolutes(tmp_path: Path) -> None:
    store = DrawingCardJobStore(tmp_path / "private")
    stored = store.save("job_01", _manifest())

    assert stored["output_path"] == "attempts/0001/drawing-card.xlsx"
    assert store.load("job_01") == stored
    stored["attempt"] = 99
    assert store.load("job_01") == _manifest()
    manifest_path = tmp_path / "private" / "job_01" / MANIFEST_FILENAME
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "private").stat().st_mode & 0o777 == 0o700
    assert all(str(tmp_path) not in json.dumps(value) for value in store.load_all().values())


@pytest.mark.parametrize(
    "value",
    [
        "/private/output.xlsx",
        "../outside.xlsx",
        "C:\\private\\output.xlsx",
        "a\\b.xlsx",
        "a//b.xlsx",
        "a/../b.xlsx",
        "a/./b.xlsx",
    ],
)
def test_save_rejects_hostile_or_non_normalized_job_relative_paths(
    tmp_path: Path, value: str
) -> None:
    store = DrawingCardJobStore(tmp_path / "private")

    with pytest.raises(ValueError):
        store.save("job_01", _manifest(output_path=value))


@pytest.mark.parametrize("job_id", ["../outside", ".", "", "a/b", "x" * 97])
def test_job_identifiers_are_bounded_and_cannot_escape_workspace(
    tmp_path: Path, job_id: str
) -> None:
    store = DrawingCardJobStore(tmp_path / "private")

    with pytest.raises(ValueError):
        store.save(job_id, _manifest())
    assert store.load(job_id) is None


def test_load_all_skips_corrupt_oversized_and_hostile_manifests(tmp_path: Path) -> None:
    root = tmp_path / "private"
    store = DrawingCardJobStore(root)
    store.save("good", _manifest())
    hostile = root / "hostile"
    hostile.mkdir()
    (hostile / MANIFEST_FILENAME).write_text(
        json.dumps(_manifest(source_paths=["/Users/secret.xlsx"])), encoding="utf-8"
    )
    corrupt = root / "corrupt"
    corrupt.mkdir()
    (corrupt / MANIFEST_FILENAME).write_text("{", encoding="utf-8")
    oversized = root / "oversized"
    oversized.mkdir()
    (oversized / MANIFEST_FILENAME).write_bytes(b"x" * (1_048_577))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / MANIFEST_FILENAME).write_text(json.dumps(_manifest()), encoding="utf-8")
    (root / "linked").symlink_to(outside, target_is_directory=True)

    assert store.load_all() == {"good": _manifest()}
    assert store.load("hostile") is None
    assert store.load("linked") is None


def test_active_manifest_survives_valid_terminal_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DrawingCardJobStore(tmp_path / "private")
    monkeypatch.setattr(drawing_card_job_store, "MAX_LOADED_JOBS", 2)
    for index in range(5):
        store.save(f"terminal-{index}", _manifest(status="failed", updated_at=f"2026-08-0{index}"))
    active = _manifest(status="review_required", updated_at="2026-08-09")
    store.save("active-review", active)

    restored = store.load_all()

    assert "active-review" in restored
    assert len(restored) <= drawing_card_job_store.MAX_LOADED_JOBS


def test_load_all_is_non_destructive_for_generic_terminal_manifests(tmp_path: Path) -> None:
    store = DrawingCardJobStore(tmp_path / "private")
    terminal = _manifest(status="failed", updated_at="2026-08-01")
    store.save("terminal", terminal)

    store.load_all()

    assert store.load("terminal") == terminal


def test_atomic_replace_keeps_previous_manifest_if_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DrawingCardJobStore(tmp_path / "private")
    store.save("job_01", _manifest(attempt=1))

    def explode(_source: object, _target: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(os, "replace", explode)
    with pytest.raises(OSError, match="replace failed"):
        store.save("job_01", _manifest(attempt=2))

    monkeypatch.undo()
    assert store.load("job_01") == _manifest(attempt=1)
    assert not list((tmp_path / "private" / "job_01").glob("*.tmp"))


def test_delete_only_removes_manifest_not_job_artifacts(tmp_path: Path) -> None:
    store = DrawingCardJobStore(tmp_path / "private")
    store.save("job_01", _manifest())
    artifact = tmp_path / "private" / "job_01" / "sources" / "01-source.xlsx"
    artifact.parent.mkdir()
    artifact.write_bytes(b"private")

    assert store.delete("job_01") is True
    assert artifact.read_bytes() == b"private"
    assert store.load("job_01") is None


def test_expected_contract_is_selectable_without_changing_drawing_card_default(
    tmp_path: Path,
) -> None:
    store = DrawingCardJobStore(tmp_path / "private", expected_contract="OtherManifest-1.0")
    other = {**_manifest(), "contract": "OtherManifest-1.0"}

    assert store.save("-job_01", other) == other
    assert store.load("-job_01") == other
    assert DrawingCardJobStore(tmp_path / "private").load("-job_01") is None

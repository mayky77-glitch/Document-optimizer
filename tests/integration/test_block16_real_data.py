"""Real-input invariance checks without reading or emitting document content."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from report_processor.audit import export_snapshot

_SOURCE_SHA = "556454e5c087f1728c994b2888191644f04d29d48fbd2a29e9aa136cf1ab0698"
_TARGET_SHA = "5b38ed6650aa5c1388c2757f3fa7aab54d012f2e54a9b0f6287f4badb1904194"


def _inputs() -> tuple[Path, Path]:
    source, target = (
        os.getenv("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX"),
        os.getenv("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX"),
    )
    if not source or not target:
        pytest.skip("real XLSX paths are not set")
    return Path(source), Path(target)


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_real_source_and_target_hash_size_and_mtime_stay_unchanged(tmp_path) -> None:
    source, target = _inputs()
    before = (_fingerprint(source), _fingerprint(target))
    assert before[0][0] == _SOURCE_SHA and before[1][0] == _TARGET_SHA
    export_snapshot(({"run_id": "real-input-audit", "count": 2},), tmp_path / "audit.json", "json")
    assert (_fingerprint(source), _fingerprint(target)) == before

"""Read-only real-input safety evidence for optional semantic suggestions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from report_processor.stage_rag import StageRelationRAG, StageText

from fixtures.stage_rag.builders import FakeEncoder


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _real_inputs() -> tuple[Path, Path]:
    source = os.getenv("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target = os.getenv("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source or not target:
        pytest.skip("real XLSX paths are not set")
    paths = (Path(source), Path(target))
    if not all(path.is_file() and path.suffix.casefold() == ".xlsx" for path in paths):
        pytest.skip("real XLSX paths must name readable .xlsx files")
    return paths


def test_real_workbook_paths_remain_byte_for_byte_unchanged() -> None:
    source, target = _real_inputs()
    before = (_fingerprint(source), _fingerprint(target))
    suggestions = StageRelationRAG(
        FakeEncoder({source.stem: (1, 0), target.stem: (1, 0)}), embedding_dimensions=2
    ).suggest((StageText("source", source.stem),), (StageText("target", target.stem),), k=1)

    assert suggestions[0].requires_manual_review and not suggestions[0].auto_accepted
    assert (_fingerprint(source), _fingerprint(target)) == before

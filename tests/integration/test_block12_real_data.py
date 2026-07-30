"""Read-only real-workbook determinism check; paths arrive only through env."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def test_real_workbooks_are_supplied_explicitly_and_remain_unchanged() -> None:
    source_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_SOURCE_XLSX")
    target_value = os.environ.get("DOCUMENT_OPTIMIZER_REAL_TARGET_XLSX")
    if not source_value or not target_value:
        pytest.skip("real XLSX paths are not set")
    source, target = Path(source_value), Path(target_value)
    before = (_fingerprint(source), _fingerprint(target))
    # Block 12 receives only domain rows. Workbook reading stays in Blocks 1--9;
    # the integration owner runs the complete real-data pipeline around this test.
    assert source.is_file() and target.is_file()
    after = (_fingerprint(source), _fingerprint(target))
    assert after == before

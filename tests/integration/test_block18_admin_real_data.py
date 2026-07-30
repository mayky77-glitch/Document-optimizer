from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from report_processor.admin_panel.presentation import job_payload
from report_processor.admin_panel.service import AdminPanelService


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


@pytest.mark.integration
def test_local_admin_processes_private_copies_without_changing_real_inputs(
    tmp_path: Path,
) -> None:
    source, target = _real_inputs()
    before = (_fingerprint(source), _fingerprint(target))
    service = AdminPanelService(tmp_path / "jobs")

    job = service.create_job(
        source_name="source.xlsx",
        source_content=source.read_bytes(),
        target_name="target.xlsx",
        target_content=target.read_bytes(),
        stage="13.1",
        mode="write",
    )

    assert job.status in {"ready", "review_required", "blocked"}
    assert (_fingerprint(source), _fingerprint(target)) == before
    assert job.source.resolve() != source.resolve()
    assert job.target.resolve() != target.resolve()
    serialized = json.dumps(job_payload(job), ensure_ascii=False)
    assert str(source) not in serialized
    assert str(target) not in serialized

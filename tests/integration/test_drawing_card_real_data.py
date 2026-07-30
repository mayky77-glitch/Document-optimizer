"""Opt-in immutable real-data smoke test for the drawing-card admin service."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardService


def _fingerprint(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _real_source() -> Path:
    value = os.getenv("DOCUMENT_OPTIMIZER_DRAWING_CARD_REAL_SOURCE_XLSX")
    if not value:
        pytest.skip("DOCUMENT_OPTIMIZER_DRAWING_CARD_REAL_SOURCE_XLSX is not set")
    path = Path(value)
    if not path.is_file() or path.suffix.casefold() != ".xlsx":
        pytest.skip("real source must be a readable .xlsx file")
    return path


@pytest.mark.integration
def test_real_source_is_immutable_and_matches_demo_acceptance(tmp_path: Path) -> None:
    source = _real_source()
    before = _fingerprint(source)
    service = DrawingCardService(tmp_path / "private-workspaces")
    job = service.create_job(sources=[(source.name, source.read_bytes())])

    assert _fingerprint(source) == before
    assert job.status == "ready"
    assert drawing_card_job_payload(job)["summary"] == {
        "source_files": 1,
        "extracted_rows": 7,
        "card_rows": 32,
        "manual_review": 0,
    }

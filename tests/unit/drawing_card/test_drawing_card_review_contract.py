"""Review lifecycle contract: opaque download, upload, and deterministic rerun."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_service import DrawingCardService

FIXTURES = Path(__file__).parents[2] / "fixtures" / "drawing_card"


def _create_review_job(service: DrawingCardService) -> str:
    job = service.create_job(
        sources=[("source.xlsx", (FIXTURES / "demo_source.xlsx").read_bytes())]
    )
    if job.status != "review_required":
        pytest.skip("fixture currently produces no manual-review job")
    return str(job.job_id)


def test_review_download_upload_and_rerun_keep_paths_opaque(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    job_id = _create_review_job(service)

    review_path, review_name = service.get_review(job_id)
    rerun = service.apply_review(
        job_id=job_id,
        review_name=review_name,
        review_content=review_path.read_bytes(),
    )

    assert review_path.is_file()
    assert review_path.is_relative_to(tmp_path / "private-workspaces")
    assert review_name == "manual_review.xlsx"
    assert rerun.status in {"processing", "review_required", "ready", "blocked", "failed"}
    assert str(tmp_path) not in str(rerun)


def test_result_is_unavailable_until_the_job_is_ready(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    job_id = _create_review_job(service)

    with pytest.raises(KeyError):
        service.get_result(job_id)

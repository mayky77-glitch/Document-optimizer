from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardService
from report_processor.drawing_card.models import WorkflowRequest, WorkflowResult
from report_processor.drawing_card.workflow import _publication_blockers
from report_processor.hierarchy import HierarchyIssue
from report_processor.processing.adapters import DefaultProcessingAdapters, ProcessingContext
from report_processor.processing.contracts import ProcessMode


def test_hierarchy_integrity_warning_is_a_strict_publication_blocker(tmp_path: Path) -> None:
    result = WorkflowResult(
        run_id="hierarchy-run",
        status="OK",
        work_dir=tmp_path / "run",
        warnings=["HIERARCHY_COST_MISMATCH"],
    )

    assert _publication_blockers(result) == ["HIERARCHY_COST_MISMATCH"]


def test_reconciliation_write_is_blocked_when_hierarchy_requires_review(tmp_path: Path) -> None:
    context = ProcessingContext(
        mode=ProcessMode.WRITE,
        strict=True,
        run_key="hierarchy-run",
        temporary_directory=tmp_path,
        values={"hierarchy_issues": (HierarchyIssue("HIERARCHY_COST_MISMATCH", "warning"),)},
    )

    with pytest.raises(RuntimeError, match="HIERARCHY_INTEGRITY_BLOCKED"):
        DefaultProcessingAdapters().write(context)


def test_drawing_admin_exposes_hierarchy_blocker_without_category_review_item(
    tmp_path: Path,
) -> None:
    def blocked_runner(request: WorkflowRequest) -> WorkflowResult:
        work_dir = request.work_dir / "blocked-run"
        work_dir.mkdir(parents=True)
        return WorkflowResult(
            run_id="blocked-run",
            status="BLOCKED",
            work_dir=work_dir,
            warnings=["HIERARCHY_COST_MISMATCH"],
        )

    service = DrawingCardService(tmp_path / "workspaces", runner=blocked_runner)
    job = service.create_job(sources=[("source.xlsx", b"PK\x03\x04workbook")])
    payload = drawing_card_job_payload(job)

    assert job.status == "blocked"
    assert job.review_items == {}
    assert payload["warnings"] == ["HIERARCHY_COST_MISMATCH"]
    assert payload["can_upload_review"] is False
    assert payload["result_url"] is None

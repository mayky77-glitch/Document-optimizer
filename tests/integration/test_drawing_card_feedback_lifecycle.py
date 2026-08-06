from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.review.inline import review_approval
from report_processor.drawing_card.statuses import Status


def _review_job(service: DrawingCardService) -> DrawingCardJob:
    directory = service.workspace_root / "review-job"
    directory.mkdir()
    row = DrawingSourceRow(
        row_id="review-row",
        location=DrawingSourceLocation("source", "safe.xlsx", "Лист1", 7, ("A7",)),
        object_index_raw="1001",
        drawing_code_raw="D-1",
        work_name_raw="Монтаж кабеля",
        unit_raw="м",
        remaining_quantity=Decimal("2"),
        remaining_total_cost=Decimal("10"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )
    decision = MatchDecision(
        row_id=row.row_id,
        category=TargetWorkCategory.POWER_CABLE,
        quantity_decision="review",
        cost_decision="review",
        quantity_rule_id=None,
        cost_rule_id=None,
        quantity_confidence=0.5,
        cost_confidence=0.5,
        matching_strategy="manual_review",
        evidence_ids=(),
        reason="manual",
        requires_manual_review=True,
        status=Status.OK,
        warnings=(),
    )
    job = DrawingCardJob(
        job_id="review-job",
        directory=directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        feedback_project_id="project",
        feedback_rules_version="rules",
        feedback_input_hashes=("a" * 64,),
        review_items={row.row_id: {"review_id": row.row_id}},
        review_rows={row.row_id: row},
        review_decisions={row.row_id: decision},
        inline_approvals={
            row.row_id: review_approval(row.row_id, "approve", TargetWorkCategory.POWER_CABLE.value)
        },
    )
    service._jobs[job.job_id] = job
    return job


def test_feedback_ledger_failure_does_not_schedule_rerun(tmp_path: Path) -> None:
    calls = []

    def runner(request):
        calls.append(request)
        raise AssertionError("runner must not be called after feedback failure")

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = _review_job(service)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")
    (service.workspace_root / "review-feedback-v2.jsonl").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        service.apply_inline_review(job_id=job.job_id)

    assert calls == []
    assert job.inline_approvals


def test_stale_membership_version_and_context_bounds_are_rejected(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private")
    job = _review_job(service)

    with pytest.raises(ValueError, match="stale membership"):
        service.put_review_item(
            job_id=job.job_id,
            review_id="review-row",
            action="approve",
            category=TargetWorkCategory.POWER_CABLE.value,
            version="obsolete",
        )
    with pytest.raises(ValueError, match="between 1 and 5"):
        service.get_review_context(job_id=job.job_id, review_id="review-row", radius=0)

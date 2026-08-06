from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardService
from report_processor.drawing_card.models import (
    DrawingCardResultRow,
    DrawingCode,
    DrawingSourceLocation,
    DrawingSourceRow,
    TargetWorkCategory,
    WorkflowRequest,
    WorkflowResult,
)
from report_processor.drawing_card.statuses import Status
from report_processor.drawing_card.workflow import (
    _publication_blocker_counts,
    _publication_blockers,
)
from report_processor.hierarchy import HierarchyIssue
from report_processor.processing.adapters import DefaultProcessingAdapters, ProcessingContext
from report_processor.processing.contracts import ProcessMode


def _contributing_card_row(row_id: str = "child-row") -> DrawingCardResultRow:
    return DrawingCardResultRow(
        object_index="0908",
        drawing_code=DrawingCode("Ч-1", "ч-1", "ч-1", ("ч-1",), Status.OK, ()),
        category=TargetWorkCategory.CONCRETE_WORKS,
        display_name="Бетонные работы",
        result_unit="м3",
        remaining_quantity=Decimal("1"),
        remaining_total_cost=Decimal("10"),
        quantity_source_rows=(row_id,),
        cost_source_rows=(row_id,),
        quantity_rule_id="rule",
        cost_rule_id="rule",
        quantity_confidence=1,
        cost_confidence=1,
        requires_manual_review=False,
        status=Status.OK,
        warnings=(),
    )


def _source_row(row_id: str, *warnings: str) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 2, ("A2",)),
        object_index_raw="0908",
        drawing_code_raw="Ч-1",
        work_name_raw="Бетонные работы",
        unit_raw="м3",
        remaining_quantity=Decimal("1"),
        remaining_total_cost=Decimal("10"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period="2026-07",
        source_revision=None,
        status=Status.WARNING if warnings else Status.OK,
        warnings=warnings,
    )


def test_drawing_card_hierarchy_reconciliation_is_diagnostic_not_a_publication_blocker(
    tmp_path: Path,
) -> None:
    result = WorkflowResult(
        run_id="hierarchy-run",
        status="OK",
        work_dir=tmp_path / "run",
        hierarchy_issues=[
            HierarchyIssue(
                "HIERARCHY_COST_MISMATCH",
                "warning",
                row_id="parent-row",
                related_row_ids=("child-row",),
            )
        ],
        card_rows=[_contributing_card_row()],
    )

    assert _publication_blockers(result) == []


def test_manual_review_blocker_count_reports_actual_rows(tmp_path: Path) -> None:
    result = WorkflowResult(
        run_id="review-count",
        status="BLOCKED",
        work_dir=tmp_path / "run",
        warnings=["MANUAL_REVIEW_REQUIRED:6"],
        manual_review_count=6,
    )

    assert _publication_blocker_counts(result) == {"MANUAL_REVIEW_REQUIRED": 6}


def test_irrelevant_hierarchy_issue_and_position_gap_do_not_block_publication(
    tmp_path: Path,
) -> None:
    result = WorkflowResult(
        run_id="hierarchy-run",
        status="OK",
        work_dir=tmp_path / "run",
        hierarchy_issues=[
            HierarchyIssue(
                "HIERARCHY_COST_MISMATCH",
                "warning",
                row_id="other-parent",
                related_row_ids=("other-child",),
            ),
            HierarchyIssue("HIERARCHY_POSITION_GAP", "warning"),
        ],
        card_rows=[_contributing_card_row()],
    )

    assert _publication_blockers(result) == []


def test_xlsb_capability_notice_does_not_block_but_missing_formula_cache_does(
    tmp_path: Path,
) -> None:
    notice = WorkflowResult(
        run_id="xlsb-notice",
        status="OK",
        work_dir=tmp_path / "notice",
        warnings=[Status.FORMULA_NOT_AVAILABLE_FOR_BACKEND],
    )
    unsafe = WorkflowResult(
        run_id="formula-cache",
        status="OK",
        work_dir=tmp_path / "unsafe",
        source_rows=[_source_row("child-row", Status.FORMULA_WITHOUT_CACHED_VALUE)],
        card_rows=[_contributing_card_row()],
    )

    assert _publication_blockers(notice) == []
    assert _publication_blockers(unsafe) == [Status.FORMULA_WITHOUT_CACHED_VALUE]


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
            blockers=["HIERARCHY_COST_MISMATCH"],
            blocker_counts={"HIERARCHY_COST_MISMATCH": 3},
        )

    service = DrawingCardService(tmp_path / "workspaces", runner=blocked_runner)
    job = service.create_job(
        sources=[
            (
                "source.xlsx",
                (
                    Path(__file__).parents[1] / "fixtures" / "drawing_card" / "demo_source.xlsx"
                ).read_bytes(),
            )
        ]
    )
    payload = drawing_card_job_payload(job)

    assert job.status == "blocked"
    assert job.review_items == {}
    assert payload["warnings"] == ["HIERARCHY_COST_MISMATCH"]
    assert payload["blocking_reasons"] == [
        {
            "code": "HIERARCHY_COST_MISMATCH",
            "message": (
                "Контрольная сумма секции не совпадает с суммой её измеряемых строк. "
                "Это диагностика и сама по себе не блокирует карточку."
            ),
            "action": ("Проверьте суммы, если они используются для финансовой сверки."),
            "count": 3,
            "blocking": True,
        }
    ]
    assert payload["can_upload_review"] is False
    assert payload["result_url"] is None

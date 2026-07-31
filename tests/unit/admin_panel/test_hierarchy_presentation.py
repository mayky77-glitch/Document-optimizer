from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from report_processor.admin_panel.presentation import processing_presentation
from report_processor.hierarchy import HierarchyIssue


def test_hierarchy_cost_discrepancy_is_russian_orange_and_exposes_actionable_amounts() -> None:
    issue = HierarchyIssue(
        code="HIERARCHY_COST_MISMATCH",
        severity="warning",
        row_id="private-row-id",
        related_row_ids=("private-child-id",),
        position_code="6.1",
        parent_amount=Decimal("120"),
        direct_children_amount=Decimal("100"),
        delta=Decimal("20"),
        tolerance=Decimal("0.01"),
    )
    result = SimpleNamespace(
        artifacts={"quality_report": SimpleNamespace(summary=None, issues=(issue,))},
        state="MANUAL_REVIEW_REQUIRED",
        exit_code=3,
        warnings=(),
        errors=(),
    )

    _summary, discrepancies, _suggestions = processing_presentation(result)

    assert discrepancies == [
        {
            "discrepancy_id": discrepancies[0]["discrepancy_id"],
            "code": "HIERARCHY_COST_MISMATCH",
            "category": "hierarchy_review",
            "color": "orange",
            "severity": "warning",
            "message": "Требуется проверка.",
            "position_code": "6.1",
            "parent_amount": "120",
            "direct_children_amount": "100",
            "delta": "20",
            "tolerance": "0.01",
        }
    ]
    assert "private-row-id" not in str(discrepancies)

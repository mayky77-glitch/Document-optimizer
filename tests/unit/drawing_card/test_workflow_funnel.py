"""Contracts for private row-disposition funnel accounting."""

from __future__ import annotations

from decimal import Decimal

from report_processor.drawing_card.audit.funnel import (
    DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
    DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
    disposition_for_decision,
    disposition_for_row,
    funnel_summary,
)
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.statuses import Status


def _row(**changes) -> DrawingSourceRow:
    values = {
        "row_id": "row-1",
        "location": DrawingSourceLocation(
            file_id="file-1",
            filename="/sensitive/source/private-book.xlsx",
            sheet_name="Sheet 1",
            row_number=19,
            coordinates=("A19",),
        ),
        "object_index_raw": "1001",
        "drawing_code_raw": "A-1",
        "work_name_raw": "Cable work",
        "unit_raw": "m",
        "remaining_quantity": Decimal("5"),
        "remaining_total_cost": Decimal("12"),
        "formula_values": (),
        "cached_values": (),
        "source_document_type": "ks6a",
        "source_period": "2026-08",
        "source_revision": None,
        "status": Status.OK,
        "warnings": ("INVALID_NUMBER:internal detail",),
        "position_code_raw": "1.2",
        "cost_type_code_raw": "work",
    }
    values.update(changes)
    return DrawingSourceRow(**values)


def _decision(**changes) -> MatchDecision:
    values = {
        "row_id": "row-1",
        "category": TargetWorkCategory.LOW_CURRENT_CABLE,
        "quantity_decision": "include",
        "cost_decision": "include",
        "quantity_rule_id": "rule-1",
        "cost_rule_id": None,
        "quantity_confidence": 1.0,
        "cost_confidence": None,
        "matching_strategy": "test",
        "evidence_ids": (),
        "reason": "test",
        "requires_manual_review": False,
        "status": Status.OK,
        "warnings": (),
    }
    values.update(changes)
    return MatchDecision(**values)


def test_disposition_record_is_private_audit_safe_and_keeps_controlled_fields() -> None:
    record = disposition_for_row(
        _row(),
        disposition=DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
        reason_code="HIERARCHY_AGGREGATE_POLICY",
        row_role="aggregate",
    )

    assert record.file_id == "file-1"
    assert record.safe_basename == "private-book.xlsx"
    assert record.sheet_name == "Sheet 1"
    assert record.row_number == 19
    assert record.position_code == "1.2"
    assert record.row_role == "aggregate"
    assert record.hazard_flags == ("INVALID_NUMBER",)
    assert "/sensitive" not in record.safe_basename


def test_matcher_outcomes_have_exactly_one_terminal_disposition() -> None:
    matched = disposition_for_decision(_row(), _decision())
    review = disposition_for_decision(
        _row(row_id="row-2"),
        _decision(row_id="row-2", requires_manual_review=True),
    )
    unclassified = disposition_for_decision(
        _row(row_id="row-3"), _decision(row_id="row-3", category=None)
    )

    assert [record.disposition for record in (matched, review, unclassified)] == [
        "MATCHED",
        "MANUAL_REVIEW",
        "UNCLASSIFIED",
    ]
    assert matched.rule_id == "rule-1"


def test_funnel_conserves_rows_and_reports_explicit_unclassified_count() -> None:
    records = [
        disposition_for_decision(_row(), _decision()),
        disposition_for_row(
            _row(row_id="row-2"),
            disposition=DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
            reason_code="HIERARCHY_RESOURCE_DETAIL_POLICY",
            row_role="resource_detail",
        ),
        disposition_for_decision(
            _row(row_id="row-3"), _decision(row_id="row-3", category=None)
        ),
    ]

    summary = funnel_summary(records, extracted_row_count=3)

    assert summary["terminal_dispositions"] == summary["extracted_rows"] == 3
    assert summary["unclassified_count"] == 1
    assert summary["disposition_counts"]["UNCLASSIFIED"] == 1
    assert summary["strict_blockers"] == []


def test_anomalous_exclusions_and_unknown_roles_are_strict_blockers() -> None:
    records = [
        disposition_for_row(
            _row(row_id=f"row-{index}"),
            disposition=DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
            reason_code="HIERARCHY_AGGREGATE_POLICY",
            row_role="aggregate",
        )
        for index in range(3)
    ]
    records.append(
        disposition_for_row(
            _row(row_id="unknown", work_name_raw=None, unit_raw=None, position_code_raw=None),
            disposition="UNCLASSIFIED",
            reason_code="NO_MATCHING_CATEGORY",
            row_role="unknown",
        )
    )

    summary = funnel_summary(records, extracted_row_count=5)

    assert "FUNNEL_CONSERVATION_FAILED" in summary["strict_blockers"]
    assert "FUNNEL_UNKNOWN_ROLE_POLICY" in summary["strict_blockers"]
    assert "FUNNEL_ANOMALOUS_EXCLUSION_SHARE" in summary["strict_blockers"]

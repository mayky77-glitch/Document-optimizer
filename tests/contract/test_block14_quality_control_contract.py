"""Frozen public contract for QualityControlEngine-14.0."""

from dataclasses import fields
from typing import get_type_hints

from report_processor.quality_control import (
    QUALITY_CONTROL_CONTRACT_VERSION,
    QUALITY_CONTROL_ENGINE_VERSION,
    QualityControlInputError,
    QualityControlReport,
    QualityControlSummary,
    QualityIssue,
    QualityIssueCode,
    QualityIssueSeverity,
    QualityLocation,
    WriteDecision,
    evaluate_quality_control,
)


def test_public_versions_enums_exports_and_report_shapes_are_frozen() -> None:
    assert QUALITY_CONTROL_CONTRACT_VERSION == "QualityControlContract-14.0"
    assert QUALITY_CONTROL_ENGINE_VERSION == "QualityControlEngine-14.0"
    assert tuple(item.value for item in WriteDecision) == (
        "allow_write",
        "allow_write_with_warnings",
        "require_manual_review",
        "block_write",
    )
    assert tuple(item.value for item in QualityIssueSeverity) == (
        "warning",
        "manual_review",
        "blocking",
    )
    assert tuple(item.value for item in QualityIssueCode) == (
        "INPUT_EMPTY",
        "DUPLICATE_IDENTITY",
        "CARDINALITY_MISMATCH",
        "IDENTITY_MISMATCH",
        "MISSING_REQUIRED_VALUE",
        "TARGET_NOT_WRITABLE",
        "FORMULA_WITHOUT_CACHE",
        "UNTRUSTED_FORMULA_CACHE",
        "EXCEL_ERROR",
        "VALUE_READ_FAILED",
        "MISSING_PROVENANCE",
        "PROVENANCE_CONFLICT",
        "TOTAL_DISCREPANCY",
        "TRACE_MISMATCH",
        "FORMULA_MISMATCH",
        "NO_VALUES",
        "UNMATCHED",
        "AMBIGUOUS",
        "MISSING_WORK_NAME",
        "MISSING_UNIT",
        "UNIT_CONFLICT",
        "TOLERANCE_EXCEEDED",
        "SOURCE_ROW_REUSED",
        "QUANTITY_COST_INCONSISTENT",
        "SIGN_CONFLICT",
        "NEGATIVE_VALUE",
        "UPSTREAM_WARNING",
    )
    assert callable(evaluate_quality_control)
    assert issubclass(QualityControlInputError, ValueError)
    assert tuple(item.name for item in fields(QualityLocation)) == (
        "source_kind",
        "source_id",
        "sheet_name",
        "row_number",
        "coordinate",
    )
    assert tuple(item.name for item in fields(QualityIssue)) == (
        "issue_id",
        "code",
        "severity",
        "message",
        "target_row_id",
        "match_result_id",
        "calculation_id",
        "source_row_ids",
        "locations",
        "evidence",
    )
    assert tuple(item.name for item in fields(QualityControlSummary)) == (
        "match_count",
        "calculation_count",
        "matched_count",
        "ambiguous_count",
        "unmatched_count",
        "calculated_count",
        "warning_issue_count",
        "manual_review_issue_count",
        "blocking_issue_count",
    )
    assert tuple(item.name for item in fields(QualityControlReport)) == (
        "report_id",
        "input_digest",
        "rule_set_hash",
        "decision",
        "issues",
        "summary",
        "match_result_ids",
        "calculation_ids",
        "contract_version",
    )
    assert fields(QualityControlReport)[-1].init is False
    assert get_type_hints(QualityIssue)["code"] is QualityIssueCode

"""Unit evidence for immutable, non-sensitive Block 14 models."""

from dataclasses import fields

import pytest
from report_processor.quality_control import (
    QualityControlReport,
    QualityControlSummary,
    QualityDecision,
    QualityIssue,
    QualityLocation,
    QualitySeverity,
)


def test_quality_models_are_frozen_and_issue_evidence_is_immutable() -> None:
    location = QualityLocation("target", "target", "Table 2", 8, "H8")
    issue = QualityIssue(
        "issue",
        "UPSTREAM_WARNING",
        QualitySeverity.WARNING,
        "safe",
        "target",
        "match",
        "calc",
        ("source-b", "source-a", "source-a"),
        (location,),
        {"code": "SOURCE_WARNING"},
    )
    assert issue.source_row_ids == ("source-a", "source-b")
    assert dict(issue.evidence) == {"code": "SOURCE_WARNING"}
    with pytest.raises((AttributeError, TypeError)):
        issue.evidence["raw_formula"] = "=SECRET()"  # type: ignore[index]
    assert fields(QualityControlReport)[-1].name == "contract_version"
    assert fields(QualityControlReport)[-1].init is False


def test_report_canonicalizes_identity_order_without_dropping_multiplicity() -> None:
    summary = QualityControlSummary(2, 2, 2, 0, 0, 2, 0, 0, 0)
    report = QualityControlReport(
        "report",
        "digest",
        "rules",
        QualityDecision.ALLOW_WRITE,
        (),
        summary,
        ("match-b", "match-a", "match-a"),
        ("calc-b", "calc-a", "calc-a"),
    )
    assert report.match_result_ids == ("match-a", "match-a", "match-b")
    assert report.calculation_ids == ("calc-a", "calc-a", "calc-b")

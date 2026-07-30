from __future__ import annotations

from decimal import Decimal

from report_processor.analytics import AnalyticalRuleSet, AnalyticalSourceRow, AnalyticalTargetRow


def source_row(
    source_row_id: str = "source-a:0001",
    *,
    line_id: str = "shared-line",
    quantity: Decimal = Decimal("1.250000000000000000"),
    status: str = "WARNING",
    warnings: tuple[str, ...] = ("SOURCE_WARNING",),
) -> AnalyticalSourceRow:
    return AnalyticalSourceRow(
        source_row_id=source_row_id,
        source_file_id="source-a",
        source_filename="source-a.xlsx",
        source_sheet="Sheet 1",
        source_row=17,
        line_id=line_id,
        document_type="ks2",
        document_period="2026-07",
        object_code="0007",
        subobject_code="0003",
        position_code="000042",
        cost_type_code="SMR",
        drawing_code="D-007",
        basis_code="GESN-01",
        work_name_raw="Pipe installation",
        work_name_normalized="pipe installation",
        unit_raw="m",
        unit_normalized="m",
        contract_quantity=quantity,
        period_quantity=Decimal("2.500000000000000000"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=Decimal("10.000000000000000000"),
        contract_cost=None,
        period_cost=Decimal("25.000000000000000000"),
        cumulative_cost=None,
        total_cost=Decimal("25.000000000000000000"),
        is_detail=True,
        is_total=False,
        is_outdated=False,
        classification="source_detail",
        status=status,
        warnings=warnings,
    )


def target_row(
    target_row_id: str = "target-a:0001",
    *,
    source_id: str = "target-a",
    fingerprint: str = "a" * 64,
    line_id: str = "target-line",
    quantity: Decimal = Decimal("3.000000000000000000"),
    status: str = "OK",
    warnings: tuple[str, ...] = (),
) -> AnalyticalTargetRow:
    return AnalyticalTargetRow(
        target_row_id=target_row_id,
        target_source_id=source_id,
        target_source_fingerprint=fingerprint,
        source_filename="target-a.xlsx",
        source_sheet="Target",
        source_row=8,
        line_id=line_id,
        document_type="ks6a",
        document_period="2026-07",
        object_code="0007",
        position_code="000042",
        work_name_raw="Pipe installation",
        unit_raw="m",
        quantity=quantity,
        classification="target_detail",
        status=status,
        warnings=warnings,
    )


def rule_set(
    content_hash: str = "b" * 64,
    *,
    clauses: tuple[tuple[str, str, str], ...] = (("field", "equals", "value"),),
) -> AnalyticalRuleSet:
    return AnalyticalRuleSet(
        content_hash=content_hash,
        source_name="synthetic-rules",
        source_format="json",
        version="1",
        clauses=clauses,
        status="OK",
        warnings=("RULE_WARNING",),
    )

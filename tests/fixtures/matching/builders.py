"""Small immutable source, target, and rule builders for matching tests."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from report_processor.business_rules.models import (
    BusinessRule,
    CostPolicy,
    QuantityPolicy,
    RuleAction,
    RuleClause,
    RuleConfigurationVersion,
    RuleDefaults,
    RuleMatchKind,
    RuleScope,
    ValidatedRuleSet,
)
from report_processor.normalization import normalize_training_rows
from report_processor.schema import SheetType
from report_processor.target_report.models import TargetNumericCell, TargetReportRow
from report_processor.training_data import DataQualityStatus, FormulaErrorCode, TrainingDataRow


def source_row(
    source_row_id: str = "source-a:17",
    *,
    document_index: str | None = "0784-01",
    object_code: str | None = "0007",
    subobject_code: str | None = "0003",
    position_code: str | None = "000042",
    work_name: str | None = "pipe installation",
    unit: str | None = "m",
) -> object:
    """Build a normalized source without changing source money values."""

    row = TrainingDataRow(
        document_type="ks2",
        document_period="2026-07",
        source_file_id="source-a",
        source_filename="source-a.xlsx",
        source_sheet="KS-2",
        source_row=17,
        source_row_id=source_row_id,
        object_code=object_code,
        subobject_code=subobject_code,
        position_code=position_code,
        cost_type_code="SMR",
        drawing_code=document_index,
        basis_code="GESN-01",
        work_name_raw=work_name,
        work_name_normalized=work_name,
        unit_raw=unit,
        unit_normalized=unit,
        contract_quantity=Decimal("11.000000000000000000"),
        period_quantity=Decimal("2.500000000000000000"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=Decimal("10.000000000000000000"),
        contract_cost=Decimal("110.000000000000000000"),
        period_cost=Decimal("25.000000000000000000"),
        cumulative_cost=None,
        total_cost=Decimal("110.000000000000000000"),
        is_detail=True,
        is_total=False,
        is_outdated=False,
        formula_error=FormulaErrorCode.NONE,
        data_quality_status=DataQualityStatus.OK,
        line_id=f"line-{source_row_id}",
        warnings=("SOURCE_WARNING",),
    )
    return normalize_training_rows((row,)).rows[0]


def target_row(
    row_number: int = 8,
    *,
    document_index: str | None = "0784-01",
    object_code: str | None = "0007",
    subobject_code: str | None = "0003",
    position_code: str | None = "000042",
    work_name: str | None = "pipe installation",
    unit: str | None = "m",
    stage: str | None = "stage-1",
) -> TargetReportRow:
    """Build one target Table 2 row, retaining input Decimal fields as evidence."""

    numeric = TargetNumericCell(Decimal("3.000000000000000000"), "3", "VALUE", "OK")
    return TargetReportRow(
        schema_version="TargetReport-9.0",
        sheet_name="Table 2",
        sheet_type=SheetType.KS6A,
        row_number=row_number,
        object_code=object_code,
        object_name="Object",
        position_code=position_code,
        work_name=work_name,
        cells=(),
        status="OK",
        warnings=("TARGET_WARNING",),
        row_kind="DETAIL",
        scope="OBJECT",
        document_index_raw=document_index,
        document_index_normalized=document_index,
        stage=stage,
        subobject_code=subobject_code,
        subobject_name="Subobject",
        unit=unit,
        document_quantity=numeric,
        selected_quantity=numeric,
        document_cost=numeric,
        selected_cost=numeric,
        writable=True,
    )


def rule_set(
    *,
    action: RuleAction = RuleAction.INCLUDE,
    match_kind: RuleMatchKind = RuleMatchKind.EXACT,
    literal: str = "pipe installation",
    scope: RuleScope | None = None,
) -> ValidatedRuleSet:
    """Build one approved data-only rule with a deterministic content hash."""

    defaults = RuleDefaults(
        source_priority=("ks6a",),
        allowed_units=("m",),
        default_run_coefficient=Decimal("1.0"),
        rounding_quantum=Decimal("0.01"),
        rounding_mode="ROUND_HALF_UP",
        cost_tolerance_ratio=Decimal("0"),
        quantity_policy=QuantityPolicy.TARGET_UNIT_OR_SINGLE_ALTERNATIVE,
        cost_policy=CostPolicy.ALL_APPROVED_ROWS,
    )
    rule = BusinessRule(
        rule_id="M12",
        rule_version="1",
        scope=scope or RuleScope(),
        clauses=(RuleClause(action=action, match_kind=match_kind, literal=literal),),
        priority=10,
        evidence=("synthetic",),
    )
    canonical_json = b'{"rule":"M12","version":"1"}'
    return ValidatedRuleSet(
        configuration_version=RuleConfigurationVersion(),
        rule_set_version="ValidatedRuleSet-10.0",
        defaults=defaults,
        rules=(rule,),
        canonical_json=canonical_json,
        content_hash=hashlib.sha256(canonical_json).hexdigest(),
    )

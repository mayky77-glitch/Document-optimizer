"""Synthetic Block 8/9/10 objects for analytics tests."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from report_processor.business_rules import load_rule_configuration
from report_processor.normalization import normalize_training_rows
from report_processor.schema import SheetType
from report_processor.target_report.models import TargetNumericCell, TargetReportRow
from report_processor.training_data import DataQualityStatus, FormulaErrorCode, TrainingDataRow


def normalized_source_row(
    source_row_id: str = "source-a:17", *, quantity: Decimal = Decimal("1.250000000000000000")
):
    row = TrainingDataRow(
        document_type="ks2",
        document_period="2026-07",
        source_file_id="source-a",
        source_filename="source-a.xlsx",
        source_sheet="Sheet 1",
        source_row=17,
        source_row_id=source_row_id,
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
        formula_error=FormulaErrorCode.NONE,
        data_quality_status=DataQualityStatus.WARNING,
        line_id="legacy-line",
        warnings=("SOURCE_WARNING",),
    )
    return normalize_training_rows((row,)).rows[0]


def target_report_row(row_number: int = 8) -> TargetReportRow:
    numeric = TargetNumericCell(Decimal("3.000000000000000000"), "3", "VALUE", "OK")
    return TargetReportRow(
        schema_version="TargetReport-9.0",
        sheet_name="Target",
        sheet_type=SheetType.KS6A,
        row_number=row_number,
        object_code="0007",
        object_name="Object",
        position_code="000042",
        work_name="Pipe installation",
        cells=(),
        status="WARNING",
        warnings=("TARGET_WARNING",),
        row_kind="DETAIL",
        scope="OBJECT",
        stage="stage-1",
        subobject_code="0003",
        subobject_name="Subobject",
        unit="m",
        document_quantity=numeric,
        selected_quantity=numeric,
        document_cost=numeric,
        selected_cost=numeric,
        writable=True,
    )


def validated_rule_set():
    path = Path(__file__).parents[1] / "business_rules" / "default_rules.json"
    result = load_rule_configuration(path)
    assert result.valid and result.rule_set is not None
    return result.rule_set

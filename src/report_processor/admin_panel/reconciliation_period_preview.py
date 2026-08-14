"""Read-only reconciliation target projection for a requested reporting period."""

from dataclasses import replace
from pathlib import Path

from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
from report_processor.excel_writer import build_period_insertion_plan
from report_processor.processing.adapters import _materialized
from report_processor.schema import analyze_workbook_schema
from report_processor.target_report import TargetReportReadRequest
from report_processor.target_report.ooxml import read_sheet_structure

from .reconciliation_period import ReportingPeriod
from .reconciliation_target import (
    ReconciliationTargetIdentity,
    ReconciliationTargetPreview,
    _base_roles,
    _bindings,
    _enumerate_stages,
    _first_detail_rows,
    _preview_bindings,
    _preview_rows,
    _rows,
    _session_snapshots,
    _sha256,
    _validate_reconciliation_target_type,
    resolve_reconciliation_stage,
)
from .reconciliation_target_measure import (
    ReconciliationTargetMeasureError,
    discover_target_measures,
)


def preview_reconciliation_target(path, digest: str, stage: str | None, period):
    """Build one read-only historical-period projection without transforming target bytes."""

    _validate_reconciliation_target_type(Path(path))
    source_path = Path(path)
    if _sha256(source_path) != digest:
        raise ValueError("RECONCILIATION_TARGET_CHANGED")
    source = _materialized(source_path, f"target:{digest}")
    with open_dual_workbook(WorkbookOpenRequest(source)) as session:
        generic = __import__("report_processor.target_report", fromlist=["read_target_report"])
        workbook_schema = analyze_workbook_schema(session)
        roles = _base_roles(workbook_schema)
        formula_snapshots, value_snapshots = _session_snapshots(session, roles)
        selected_stage = resolve_reconciliation_stage(
            _enumerate_stages(session.formula_workbook, roles, formula_snapshots), stage
        )
        detail_rows = _first_detail_rows(
            session.formula_workbook, selected_stage, roles, formula_snapshots
        )
        if not detail_rows:
            raise ValueError("RECONCILIATION_TARGET_STAGE_EMPTY")
        merged_ranges = {
            sheet_name: read_sheet_structure(session.source.local_path, sheet_name).merged_ranges
            for sheet_name in detail_rows
        }
        try:
            measure_pairs = discover_target_measures(
                session.formula_workbook, detail_rows, merged_ranges
            )
        except ReconciliationTargetMeasureError as error:
            if str(error) != "TARGET_CURRENT_PERIOD_PAIR_MISSING":
                raise
            reporting_period = (
                period if isinstance(period, ReportingPeriod) else ReportingPeriod.parse(period)
            )
            plan = build_period_insertion_plan(
                source_path, reporting_period, detail_rows, merged_ranges
            )
            if plan.source_sha256 != digest:
                raise ValueError("RECONCILIATION_TARGET_CHANGED") from None
            if plan.idempotent or not plan.anchors:
                raise ValueError("RECONCILIATION_TARGET_PREVIEW_INVALID") from None
            report = generic.read_target_report(
                session, workbook_schema, TargetReportReadRequest(selected_stage=selected_stage)
            )
            rows = tuple(
                _preview_rows(
                    session, selected_stage, plan, roles, formula_snapshots, value_snapshots
                )
            )
            schema = replace(report.schema, column_bindings=_preview_bindings(roles, plan))
            identity = ReconciliationTargetIdentity(
                digest, selected_stage, reporting_period, plan.plan_digest
            )
            if _sha256(source_path) != digest:
                raise ValueError("RECONCILIATION_TARGET_CHANGED") from None
            return ReconciliationTargetPreview(schema, rows, reporting_period, plan, identity)
        report = generic.read_target_report(
            session, workbook_schema, TargetReportReadRequest(selected_stage=selected_stage)
        )
        rows = tuple(
            _rows(session, selected_stage, measure_pairs, roles, formula_snapshots, value_snapshots)
        )
        schema = replace(report.schema, column_bindings=_bindings(roles, measure_pairs))
        identity = ReconciliationTargetIdentity(digest, selected_stage)
        if _sha256(source_path) != digest:
            raise ValueError("RECONCILIATION_TARGET_CHANGED")
        return ReconciliationTargetPreview(schema, rows, None, None, identity)


__all__ = ("ReconciliationTargetPreview", "preview_reconciliation_target")

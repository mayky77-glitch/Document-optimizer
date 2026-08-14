"""Read-only reconciliation target projection for a requested reporting period."""

from pathlib import Path

from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
from report_processor.excel_writer import build_period_insertion_plan
from report_processor.processing.adapters import _materialized
from report_processor.schema import analyze_workbook_schema
from report_processor.target_report import TargetPeriodIdentity, TargetReportReadRequest

from .reconciliation_period import ReportingPeriod
from .reconciliation_target import (
    ReconciliationTargetIdentity,
    ReconciliationTargetPreview,
    _base_roles,
    _bindings,
    _current_pair_period_identity,
    _enumerate_stages,
    _first_detail_rows,
    _preview_bindings,
    _preview_rows,
    _reconciliation_metadata_schema,
    _reconciliation_schema,
    _request_snapshots,
    _rows,
    _session_snapshots,
    _sha256,
    _snapshot_session,
    _validate_reconciliation_target_type,
    resolve_reconciliation_stage,
)
from .reconciliation_target_measure import (
    ReconciliationTargetMeasureError,
    discover_target_measures,
    raw_worksheet_merge_ranges,
)


def preview_reconciliation_target(path, digest: str, stage: str | None, period):
    """Build one read-only historical-period projection without transforming target bytes."""

    _validate_reconciliation_target_type(Path(path))
    source_path = Path(path)
    if _sha256(source_path) != digest:
        raise ValueError("RECONCILIATION_TARGET_CHANGED")
    source = _materialized(source_path, f"target:{digest}")
    with open_dual_workbook(WorkbookOpenRequest(source)) as session:
        formula_all, value_all = _request_snapshots(session)
        adapted = _snapshot_session(session, formula_all, value_all)
        generic = __import__("report_processor.target_report", fromlist=["read_target_report"])
        workbook_schema = analyze_workbook_schema(adapted)
        roles = _base_roles(workbook_schema)
        metadata_schema = _reconciliation_metadata_schema(workbook_schema, roles)
        formula_snapshots, value_snapshots = _session_snapshots(adapted, roles)
        selected_stage = resolve_reconciliation_stage(
            _enumerate_stages(adapted.formula_workbook, roles, formula_snapshots), stage
        )
        detail_rows = _first_detail_rows(
            adapted.formula_workbook, selected_stage, roles, formula_snapshots
        )
        if not detail_rows:
            raise ValueError("RECONCILIATION_TARGET_STAGE_EMPTY")
        merged_ranges = {
            sheet_name: raw_worksheet_merge_ranges(session.source.local_path, sheet_name)
            for sheet_name in detail_rows
        }
        try:
            measure_pairs = discover_target_measures(
                adapted.formula_workbook,
                detail_rows,
                merged_ranges,
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
                adapted,
                metadata_schema,
                TargetReportReadRequest(selected_stage=selected_stage, max_rows=0),
            )
            rows = tuple(
                _preview_rows(
                    adapted, selected_stage, plan, roles, formula_snapshots, value_snapshots
                )
            )
            schema = _reconciliation_schema(
                report.schema,
                adapted,
                roles,
                _preview_bindings(roles, plan),
                rows,
                period_identity=TargetPeriodIdentity(
                    current_period=reporting_period.value,
                    status="OK",
                ),
                pair_cardinality=len(plan.anchors),
            )
            identity = ReconciliationTargetIdentity(
                digest, selected_stage, reporting_period, plan.plan_digest
            )
            if _sha256(source_path) != digest:
                raise ValueError("RECONCILIATION_TARGET_CHANGED") from None
            return ReconciliationTargetPreview(schema, rows, reporting_period, plan, identity)
        report = generic.read_target_report(
            adapted,
            metadata_schema,
            TargetReportReadRequest(selected_stage=selected_stage, max_rows=0),
        )
        rows = tuple(
            _rows(adapted, selected_stage, measure_pairs, roles, formula_snapshots, value_snapshots)
        )
        schema = _reconciliation_schema(
            report.schema,
            adapted,
            roles,
            _bindings(roles, measure_pairs),
            rows,
            period_identity=_current_pair_period_identity(measure_pairs),
            pair_cardinality=len(measure_pairs),
        )
        identity = ReconciliationTargetIdentity(digest, selected_stage)
        if _sha256(source_path) != digest:
            raise ValueError("RECONCILIATION_TARGET_CHANGED")
        return ReconciliationTargetPreview(schema, rows, None, None, identity)


__all__ = ("ReconciliationTargetPreview", "preview_reconciliation_target")

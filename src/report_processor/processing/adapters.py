"""Narrow adapter boundary between Block 17 and the existing Blocks 1--16."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from .contracts import ProcessMode


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """Data returned by one upstream stage without prescribing its domain model."""

    artifacts: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    decision: str | None = None


class ProcessingAdapters(Protocol):
    """Adapters call established public APIs; the controller owns no stage logic."""

    def inspect(self, context: ProcessingContext) -> StageOutcome: ...

    def calculate(self, context: ProcessingContext) -> StageOutcome: ...

    def audit(self, context: ProcessingContext) -> StageOutcome: ...

    def write(self, context: ProcessingContext) -> StageOutcome: ...


@dataclass(slots=True)
class ProcessingContext:
    mode: ProcessMode
    strict: bool
    run_key: str
    temporary_directory: object
    values: dict[str, object] = field(default_factory=dict)


class DefaultProcessingAdapters:
    """Minimal concrete bridge to existing public APIs.

    Domain-specific selections and rules are deliberately passed by the caller's
    integration adapter; this class keeps the public default safe and read-only.
    """

    def inspect(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
        from report_processor.extraction import extract_supported_workbook_rows
        from report_processor.schema import analyze_workbook_schema
        from report_processor.target_report import TargetReportReadRequest, read_target_report
        from report_processor.training_data import prepare_training_data

        request = _request(context)
        source_id = f"source:{context.values['source_sha256']}"
        target_id = f"target:{context.values['target_sha256']}"
        source = _materialized(request.source_path, source_id)
        target = _materialized(request.target_path, target_id)
        with open_dual_workbook(WorkbookOpenRequest(source)) as session:
            source_schema = analyze_workbook_schema(session)
            extracted = extract_supported_workbook_rows(
                session,
                source_schema,
                document_index=request.options.get("document_index"),
                document_period=request.month,
            )
        with open_dual_workbook(WorkbookOpenRequest(target)) as session:
            target_schema = analyze_workbook_schema(session)
            target_report = read_target_report(session, target_schema, TargetReportReadRequest())
        source_rows = tuple(row for result in extracted for row in result.rows)
        training = prepare_training_data(source_rows)
        return StageOutcome(
            artifacts={
                "source_schema": source_schema,
                "target_report": target_report,
                "training": training,
                "target_source": target,
            },
        )

    def calculate(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.business_rules import load_default_rule_set, load_rule_configuration
        from report_processor.calculation import calculate_matches
        from report_processor.matching import match_rows
        from report_processor.normalization import normalize_training_rows

        request = _request(context)
        validation = (
            load_rule_configuration(request.rules_path)
            if request.rules_path is not None
            else load_default_rule_set()
        )
        if not validation.valid or validation.rule_set is None:
            raise ValueError("RULE_CONFIGURATION_INVALID")
        target_report = context.values["target_report"]
        normalized = normalize_training_rows(context.values["training"].rows)
        matches = match_rows(
            normalized.rows,
            target_report.rows,
            validation.rule_set,
            target_source_id=target_report.schema.source_file_id,
            target_fingerprint=target_report.schema.source_fingerprint.value,
        )
        calculations = calculate_matches(matches, validation.rule_set)
        return StageOutcome(
            artifacts={
                "rule_set": validation.rule_set,
                "normalized": normalized,
                "matches": matches,
                "calculations": calculations,
            },
            warnings=normalized.warnings,
        )

    def audit(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.quality_control import evaluate_quality_control

        report = evaluate_quality_control(
            context.values["matches"], context.values["calculations"], context.values["rule_set"]
        )
        return StageOutcome(
            artifacts={"quality_report": report, "audit_boundary": "DATA_COMMITTED"},
            warnings=tuple(issue.code.value for issue in report.issues),
            decision=report.decision.value,
        )

    def write(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.excel_writer import write_target_report

        request = _request(context)
        report = context.values["quality_report"]
        target_report = context.values["target_report"]
        written = write_target_report(
            request.target_path,
            request.output_path,
            report.decision,
            context.values["calculations"],
            target_report.schema,
        )
        return StageOutcome(
            artifacts={"write": written, "audit_boundary": "EXPORT_VERIFIED"},
            warnings=written.warnings,
            decision=report.decision.value,
        )


def _request(context: ProcessingContext):
    return context.values["request"]


def _materialized(path, source_id):
    from report_processor.materialization.models import MaterializedSource

    stat = path.stat()
    return MaterializedSource(
        local_path=path,
        original_file_id=source_id,
        original_relative_path=path.name,
        source_kind="file",
        archive_path=None,
        was_extracted=False,
        temporary=False,
        size_bytes=stat.st_size,
        extension=path.suffix.casefold(),
        cleanup_required=False,
        warnings=(),
    )

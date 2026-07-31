"""Narrow adapter boundary between Block 17 and the existing Blocks 1--16."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .contracts import ProcessMode

_UPSTREAM_CONTRACTS = {
    "manifest": "FileManifest-2.0",
    "manifest_enriched": "FileManifest-3.0",
    "extraction": "ExtractionResult-6.0",
    "training": "TrainingData-7.0",
    "normalization": "Normalization-8.0",
    "target": "TargetReport-9.0",
    "rules": "RuleConfigurationVersion-1.0",
    "analytics": "AnalyticalStore-11.0",
    "analytics_schema": "AnalyticalSchema-1",
    "matching": "MatchingContract-12.0",
    "calculation": "CalculationContract-13.0",
    "quality_control": "QualityControlContract-14.0",
    "writer": "ExcelWriterContract-15.1",
    "audit": "StageJournal-16.0",
    "stage_rag": "StageRelationRAG-18.0",
}


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

    def __init__(self, stage_encoder: object | None = None) -> None:
        self._stage_encoder = stage_encoder

    def inspect(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
        from report_processor.extraction import extract_supported_workbook_rows
        from report_processor.identifiers.manifest_enricher import (
            enrich_manifest_with_document_indexes,
        )
        from report_processor.inventory import build_file_manifest
        from report_processor.schema import analyze_workbook_schema
        from report_processor.selection.manifest_enricher import (
            enrich_manifest_with_document_metadata,
        )
        from report_processor.target_report import TargetReportReadRequest, read_target_report
        from report_processor.training_data import prepare_training_data

        request = _request(context)
        source_manifest = enrich_manifest_with_document_metadata(
            enrich_manifest_with_document_indexes(build_file_manifest(request.source_path))
        )
        target_manifest = enrich_manifest_with_document_metadata(
            enrich_manifest_with_document_indexes(build_file_manifest(request.target_path))
        )
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
                "source_manifest": source_manifest,
                "target_manifest": target_manifest,
                "source_selection": "EXPLICIT_SOURCE",
                "source_schema": source_schema,
                "target_report": target_report,
                "training": training,
                "hierarchy_issues": training.hierarchy_issues,
                "target_source": target,
            },
            warnings=training.warnings,
        )

    def calculate(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.analytics import AnalyticalStore
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
        analytics_path = Path(context.temporary_directory) / "analytics.duckdb"
        with AnalyticalStore(analytics_path) as store:
            source_load = store.load_source_rows(normalized.rows)
            target_load = store.load_target_rows(
                target_report.rows,
                target_source_id=target_report.schema.source_file_id,
                target_fingerprint=target_report.schema.source_fingerprint.value,
            )
            rule_load = store.load_rule_set(validation.rule_set)
        matches = match_rows(
            normalized.rows,
            target_report.rows,
            validation.rule_set,
            target_source_id=target_report.schema.source_file_id,
            target_fingerprint=target_report.schema.source_fingerprint.value,
        )
        calculations = calculate_matches(matches, validation.rule_set)
        rag_artifacts, rag_warnings = self._stage_relation_suggestions(
            request, normalized.rows, matches
        )
        return StageOutcome(
            artifacts={
                "rule_set": validation.rule_set,
                "normalized": normalized,
                "analytics_source_count": source_load.received_count,
                "analytics_target_count": target_load.received_count,
                "analytics_rule_count": rule_load.received_count,
                "matches": matches,
                "calculations": calculations,
                **rag_artifacts,
            },
            warnings=(*normalized.warnings, *rag_warnings),
        )

    def _stage_relation_suggestions(self, request, source_rows, matches):
        if request.options.get("stage_rag") is not True:
            return {}, ()

        from report_processor.matching import MatchStatus
        from report_processor.stage_rag import (
            RUBERT_TINY2_MODEL_ID,
            RUBERT_TINY2_MODEL_REVISION,
            RuBERTTiny2Encoder,
            StageRAGModelUnavailableError,
            StageText,
            retrieve_stage_relations,
        )

        sources = tuple(
            StageText(row.source_row_id, row.work_name)
            for row in source_rows
            if row.work_name and row.work_name.strip()
        )
        targets = tuple(
            StageText(
                match.result_id,
                match.target_row.stage or match.target_row.work_name,
            )
            for match in matches
            if match.status is not MatchStatus.MATCHED
            and (match.target_row.stage or match.target_row.work_name)
        )
        if not sources or not targets:
            return {
                "stage_rag_status": "NO_STAGE_TEXT",
                "stage_relation_suggestions": (),
            }, ()

        top_k = request.options.get("stage_rag_top_k", 3)
        if isinstance(top_k, bool) or not isinstance(top_k, int):
            raise ValueError("stage_rag_top_k должен быть целым")
        top_k = min(top_k, len(sources))
        encoder = self._stage_encoder or RuBERTTiny2Encoder()
        try:
            suggestions = retrieve_stage_relations(
                encoder,
                sources,
                targets,
                k=top_k,
            )
        except StageRAGModelUnavailableError:
            return {
                "stage_rag_status": "RAG_MODEL_UNAVAILABLE",
                "stage_rag_requires_manual_review": True,
            }, ("RAG_MODEL_UNAVAILABLE",)
        return {
            "stage_rag_status": "MANUAL_REVIEW_REQUIRED",
            "stage_rag_model_id": RUBERT_TINY2_MODEL_ID,
            "stage_rag_model_revision": RUBERT_TINY2_MODEL_REVISION,
            "stage_rag_requires_manual_review": True,
            "stage_relation_suggestions": suggestions,
        }, ("STAGE_RAG_MANUAL_REVIEW_REQUIRED",)

    def audit(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.audit import AuditJournal, AuditStage, AuditState, export_snapshot
        from report_processor.audit.serialization import event_payload
        from report_processor.quality_control import evaluate_quality_control

        request = _request(context)
        report = evaluate_quality_control(
            context.values["matches"], context.values["calculations"], context.values["rule_set"]
        )
        audit_directory = _audit_directory(context)
        with AuditJournal(audit_directory / "journal.sqlite3") as journal:
            run = journal.begin_run(
                (
                    str(context.values["source_sha256"]),
                    str(context.values["target_sha256"]),
                ),
                {
                    "boolean_flag": request.strict,
                    "controlled_stage_code": request.stage or "ALL",
                },
                _UPSTREAM_CONTRACTS,
                context.values["rule_set"].content_hash,
            )
            journal.append_event(run.run_id, AuditStage.RUN, AuditState.PENDING)
            journal.append_event(
                run.run_id,
                AuditStage.DATA,
                AuditState.DATA_COMMITTED,
                fields={
                    "artifact_sha256": report.input_digest,
                    "count": report.summary.calculation_count,
                },
            )
            export_hash = None
            if request.mode is ProcessMode.DRY_RUN:
                journal.append_event(
                    run.run_id,
                    AuditStage.EXPORT,
                    AuditState.EXPORT_PREPARED,
                    fields={"artifact_sha256": report.report_id},
                )
                export_hash = export_snapshot(
                    (event_payload(event) for event in journal.events(run.run_id)),
                    audit_directory / f"{run.run_id}.json",
                    "json",
                )
                journal.verify_export(
                    run.run_id,
                    snapshot_hash=export_hash,
                    published_hash=export_hash,
                )
                journal.record_cross_store_hashes(
                    run.run_id,
                    data_hash=report.input_digest,
                    export_hash=export_hash,
                )
            events = journal.validate_run(run.run_id)
        hierarchy_issues = tuple(context.values.get("hierarchy_issues", ()) or ())
        decision = (
            "require_manual_review"
            if context.values.get("stage_rag_requires_manual_review") is True or hierarchy_issues
            else report.decision.value
        )
        return StageOutcome(
            artifacts={
                "quality_report": report,
                "audit_run_id": run.run_id,
                "audit_boundary": events[-1].controlled_state_code,
                "audit_export_hash": export_hash or "",
            },
            warnings=tuple(issue.code.value for issue in report.issues)
            + tuple(issue.code for issue in hierarchy_issues),
            decision=decision,
        )

    def write(self, context: ProcessingContext) -> StageOutcome:
        from report_processor.audit import AuditJournal, AuditStage, AuditState, export_snapshot
        from report_processor.audit.serialization import event_payload
        from report_processor.excel_writer import write_target_report

        if context.values.get("hierarchy_issues"):
            raise RuntimeError("HIERARCHY_INTEGRITY_BLOCKED")
        request = _request(context)
        report = context.values["quality_report"]
        target_report = context.values["target_report"]
        with AuditJournal(_audit_directory(context) / "journal.sqlite3") as journal:
            run_id = context.values["audit_run_id"]
            journal.recover(run_id)
            journal.append_event(
                run_id,
                AuditStage.EXPORT,
                AuditState.EXPORT_PREPARED,
                fields={"artifact_sha256": report.report_id},
            )
            audit_export_hash = export_snapshot(
                (event_payload(event) for event in journal.events(run_id)),
                _audit_directory(context) / f"{run_id}.json",
                "json",
            )
            written = write_target_report(
                request.target_path,
                request.output_path,
                report.decision,
                context.values["calculations"],
                target_report.schema,
            )
            if written.output_sha256 is None:
                raise RuntimeError("WRITE_OUTPUT_NOT_VERIFIED")
            journal.verify_export(
                run_id,
                snapshot_hash=written.output_sha256,
                published_hash=written.output_sha256,
            )
            journal.record_cross_store_hashes(
                run_id,
                data_hash=report.input_digest,
                export_hash=written.output_sha256,
            )
            boundary = journal.validate_run(run_id)[-1].controlled_state_code
        return StageOutcome(
            artifacts={
                "write": written,
                "audit_run_id": run_id,
                "audit_boundary": boundary,
                "audit_export_hash": audit_export_hash,
            },
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


def _audit_directory(context: ProcessingContext) -> Path:
    request = _request(context)
    directory = request.audit_directory or Path(context.temporary_directory) / "audit"
    directory.mkdir(parents=True, exist_ok=True)
    return directory

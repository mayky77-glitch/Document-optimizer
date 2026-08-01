"""Private workbook adapters for one authoritative global reconciliation pass."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from report_processor.processing import execute_reconciliation
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewDecision,
    feedback_for_group,
    latest_feedback,
    normalize_name,
    normalize_unit,
)

from .reconciliation_state import ReconciliationReviewState


@dataclass(frozen=True, slots=True)
class ReconciliationReviewResult:
    state: ReconciliationReviewState


def prepare_review(job, feedback: tuple[FeedbackRecord, ...]) -> ReconciliationReviewResult:
    artifacts, categories = _run(job, ())
    feedback_decisions = _feedback_decisions(artifacts, feedback)
    if feedback_decisions:
        artifacts, categories = _run(job, feedback_decisions)
    state = ReconciliationReviewState(
        rows={row.row_id: row for row in artifacts.review_rows},
        groups={group.group_id: group for group in artifacts.review_groups},
        categories=categories,
        source_digests=job.source_digests,
        target_digest=job.target_digest,
    )
    for decision in feedback_decisions:
        if decision.group_id in state.groups:
            group = next(
                item for item in state.group_snapshot() if item.group_id == decision.group_id
            )
            state.put_group(
                decision.group_id,
                ReviewDecision(
                    action=decision.action,
                    mode=decision.mode,
                    target_category=decision.target_category,
                    group_id=decision.group_id,
                    version=group.version,
                ),
            )
    for decision in feedback_decisions:
        if decision.row_id in state.rows:
            group = next(
                item for item in state.group_snapshot() if decision.row_id in item.member_ids
            )
            state.put_row(
                decision.row_id,
                ReviewDecision(
                    action=decision.action,
                    mode=decision.mode,
                    target_category=decision.target_category,
                    row_id=decision.row_id,
                    version=group.version,
                ),
            )
    return ReconciliationReviewResult(state)


def apply_review(
    job, state: ReconciliationReviewState
) -> tuple[object, tuple[FeedbackRecord, ...]]:
    artifacts, _categories = _run(job, state.core_decisions(), write=True)
    output = job.directory / "result.xlsx"
    written = artifacts.write_result
    if written is None or not output.is_file() or getattr(written, "output_sha256", None) is None:
        raise RuntimeError("authoritative workbook write was not verified")
    records = _feedback_records(state)
    return output, records


def _run(job, decisions: tuple[ReviewDecision, ...], *, write: bool = False):
    from report_processor.business_rules import load_default_rule_set, load_rule_configuration
    from report_processor.excel_writer import write_target_report

    validation = (
        load_rule_configuration(job.rules_path)
        if getattr(job, "rules_path", None)
        else load_default_rule_set()
    )
    if not validation.valid or validation.rule_set is None:
        raise ValueError("RULE_CONFIGURATION_INVALID")
    adapter = _WorkbookAdapter(job)
    captured: dict[str, object] = {}

    def inspect(target: Path):
        report = adapter.target_report(target)
        captured["schema"] = report.schema
        return report.rows

    def write_once(target: Path, calculations):
        schema = captured.get("schema")
        if schema is None:
            raise RuntimeError("target schema missing")
        from report_processor.quality_control import WriteDecision

        return write_target_report(
            target,
            job.directory / "result.xlsx",
            WriteDecision.ALLOW_WRITE,
            calculations,
            schema,
        )

    artifacts = execute_reconciliation(
        tuple(job.sources or (job.source,)),
        job.target,
        validation.rule_set,
        inspect_target=inspect,
        normalize_source=adapter.normalized_rows,
        target_source_id=f"target:{job.target_digest}",
        target_fingerprint=f"sha256:{job.target_digest}",
        decisions=decisions,
        write=write_once if write else None,
    )
    categories = {
        match.target_row_id: (
            match.target_row.stage or match.target_row.work_name or "Целевая строка"
        )
        for match in artifacts.matches
    }
    return artifacts, categories


class _WorkbookAdapter:
    def __init__(self, job) -> None:
        self.job = job

    def target_report(self, path: Path):
        from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
        from report_processor.processing.adapters import _materialized
        from report_processor.schema import analyze_workbook_schema
        from report_processor.target_report import TargetReportReadRequest, read_target_report

        source = _materialized(path, f"target:{self.job.target_digest}")
        with open_dual_workbook(WorkbookOpenRequest(source)) as session:
            return read_target_report(
                session,
                analyze_workbook_schema(session),
                TargetReportReadRequest(selected_stage=self.job.stage),
            )

    def normalized_rows(self, path: Path):
        from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
        from report_processor.extraction import extract_supported_workbook_rows
        from report_processor.normalization import normalize_training_rows
        from report_processor.processing.adapters import _materialized
        from report_processor.schema import analyze_workbook_schema
        from report_processor.training_data import prepare_training_data

        source = _materialized(path, _source_identity(self.job, path))
        with open_dual_workbook(WorkbookOpenRequest(source)) as session:
            extracted = extract_supported_workbook_rows(session, analyze_workbook_schema(session))
        training = prepare_training_data(tuple(row for result in extracted for row in result.rows))
        return normalize_training_rows(training.rows).rows


def _source_identity(job, path: Path) -> str:
    index = (job.sources or (job.source,)).index(path)
    return f"source:{index}:{job.source_digests[index]}"


def _feedback_decisions(
    artifacts, feedback: tuple[FeedbackRecord, ...]
) -> tuple[ReviewDecision, ...]:
    rows = {row.row_id: row for row in artifacts.review_rows}
    records = latest_feedback(feedback)
    decisions: list[ReviewDecision] = []
    for group in artifacts.review_groups:
        if (record := feedback_for_group(group, feedback)) is not None:
            decisions.append(
                ReviewDecision(
                    action=record.action,
                    mode=record.mode,
                    target_category=record.target_category,
                    group_id=group.group_id,
                    version=group.version,
                )
            )
            continue
        for row_id in group.member_ids:
            row = rows[row_id]
            record = records.get((normalize_name(row.display_name), normalize_unit(row.unit)))
            if record is not None:
                decisions.append(
                    ReviewDecision(
                        action=record.action,
                        mode=record.mode,
                        target_category=record.target_category,
                        row_id=row_id,
                        version=group.version,
                    )
                )
    return tuple(decisions)


def _feedback_records(state: ReconciliationReviewState) -> tuple[FeedbackRecord, ...]:
    from report_processor.reconciliation_review import (
        feedback_from_decision,
        feedback_from_row_decision,
    )

    groups = {group.group_id: group for group in state.group_snapshot()}
    records = [
        feedback_from_decision(groups[group_id], decision, sequence=index)
        for index, (group_id, decision) in enumerate(sorted(state.group_decisions.items()), 1)
    ]
    records.extend(
        feedback_from_row_decision(state.rows[row_id], decision, sequence=index)
        for index, (row_id, decision) in enumerate(
            sorted(state.row_decisions.items()), len(records) + 1
        )
    )
    return tuple(records)

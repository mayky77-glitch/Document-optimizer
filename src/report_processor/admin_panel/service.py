"""Private job lifecycle and the public processing execution boundary."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import shutil
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from report_processor.domain.exceptions import ReportProcessorError

from .presentation import journal_payload, processing_presentation
from .reconciliation_execution import ReconciliationReviewResult, apply_review, prepare_review
from .reconciliation_feedback_store import ReconciliationFeedbackStore
from .reconciliation_state import ReconciliationReviewState
from .reconciliation_uploads import digest as _digest
from .reconciliation_uploads import (
    is_safe_stage_text,
    validate_mode,
    validate_stage,
    validate_workbook_upload,
    validated_sources,
)

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_SOURCES = 32
MAX_RETAINED_TERMINAL_JOBS = 64
MAX_MANUAL_DISCREPANCY_DECISIONS = 5_000
MAX_STAGE_OPTIONS = 64
LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AdminJob:
    job_id: str
    directory: Path
    source: Path
    target: Path
    stage: str
    mode: str
    source_digest: str
    target_digest: str
    operation: str = "reconcile"
    sources: tuple[Path, ...] = ()
    source_digests: tuple[str, ...] = ()
    source_names: tuple[str, ...] = ()
    target_name: str = ""
    source_issues: tuple[dict[str, object], ...] = ()
    status: str = "pending"
    output: Path | None = None
    summary: dict[str, object] = field(default_factory=dict)
    discrepancies: list[dict[str, object]] = field(default_factory=list)
    suggestions: list[dict[str, object]] = field(default_factory=list)
    decisions: list[dict[str, str]] = field(default_factory=list)
    errors: tuple[str, ...] = ()
    result_name: str | None = None
    review_state: ReconciliationReviewState | None = None
    verification_status: str | None = None
    verification_message: str | None = None
    checked_row_count: int = 0
    failed_row_count: int = 0

    @property
    def result_available(self) -> bool:
        return (
            self.output is not None
            and self.output.is_file()
            and not self.unresolved_suggestion_ids
            and not self.unresolved_manual_discrepancy_ids
            and self.status not in {"pending", "running", "failed"}
        )

    @property
    def unresolved_suggestion_ids(self) -> set[str]:
        decided = {item.get("suggestion_id") for item in self.decisions}
        return {
            str(item.get("suggestion_id"))
            for item in self.suggestions
            if item.get("requires_manual_review") is True
        } - decided

    @property
    def unresolved_manual_discrepancy_ids(self) -> set[str]:
        decided = {
            item.get("discrepancy_id")
            for item in self.decisions
            if item.get("decision") in {"approve", "reject"}
        }
        return {
            str(item.get("discrepancy_id"))
            for item in self.discrepancies
            if item.get("severity") == "manual_review"
            and isinstance(item.get("discrepancy_id"), str)
        } - decided


class AdminPanelService:
    """Own opaque job IDs and never exposes private workspace paths."""

    def __init__(
        self,
        workspace_root: Path,
        execute: Callable[[AdminJob], object] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.execute = execute
        self.jobs: dict[str, AdminJob] = {}
        self._reconciliation_locks: dict[str, threading.RLock] = {}
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)
        self.feedback_store = ReconciliationFeedbackStore(self.workspace_root)

    def create_job(
        self,
        *,
        source_name: str | None = None,
        source_content: bytes | None = None,
        sources: list[tuple[str, bytes]] | None = None,
        target_name: str,
        target_content: bytes,
        stage: str | None,
        mode: str = "write",
        operation: str = "reconcile",
        validate_target_stage: bool = False,
    ) -> AdminJob:
        upload_sources = validated_sources(sources, source_name, source_content)
        validate_workbook_upload(target_name, target_content)
        if (
            sum(len(content) for _name, content in upload_sources) + len(target_content)
            > MAX_UPLOAD_BYTES
        ):
            raise ValueError("combined upload is too large")
        clean_stage = validate_stage(stage) if stage is not None else None
        clean_mode = validate_mode(mode)
        clean_operation = validate_operation(operation)
        job_id = secrets.token_urlsafe(18)
        directory = self.workspace_root / job_id
        registered = False
        try:
            directory.mkdir(mode=0o700, parents=False, exist_ok=False)
            source_paths = tuple(
                directory / f"source-{index:02d}{Path(name).suffix.casefold()}"
                for index, (name, _content) in enumerate(upload_sources, 1)
            )
            target = directory / f"target{Path(target_name).suffix.casefold()}"
            for source, (_name, content) in zip(source_paths, upload_sources, strict=True):
                _private_write(source, content)
            _private_write(target, target_content)
            target_digest = _digest(target_content)
            selected_stage = (
                _resolve_target_stage(target, target_digest, clean_stage)
                if validate_target_stage or clean_stage is None
                else clean_stage
            )
            job = AdminJob(
                job_id=job_id,
                directory=directory,
                source=source_paths[0],
                target=target,
                stage=selected_stage,
                mode=clean_mode,
                source_digest=_digest(upload_sources[0][1]),
                target_digest=target_digest,
                sources=source_paths,
                source_digests=tuple(_digest(content) for _name, content in upload_sources),
                source_names=tuple(name for name, _content in upload_sources),
                target_name=target_name,
                operation=clean_operation,
            )
            self.jobs[job_id] = job
            registered = True
            result = self.run(job_id)
            self._prune_terminal_jobs()
            return result
        except (OSError, TypeError, ValueError, ReportProcessorError):
            if registered:
                self.jobs.pop(job_id, None)
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def run(self, job_id: str) -> AdminJob:
        job = self.get_job(job_id)
        if job.status not in {"pending", "failed"}:
            raise ValueError("job cannot be run from its current state")
        job.status = "running"
        try:
            if job.operation == "verify":
                from .reconciliation_verification import verify_reconciliation

                execution_result = verify_reconciliation(
                    job, self.feedback_store.records(job.target_digest)
                )
            else:
                execution_result = (
                    self.execute(job)
                    if self.execute is not None
                    else prepare_review(job, self.feedback_store.records(job.target_digest))
                )
            self._apply_execution_result(job, execution_result)
            _verify_inputs(job)
        except (OSError, TypeError, ValueError, RuntimeError) as error:
            _remove_partial_output(job)
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
            _verification_failure_issues(job, error)
        except Exception:
            LOGGER.exception("Unexpected admin-panel executor failure for job %s", job.job_id)
            _remove_partial_output(job)
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
        if job.status == "failed":
            shutil.rmtree(job.directory, ignore_errors=True)
        return job

    def get_job(self, job_id: str) -> AdminJob:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

    def get(self, job_id: str) -> AdminJob:
        """Backward-compatible alias for the frozen in-process service API."""

        return self.get_job(job_id)

    def put_reconciliation_group(self, job_id: str, group_id: str, decision) -> AdminJob:
        with self._reconciliation_lock(job_id):
            job = self._review_job(job_id)
            job.review_state.put_group(group_id, decision)
            return job

    def put_reconciliation_row(self, job_id: str, row_id: str, decision) -> AdminJob:
        with self._reconciliation_lock(job_id):
            job = self._review_job(job_id)
            job.review_state.put_row(row_id, decision)
            return job

    def delete_reconciliation_row(self, job_id: str, row_id: str, version: str) -> AdminJob:
        with self._reconciliation_lock(job_id):
            job = self._review_job(job_id)
            job.review_state.delete_row(row_id, version)
            return job

    def apply_reconciliation(self, job_id: str) -> AdminJob:
        with self._reconciliation_lock(job_id):
            job = self.get_job(job_id)
            if job.status == "ready":
                _verify_inputs(job)
                if not job.result_available:
                    raise ValueError("authoritative result is unavailable")
                return job
            job = self._review_job(job_id)
            if job.review_state.unresolved_row_ids():
                raise ValueError("authoritative review is incomplete")
            inputs = _capture_input_snapshot(job)
            decisions = tuple(job.review_state.core_decisions())
            job.status = "running"
            owned_output: tuple[int, int] | None = None
            try:
                applied = apply_review(job, job.review_state, decisions)
                output, feedback = applied
                owned_output, output_digest = _validate_owned_apply_output(job, output)
                apply_key = getattr(applied, "apply_key", None)
                plan_hash = getattr(applied, "payload_hash", None)
                if not isinstance(apply_key, str) or not isinstance(plan_hash, str):
                    plan_hash = _digest_apply_fallback(
                        job, job.review_state, feedback, output_digest
                    )
                    apply_key = _digest_apply_fallback(
                        job, job.review_state, feedback, output_digest, purpose="key"
                    )
                payload_hash = hashlib.sha256(
                    f"{plan_hash}:output-sha256:{output_digest}".encode()
                ).hexdigest()
                self.feedback_store.commit_apply(
                    target_digest=job.target_digest,
                    apply_key=apply_key,
                    payload_hash=payload_hash,
                    records=feedback,
                    precommit_validator=lambda: _verify_apply_artifacts(
                        job, inputs, output, owned_output
                    ),
                )
                # No fallible I/O after the SQLite commit point.
                job.output, job.result_name, job.status = output, "optimized-report.xlsx", "ready"
            except (OSError, TypeError, ValueError, RuntimeError):
                _remove_partial_output(job, owned_output)
                job.status, job.errors = "failed", ("PROCESSING_FAILED",)
                raise
            return job

    def _reconciliation_lock(self, job_id: str) -> threading.RLock:
        return self._reconciliation_locks.setdefault(job_id, threading.RLock())

    def _review_job(self, job_id: str) -> AdminJob:
        job = self.get_job(job_id)
        if job.review_state is None or job.status != "review_required":
            raise ValueError("authoritative review is unavailable")
        return job

    def record_decision(self, *, job_id: str, suggestion_id: str, decision: str) -> AdminJob:
        if decision not in {"fit", "not_fit"}:
            raise ValueError("decision must be fit or not_fit")
        job = self.get_job(job_id)
        available = {
            str(item.get("suggestion_id"))
            for item in job.suggestions
            if item.get("requires_manual_review") is True
        }
        if suggestion_id not in available:
            raise ValueError("unknown suggestion")
        if any(item.get("suggestion_id") == suggestion_id for item in job.decisions):
            raise ValueError("suggestion already decided")
        job.decisions.append(
            {
                "suggestion_id": suggestion_id,
                "decision": decision,
                "effect": "review_journal_only",
            }
        )
        self._complete_review_if_resolved(job)
        self._prune_terminal_jobs()
        return job

    def record_suggestion_group_decision(
        self,
        *,
        job_id: str,
        group_id: str,
        suggestion_id: str | None,
        decision: str,
    ) -> AdminJob:
        """Atomically resolve one currently presented semantic target group."""

        if decision not in {"apply", "reject"} or not isinstance(group_id, str) or not group_id:
            raise ValueError("invalid suggestion group decision")
        job = self.get_job(job_id)
        from .presentation import _controlled_id

        open_groups: dict[str, list[dict[str, object]]] = {}
        decided = {str(item.get("suggestion_id")) for item in job.decisions}
        for item in job.suggestions:
            target_ref = item.get("target_ref")
            item_id = item.get("suggestion_id")
            if (
                item.get("requires_manual_review") is True
                and isinstance(target_ref, str)
                and isinstance(item_id, str)
                and item_id not in decided
            ):
                open_groups.setdefault(
                    _controlled_id("suggestion-review-group", target_ref), []
                ).append(item)
        members = open_groups.get(group_id)
        if not members:
            raise ValueError("suggestion group is no longer open")
        member_ids = {str(item["suggestion_id"]) for item in members}
        if decision == "apply":
            if not isinstance(suggestion_id, str) or suggestion_id not in member_ids:
                raise ValueError("selected suggestion is not in the open group")
            entries = [
                {
                    "suggestion_id": item_id,
                    "decision": "fit" if item_id == suggestion_id else "not_fit",
                    "effect": "review_journal_only",
                }
                for item_id in sorted(member_ids)
            ]
        else:
            if suggestion_id is not None:
                raise ValueError("reject does not select a suggestion")
            entries = [
                {
                    "suggestion_id": item_id,
                    "decision": "not_fit",
                    "effect": "review_journal_only",
                }
                for item_id in sorted(member_ids)
            ]
        # All group and selected-member validation precedes this single mutation.
        job.decisions.extend(entries)
        self._complete_review_if_resolved(job)
        self._prune_terminal_jobs()
        return job

    def record_manual_discrepancy_decision(
        self,
        *,
        job_id: str,
        group_id: str,
        discrepancy_ids: list[str] | None,
        decision: str,
    ) -> AdminJob:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("group is required")
        if discrepancy_ids is not None and not isinstance(discrepancy_ids, list):
            raise ValueError("discrepancy IDs are required")
        if discrepancy_ids is not None and len(discrepancy_ids) > MAX_MANUAL_DISCREPANCY_DECISIONS:
            raise ValueError("too many discrepancy IDs")
        if discrepancy_ids is not None and any(
            not isinstance(item, str) or not item for item in discrepancy_ids
        ):
            raise ValueError("invalid discrepancy ID")
        if discrepancy_ids is not None and len(set(discrepancy_ids)) != len(discrepancy_ids):
            raise ValueError("duplicate discrepancy ID")
        job = self.get_job(job_id)
        from .presentation import manual_review_groups

        groups = manual_review_groups(job.discrepancies, job.decisions, include_ids=True)
        group = next((item for item in groups if item["group_id"] == group_id), None)
        expected_ids = group["discrepancy_ids"] if group is not None else []
        if group is None or (
            discrepancy_ids is not None and set(discrepancy_ids) != set(expected_ids)
        ):
            raise ValueError("decision must match one open group exactly")
        # All validation occurs before mutation so rejected requests remain atomic.
        job.decisions.extend(
            {
                "discrepancy_id": discrepancy_id,
                "decision": decision,
                "effect": "review_journal_only",
            }
            for discrepancy_id in expected_ids
        )
        self._complete_review_if_resolved(job)
        self._prune_terminal_jobs()
        return job

    @staticmethod
    def _complete_review_if_resolved(job: AdminJob) -> None:
        if job.unresolved_suggestion_ids or job.unresolved_manual_discrepancy_ids:
            return
        if job.output is None:
            job.output = job.directory / "review-journal.json"
            _private_write(job.output, journal_payload(job))
            job.result_name = "review-journal.json"
            job.status = "review_recorded"
        elif job.status == "review_required":
            job.status = "ready"

    def get_result(self, job_id: str) -> tuple[Path, str]:
        job = self.get_job(job_id)
        if not job.result_available or job.output is None or job.result_name is None:
            raise KeyError(job_id)
        return job.output, job.result_name

    def _prune_terminal_jobs(self) -> None:
        terminal = [
            job_id
            for job_id, job in self.jobs.items()
            if job.status in {"ready", "failed", "blocked", "review_recorded"}
        ]
        active_count = len(self.jobs) - len(terminal)
        terminal_limit = max(0, MAX_RETAINED_TERMINAL_JOBS - active_count)
        for job_id in terminal[:-terminal_limit] if terminal_limit else terminal:
            self.jobs.pop(job_id, None)

    def _apply_execution_result(self, job: AdminJob, result: object) -> None:
        from .reconciliation_verification import VerificationResult

        if isinstance(result, VerificationResult):
            _apply_verification_result(job, result)
            return
        if isinstance(result, ReconciliationReviewResult):
            job.review_state = result.state
            job.source_issues = tuple(
                {
                    "basename": item.safe_basename,
                    "comment": item.comment,
                    "repair_hint": item.repair_hint,
                    "can_continue": item.can_continue,
                }
                for item in result.source_issues
            )
            job.status = "failed" if result.state is None else "review_required"
            if result.target_error:
                job.source_issues = (
                    {
                        "basename": job.target_name,
                        "comment": "Не удалось прочитать структуру целевого отчёта.",
                        "repair_hint": "Проверьте шаблон отчёта и повторите загрузку.",
                        "can_continue": False,
                    },
                )
            job.summary = {}
            job.discrepancies = []
            job.suggestions = []
            return
        if result is None or isinstance(result, Path):
            job.output = result
            if (
                result is not None
                and result.is_file()
                and result.resolve().is_relative_to(job.directory.resolve())
            ):
                os.chmod(result, 0o600)
                job.result_name = "optimized-report.xlsx"
                job.status = "ready"
            else:
                job.output = None
                job.status = "failed"
                job.errors = ("PROCESSING_FAILED",)
            return

        summary, discrepancies, suggestions = processing_presentation(result)
        job.summary = summary
        job.discrepancies = discrepancies
        job.suggestions = suggestions
        job.errors = tuple(str(item)[:120] for item in getattr(result, "errors", ()) or ())
        output = job.directory / "result.xlsx"
        if output.is_file():
            os.chmod(output, 0o600)
            job.output = output
            job.result_name = "optimized-report.xlsx"

        exit_code = _exit_code(result)
        if exit_code in {0, 1}:
            job.status = "review_required" if _has_unresolved_reviews(job) else "ready"
        elif exit_code in {3, 4}:
            job.status = "review_required" if _has_unresolved_reviews(job) else "blocked"
        else:
            job.status = "failed"
            job.errors = job.errors or ("PROCESSING_FAILED",)
            _remove_partial_output(job)
            return
        if job.output is None and not _has_unresolved_reviews(job):
            job.output = job.directory / "review-journal.json"
            _private_write(job.output, journal_payload(job))
            job.result_name = "review-journal.json"


def _apply_verification_result(job: AdminJob, result) -> None:
    job.review_state = None
    job.summary = {}
    job.discrepancies = []
    job.suggestions = []
    job.decisions = []
    job.source_issues = ()
    job.verification_status = result.verification_status
    job.verification_message = result.message
    job.checked_row_count = result.checked_row_count
    job.failed_row_count = result.failed_row_count
    if result.output is None:
        job.output = None
        job.result_name = None
        job.status = "ready"
        return
    output = result.output
    if (
        not output.is_file()
        or output.is_symlink()
        or not output.resolve().is_relative_to(job.directory.resolve())
        or result.result_name is None
    ):
        raise RuntimeError("VERIFICATION_OUTPUT_INVALID")
    os.chmod(output, 0o600)
    job.output = output
    job.result_name = result.result_name
    job.status = "ready"


def _verification_failure_issues(job: AdminJob, error: Exception) -> None:
    if job.operation != "verify":
        return
    from .reconciliation_verification import VerificationTechnicalFailure

    if not isinstance(error, VerificationTechnicalFailure):
        return
    job.source_issues = tuple(error.issues)


def _has_unresolved_reviews(job: AdminJob) -> bool:
    return bool(job.unresolved_suggestion_ids or job.unresolved_manual_discrepancy_ids)


def _private_write(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)


def _default_execute(job: AdminJob) -> object:
    from report_processor.processing import ProcessMode, ProcessReportRequest
    from report_processor.workflow import process_report

    target = job.target
    result = None
    for index, source in enumerate(job.sources or (job.source,), 1):
        output = job.directory / (
            "result.xlsx"
            if index == len(job.sources or (job.source,))
            else f"result-{index:02d}.xlsx"
        )
        request = ProcessReportRequest(
            source_path=source,
            target_path=target,
            mode=ProcessMode(job.mode),
            strict=False,
            output_path=output if job.mode == "write" else None,
            stage=job.stage,
            options={"stage_rag": True, "stage_rag_top_k": 3},
        )
        result = process_report(request)
        if job.mode == "write" and result.exit_code.value in {0, 1}:
            target = output
        else:
            break
    return result


def validate_operation(operation: object) -> str:
    if not isinstance(operation, str) or operation not in {"reconcile", "verify"}:
        raise ValueError("invalid operation")
    return operation


class TargetStageSelectionError(ValueError):
    """A controlled stage-selection outcome safe to project to the API."""

    def __init__(self, code: str, stage_options: tuple[str, ...] = ()) -> None:
        super().__init__(code)
        self.code = code
        self.stage_options = stage_options


def _resolve_target_stage(target: Path, digest: str, requested: str | None) -> str:
    stages = _structurally_valid_target_stages(target, digest)
    if requested is not None:
        if requested in stages:
            return requested
        raise TargetStageSelectionError("not_found")
    if len(stages) == 1:
        return stages[0]
    if not stages:
        raise TargetStageSelectionError("not_found")
    if len(stages) > MAX_STAGE_OPTIONS:
        raise TargetStageSelectionError("selection_limit_exceeded")
    raise TargetStageSelectionError("selection_required", stages)


def _structurally_valid_target_stages(target: Path, digest: str) -> tuple[str, ...]:
    """Return only stages that the authoritative reader can turn into target rows."""

    from report_processor.excel import WorkbookOpenRequest, open_dual_workbook
    from report_processor.processing.adapters import _materialized

    from .reconciliation_target import structurally_valid_reconciliation_stages

    try:
        source = _materialized(target, f"target-stage-discovery:{digest}")
        with open_dual_workbook(WorkbookOpenRequest(source)) as session:
            discovered = structurally_valid_reconciliation_stages(
                session, maximum=MAX_STAGE_OPTIONS
            )
    except (OSError, TypeError, ValueError, RuntimeError, ReportProcessorError):
        return ()
    return tuple(stage for stage in discovered if is_safe_stage_text(stage))


def _verify_inputs(job: AdminJob) -> None:
    _capture_input_snapshot(job)


def _capture_input_snapshot(job: AdminJob) -> tuple[tuple[Path, str, tuple[int, int]], ...]:
    sources = job.sources or (job.source,)
    digests = job.source_digests or (job.source_digest,)
    if len(sources) != len(digests):
        raise RuntimeError("source upload changed during processing")
    snapshot = []
    for source, digest in zip(sources, digests, strict=True):
        identity, actual = _file_identity_and_digest(source)
        if actual != digest:
            raise RuntimeError("source upload changed during processing")
        snapshot.append((source, digest, identity))
    identity, actual = _file_identity_and_digest(job.target)
    if actual != job.target_digest:
        raise RuntimeError("target upload changed during processing")
    snapshot.append((job.target, job.target_digest, identity))
    return tuple(snapshot)


def _file_digest(path: Path) -> str:
    _identity, digest = _file_identity_and_digest(path)
    return digest


def _file_identity_and_digest(path: Path) -> tuple[tuple[int, int], str]:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("input upload is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return (info.st_dev, info.st_ino), digest.hexdigest()
    finally:
        os.close(descriptor)


def _exit_code(result: object) -> int:
    value = getattr(result, "exit_code", -1)
    return int(value.value if hasattr(value, "value") else value)


def _validate_owned_apply_output(job: AdminJob, output: object) -> tuple[tuple[int, int], str]:
    expected = job.directory / "result.xlsx"
    if not isinstance(output, Path) or output != expected:
        raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")
    try:
        return _file_identity_and_digest_with_mode(output)
    except OSError as error:
        raise RuntimeError("RECONCILIATION_OUTPUT_INVALID") from error


def _file_identity_and_digest_with_mode(path: Path) -> tuple[tuple[int, int], str]:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return (info.st_dev, info.st_ino), digest.hexdigest()
    finally:
        os.close(descriptor)


def _verify_apply_artifacts(
    job: AdminJob,
    inputs: tuple[tuple[Path, str, tuple[int, int]], ...],
    output: Path,
    output_identity: tuple[int, int],
) -> None:
    for path, expected_digest, expected_identity in inputs:
        identity, digest = _file_identity_and_digest(path)
        if identity != expected_identity or digest != expected_digest:
            raise RuntimeError("input upload changed during authoritative apply")
    identity, _digest = _file_identity_and_digest(output)
    if identity != output_identity:
        raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")


def _digest_apply_fallback(
    job: AdminJob,
    state: ReconciliationReviewState,
    feedback: tuple[object, ...],
    output_digest: str,
    *,
    purpose: str = "payload",
) -> str:
    """Only supports legacy injected executors; authoritative apply supplies its plan."""
    encoded = repr(
        (
            "ReconciliationApplyIntegrity-1.0",
            purpose,
            job.job_id,
            job.target_digest,
            tuple(job.source_digests),
            job.stage,
            state.version_fingerprint,
            feedback,
            output_digest,
        )
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _remove_partial_output(job: AdminJob, owned_identity: tuple[int, int] | None = None) -> None:
    candidate = job.directory / "result.xlsx"
    if owned_identity is not None:
        try:
            current = candidate.stat()
        except FileNotFoundError:
            pass
        else:
            if (current.st_dev, current.st_ino) == owned_identity:
                candidate.unlink(missing_ok=True)
    job.output = None
    job.result_name = None

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
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

from report_processor.domain.exceptions import ReportProcessorError

from .drawing_card_job_store import DrawingCardJobStore
from .presentation import journal_payload, processing_presentation
from .reconciliation_execution import (
    ReconciliationReviewResult,
    apply_review,
    prepare_period_review,
    prepare_review,
    rebuild_apply_evidence,
)
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
RECONCILIATION_MANIFEST_CONTRACT = "AdminReconciliationJobManifest-3.0"
_RECOVERABLE_MANIFEST_STATUSES = frozenset(
    {"ready", "review_required", "applying", "pending", "running"}
)
_CANONICAL_VERIFICATION_STATUSES = frozenset({"passed", "failed"})
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
    reporting_period: str | None = None
    target_identity_digest: str | None = None
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
    output_identity: tuple[int, int] | None = None
    output_digest: str | None = None
    apply_manifest: dict[str, object] | None = None
    reconciliation_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def result_available(self) -> bool:
        return (
            self.output is not None
            and self.output.is_file()
            and not self.unresolved_suggestion_ids
            and not self.unresolved_manual_discrepancy_ids
            and self.status not in {"pending", "running", "applying", "failed"}
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
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)
        self.feedback_store = ReconciliationFeedbackStore(self.workspace_root)
        self._job_store = DrawingCardJobStore(
            self.workspace_root, expected_contract=RECONCILIATION_MANIFEST_CONTRACT
        )
        self._recover_jobs()

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
        reporting_period: str | None = None,
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
        clean_period = _validate_reporting_period(reporting_period)
        if clean_operation == "verify" and clean_period is not None:
            raise ValueError("REPORTING_PERIOD_UNSUPPORTED_FOR_VERIFY")
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
                reporting_period=clean_period,
                target_identity_digest=(
                    None
                    if clean_period is not None
                    else _strict_target_identity_digest(target_digest, selected_stage)
                ),
            )
            self.jobs[job_id] = job
            registered = True
            self._persist_job(job)
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
        self._persist_job(job)
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
                    else _prepare_job_review(job, self.feedback_store.records(job.target_digest))
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
            self._job_store.delete(job.job_id)
            shutil.rmtree(job.directory, ignore_errors=True)
        else:
            self._persist_job(job)
        return job

    def get_job(self, job_id: str) -> AdminJob:
        if job_id not in self.jobs:
            manifest = self._job_store.load(job_id)
            if manifest is None or not self._recover_manifest(job_id, manifest):
                raise KeyError(job_id)
        return self.jobs[job_id]

    def get(self, job_id: str) -> AdminJob:
        """Backward-compatible alias for the frozen in-process service API."""

        return self.get_job(job_id)

    def put_reconciliation_group(self, job_id: str, group_id: str, decision) -> AdminJob:
        return self._mutate_reconciliation(job_id, "put_group", group_id, decision)

    def put_reconciliation_row(self, job_id: str, row_id: str, decision) -> AdminJob:
        return self._mutate_reconciliation(job_id, "put_row", row_id, decision)

    def delete_reconciliation_row(self, job_id: str, row_id: str, version: str) -> AdminJob:
        return self._mutate_reconciliation(job_id, "delete_row", row_id, version)

    def put_reconciliation_package(self, job_id: str, package_id: str, decision) -> AdminJob:
        return self._mutate_reconciliation(job_id, "put_package", package_id, decision)

    def put_reconciliation_family(self, job_id: str, family_id: str, decision) -> AdminJob:
        return self._mutate_reconciliation(job_id, "put_family", family_id, decision)

    def accept_reconciliation_safe_packages(self, job_id: str, packages) -> AdminJob:
        return self._mutate_reconciliation(job_id, "accept_safe_packages", packages)

    def undo_reconciliation(self, job_id: str) -> AdminJob:
        return self._mutate_reconciliation(job_id, "undo")

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
            _validate_apply_identity(job, job.review_state)
            decisions = tuple(job.review_state.core_decisions())
            job.status = "applying"
            self._persist_job(job)
            owned_output: tuple[int, int] | None = None
            try:
                _verify_inputs(job)
                apply_job = _materialize_apply_snapshot(job)
                applied = apply_review(apply_job, job.review_state, decisions)
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
                evidence = _apply_evidence(apply_job, job.review_state, decisions, applied)
                if evidence["actionable"] is False and output_digest != job.target_digest:
                    raise RuntimeError("RECONCILIATION_UNCHANGED_OUTPUT_INVALID")
                job.output = output
                job.result_name = "optimized-report.xlsx"
                job.output_identity = owned_output
                job.output_digest = output_digest
                job.apply_manifest = _apply_manifest(
                    output,
                    owned_output,
                    output_digest,
                    apply_key,
                    payload_hash,
                    evidence,
                )
                # The exact replay plan is durable before touching SQLite.
                self._persist_job(job)
                self.feedback_store.commit_apply(
                    target_digest=job.target_digest,
                    apply_key=apply_key,
                    payload_hash=payload_hash,
                    records=feedback,
                    precommit_validator=lambda: _verify_apply_artifacts(
                        job, output, owned_output, output_digest
                    ),
                )
                # Publish a fully validated ready manifest while keeping the
                # in-memory state applying until that durable write succeeds.
                ready_manifest = self._manifest_for(
                    replace(job, status="ready", apply_manifest=None)
                )
                self._job_store.save(job.job_id, ready_manifest)
                job.status = "ready"
                job.apply_manifest = None
            except BaseException:
                if job.apply_manifest is None:
                    _remove_partial_output(job, owned_output)
                    job.status, job.errors = "failed", ("PROCESSING_FAILED",)
                    self._persist_job(job)
                raise
            return job

    def _reconciliation_lock(self, job_id: str) -> threading.RLock:
        return self.get_job(job_id).reconciliation_lock

    def _mutate_reconciliation(self, job_id: str, method: str, *args) -> AdminJob:
        with self._reconciliation_lock(job_id):
            job = self._review_job(job_id)
            getattr(job.review_state, method)(*args)
            return job

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
        self._persist_job(job)
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
        self._persist_job(job)
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
        self._persist_job(job)
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
        _verify_served_output(job)
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

    def _persist_job(self, job: AdminJob) -> None:
        """Persist only immutable upload facts and bounded result metadata."""
        self._job_store.save(job.job_id, self._manifest_for(job))

    def _manifest_for(self, job: AdminJob) -> dict[str, object]:
        source_paths = tuple(job.sources or (job.source,))
        source_digests = tuple(job.source_digests or (job.source_digest,))
        source_names = tuple(job.source_names or tuple(path.name for path in source_paths))
        if len(source_paths) != len(source_digests) or not source_paths:
            raise ValueError("reconciliation job has invalid source facts")
        if len(source_names) != len(source_paths) or any(not name for name in source_names):
            raise ValueError("reconciliation job has invalid source names")
        _validate_manifest_identity(job)
        payload: dict[str, object] = {
            "contract": RECONCILIATION_MANIFEST_CONTRACT,
            "status": job.status,
            "operation": job.operation,
            "mode": job.mode,
            "stage": job.stage,
            "source_paths": [_job_relative_path(job, path) for path in source_paths],
            "source_digests": list(source_digests),
            "source_names": [Path(name).name for name in source_names],
            "target_path": _job_relative_path(job, job.target),
            "target_digest": job.target_digest,
            "target_name": Path(job.target_name or job.target.name).name,
            "reporting_period": job.reporting_period,
            "target_identity_digest": job.target_identity_digest,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        if job.output is not None:
            if not _safe_artifact_name(job.result_name):
                raise ValueError("reconciliation output name is invalid")
            payload["output_path"] = _job_relative_path(job, job.output)
            if job.output_identity is None or job.output_digest is None:
                identity, output_digest, _mode = _current_output_facts(job.output)
                job.output_identity = identity
                job.output_digest = output_digest
            payload["output_digest"] = job.output_digest
            payload["output_identity"] = list(job.output_identity)
            payload["result_name"] = job.result_name
        if job.apply_manifest is not None:
            payload["apply"] = job.apply_manifest
        if job.operation == "verify":
            _validate_verification_metadata(job)
            payload.update(
                verification_status=job.verification_status,
                verification_message=job.verification_message,
                checked_row_count=job.checked_row_count,
                failed_row_count=job.failed_row_count,
            )
        return payload

    def _recover_jobs(self) -> None:
        for job_id, manifest in self._job_store.load_all().items():
            self._recover_manifest(job_id, manifest)
        self._prune_terminal_jobs()

    def _recover_manifest(self, job_id: str, manifest: dict[str, object]) -> bool:
        if job_id in self.jobs:
            return True
        try:
            job = _job_from_manifest(self.workspace_root, job_id, manifest)
            if job.status not in _RECOVERABLE_MANIFEST_STATUSES:
                return False
            _verify_inputs(job)
            if job.status == "review_required":
                recovered = _prepare_job_review(job, self.feedback_store.records(job.target_digest))
                self._apply_execution_result(job, recovered)
                if job.status != "review_required" or job.review_state is None:
                    raise RuntimeError("review cannot be recovered")
            elif job.status == "ready":
                _verify_recovered_ready_job(job, manifest)
            elif job.status == "applying":
                self._recover_applying_job(job, manifest)
            else:
                # Never repeat interrupted processing.  An applying manifest
                # lacks an immutable feedback payload, so it cannot safely
                # exact-replay the SQLite commit and must fail closed.
                job.status = "failed"
                job.errors = ("PROCESSING_INTERRUPTED",)
            self.jobs[job_id] = job
            self._persist_job(job)
            return True
        except (OSError, TypeError, ValueError, RuntimeError):
            return False

    def _recover_applying_job(self, job: AdminJob, manifest: dict[str, object]) -> None:
        plan = _load_apply_manifest(job, manifest.get("apply"))
        evidence = plan["evidence"]
        if evidence["target_identity_digest"] != job.target_identity_digest:
            raise RuntimeError("reconciliation apply target identity changed")
        if evidence["input_snapshots"] != tuple(_apply_snapshot_names(job)):
            raise RuntimeError("reconciliation apply snapshots changed")
        job.output = _manifest_path(job.directory, plan["output_path"])
        job.result_name = "optimized-report.xlsx"
        job.output_identity = plan["output_identity"]
        job.output_digest = plan["output_digest"]
        _verify_apply_artifacts(job, job.output, plan["output_identity"], plan["output_digest"])
        if evidence["actionable"] is False and plan["output_digest"] != job.target_digest:
            raise RuntimeError("reconciliation unchanged output changed")
        recovered = _prepare_job_review(job, self.feedback_store.records(job.target_digest))
        self._apply_execution_result(job, recovered)
        if job.status != "review_required" or job.review_state is None:
            raise RuntimeError("reconciliation apply plan cannot be rebuilt")
        _validate_apply_identity(job, job.review_state)
        decisions = _resolve_replay_decisions(
            evidence["decisions"], job.review_state, evidence["target_identity_digest"]
        )
        current_decisions = _dump_replay_decisions(
            job.review_state.core_decisions(), evidence["target_identity_digest"]
        )
        if current_decisions != list(evidence["decisions"]):
            raise RuntimeError("reconciliation apply decisions changed")
        apply_job = _materialize_apply_snapshot(job)
        rebuilt = rebuild_apply_evidence(apply_job, job.review_state, decisions)
        if any(
            rebuilt[key] != evidence[key]
            for key in (
                "catalog_digest",
                "target_identity_digest",
                "calculation_digest",
                "rules_hash",
                "actionable",
            )
        ):
            raise RuntimeError("reconciliation apply evidence changed")
        payload_hash = hashlib.sha256(
            f"{rebuilt['plan_hash']}:output-sha256:{job.output_digest}".encode()
        ).hexdigest()
        if rebuilt["apply_key"] != plan["apply_key"] or payload_hash != plan["payload_hash"]:
            raise RuntimeError("reconciliation apply plan changed")
        self.feedback_store.commit_apply(
            target_digest=job.target_digest,
            apply_key=plan["apply_key"],
            payload_hash=plan["payload_hash"],
            records=rebuilt["feedback"],
            precommit_validator=lambda: _verify_apply_artifacts(
                job, job.output, plan["output_identity"], plan["output_digest"]
            ),
        )
        job.status = "ready"
        job.apply_manifest = None

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


def _job_relative_path(job: AdminJob, path: Path) -> str:
    resolved_directory = job.directory.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    if path.is_symlink() or not resolved_path.is_relative_to(resolved_directory):
        raise ValueError("job artifact is outside its private directory")
    return resolved_path.relative_to(resolved_directory).as_posix()


def _safe_artifact_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 255
        and value == Path(value).name
        and "/" not in value
        and "\\" not in value
    )


def _prepare_job_review(job: AdminJob, feedback):
    """Select the period path only for a canonical period-bearing reconciliation job."""
    if job.reporting_period is None:
        return prepare_review(job, feedback)
    return prepare_period_review(job, feedback)


def _job_from_manifest(workspace_root: Path, job_id: str, manifest: dict[str, object]) -> AdminJob:
    if manifest.get("contract") != RECONCILIATION_MANIFEST_CONTRACT:
        raise ValueError("reconciliation manifest contract is unsupported")
    required_strings = (
        "status",
        "operation",
        "mode",
        "stage",
        "target_path",
        "target_digest",
        "target_name",
        "updated_at",
    )
    if any(not isinstance(manifest.get(key), str) or not manifest[key] for key in required_strings):
        raise ValueError("reconciliation manifest is incomplete")
    required_keys = (
        "source_paths",
        "source_digests",
        "source_names",
        "reporting_period",
        "target_identity_digest",
    )
    if any(key not in manifest for key in required_keys):
        raise ValueError("reconciliation manifest is incomplete")
    status = str(manifest["status"])
    if status not in _RECOVERABLE_MANIFEST_STATUSES:
        raise ValueError("reconciliation manifest status is unsupported")
    operation = validate_operation(manifest["operation"])
    allowed_keys = {
        "contract",
        "status",
        "operation",
        "mode",
        "stage",
        "source_paths",
        "source_digests",
        "source_names",
        "target_path",
        "target_digest",
        "target_name",
        "reporting_period",
        "target_identity_digest",
        "updated_at",
        "output_path",
        "output_digest",
        "output_identity",
        "result_name",
    }
    if operation == "verify":
        allowed_keys.update(
            {
                "verification_status",
                "verification_message",
                "checked_row_count",
                "failed_row_count",
            }
        )
    if status == "applying":
        allowed_keys.add("apply")
    if set(manifest) - allowed_keys:
        raise ValueError("reconciliation manifest fields are unsupported")
    reporting_period = _validate_reporting_period(manifest.get("reporting_period"))
    if operation == "verify" and reporting_period is not None:
        raise ValueError("REPORTING_PERIOD_UNSUPPORTED_FOR_VERIFY")
    mode = validate_mode(manifest["mode"])
    stage = validate_stage(manifest["stage"])
    directory = Path(workspace_root) / job_id
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("reconciliation job directory is unsafe")
    directory = directory.resolve(strict=True)
    source_paths = _manifest_paths(directory, manifest.get("source_paths"))
    source_digests = _manifest_digests(manifest.get("source_digests"), expected=len(source_paths))
    target = _manifest_path(directory, manifest["target_path"])
    target_digest = _manifest_digest(manifest["target_digest"])
    target_identity_digest = _optional_manifest_digest(manifest.get("target_identity_digest"))
    names = manifest.get("source_names")
    if (
        not isinstance(names, list)
        or len(names) != len(source_paths)
        or any(not isinstance(item, str) or not item for item in names)
    ):
        raise ValueError("reconciliation manifest source names are invalid")
    if any(not _safe_artifact_name(item) for item in names):
        raise ValueError("reconciliation manifest source names are invalid")
    source_names = tuple(names)
    if not _safe_artifact_name(manifest["target_name"]):
        raise ValueError("reconciliation manifest target name is invalid")
    output = None
    output_keys = ("output_path", "output_digest", "output_identity", "result_name")
    present_output_keys = {key for key in output_keys if key in manifest}
    if present_output_keys:
        if present_output_keys != set(output_keys) or any(
            manifest[key] is None for key in output_keys
        ):
            raise ValueError("reconciliation manifest output is incomplete")
        if not _safe_artifact_name(manifest["result_name"]):
            raise ValueError("reconciliation manifest output name is invalid")
        output = _manifest_path(directory, manifest["output_path"])
    output_identity = _manifest_identity(manifest.get("output_identity")) if output else None
    output_digest = _manifest_digest(manifest.get("output_digest")) if output else None
    has_apply = "apply" in manifest
    if has_apply != (status == "applying" and output is not None):
        raise ValueError("reconciliation manifest apply is inconsistent")
    if operation == "verify":
        verification_keys = (
            "verification_status",
            "verification_message",
            "checked_row_count",
            "failed_row_count",
        )
        if any(key not in manifest for key in verification_keys):
            raise ValueError("reconciliation verification manifest is incomplete")
        if not all(
            isinstance(manifest[key], int) and manifest[key] >= 0 for key in verification_keys[2:]
        ):
            raise ValueError("reconciliation verification manifest is invalid")
    elif any(
        key in manifest
        for key in (
            "verification_status",
            "verification_message",
            "checked_row_count",
            "failed_row_count",
        )
    ):
        raise ValueError("reconciliation verification manifest is invalid")
    job = AdminJob(
        job_id=job_id,
        directory=directory,
        source=source_paths[0],
        target=target,
        stage=stage,
        mode=mode,
        source_digest=source_digests[0],
        target_digest=target_digest,
        reporting_period=reporting_period,
        target_identity_digest=target_identity_digest,
        operation=operation,
        sources=source_paths,
        source_digests=source_digests,
        source_names=source_names,
        target_name=Path(str(manifest.get("target_name") or target.name)).name,
        status=status,
        output=output,
        output_identity=output_identity,
        output_digest=output_digest,
        result_name=manifest["result_name"] if output is not None else None,
        verification_status=(
            str(manifest["verification_status"])
            if isinstance(manifest.get("verification_status"), str)
            else None
        ),
        verification_message=(
            str(manifest["verification_message"])
            if isinstance(manifest.get("verification_message"), str)
            else None
        ),
        checked_row_count=(
            _strict_manifest_count(manifest.get("checked_row_count"))
            if operation == "verify"
            else 0
        ),
        failed_row_count=(
            _strict_manifest_count(manifest.get("failed_row_count")) if operation == "verify" else 0
        ),
    )
    if operation == "verify":
        _validate_verification_metadata(job)
    _validate_manifest_identity(job)
    return job


def _manifest_paths(directory: Path, value: object) -> tuple[Path, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_SOURCES:
        raise ValueError("reconciliation manifest sources are invalid")
    return tuple(_manifest_path(directory, item) for item in value)


def _manifest_path(directory: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("reconciliation manifest path is invalid")
    candidate = directory / value
    if candidate.parent == directory and "/" not in value:
        pass
    resolved = candidate.resolve(strict=True)
    if candidate.is_symlink() or not resolved.is_relative_to(directory):
        raise ValueError("reconciliation manifest path is unsafe")
    return resolved


def _manifest_digests(value: object, *, expected: int) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError("reconciliation manifest digests are invalid")
    return tuple(_manifest_digest(item) for item in value)


def _manifest_digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("reconciliation manifest digest is invalid")
    return value


def _optional_manifest_digest(value: object) -> str | None:
    return None if value is None else _manifest_digest(value)


def _validate_reporting_period(value: object) -> str | None:
    if value is None:
        return None
    from .reconciliation_period import ReportingPeriod

    return ReportingPeriod.parse(value).value


def _strict_target_identity_digest(target_digest: str, stage: str) -> str:
    from .reconciliation_target import ReconciliationTargetIdentity

    return ReconciliationTargetIdentity(target_digest, stage).target_identity_digest


def _period_target_identity_digest(job: AdminJob) -> str:
    from .reconciliation_period_preview import preview_reconciliation_target

    return preview_reconciliation_target(
        job.target, job.target_digest, job.stage, job.reporting_period
    ).target_identity_digest


def _validate_manifest_identity(job: AdminJob) -> None:
    if job.operation == "verify" and job.reporting_period is not None:
        raise ValueError("REPORTING_PERIOD_UNSUPPORTED_FOR_VERIFY")
    if job.reporting_period is None:
        expected = _strict_target_identity_digest(job.target_digest, job.stage)
        if job.target_identity_digest != expected:
            raise ValueError("reconciliation target identity is inconsistent")
        return
    if job.status in {"pending", "running"}:
        if job.target_identity_digest is not None:
            raise ValueError("reconciliation target identity is inconsistent")
        return
    expected = _period_target_identity_digest(job)
    if job.target_identity_digest != expected:
        raise ValueError("reconciliation target identity is inconsistent")


def _validate_apply_identity(job: AdminJob, state: ReconciliationReviewState) -> None:
    if (
        job.target_identity_digest is None
        or state.target_identity_digest != job.target_identity_digest
    ):
        raise RuntimeError("reconciliation apply target identity changed")


def _validate_verification_metadata(job: AdminJob) -> None:
    if (
        type(job.checked_row_count) is not int
        or type(job.failed_row_count) is not int
        or not 0 <= job.failed_row_count <= job.checked_row_count <= 10_000_000
    ):
        raise ValueError("reconciliation verification manifest is invalid")
    if job.status in {"pending", "running", "failed"}:
        if (
            job.verification_status is not None
            or job.verification_message is not None
            or job.checked_row_count != 0
            or job.failed_row_count != 0
        ):
            raise ValueError("reconciliation verification manifest is invalid")
        return
    if job.status != "ready" or job.verification_status not in _CANONICAL_VERIFICATION_STATUSES:
        raise ValueError("reconciliation verification manifest is invalid")
    if not isinstance(job.verification_message, str) or not job.verification_message:
        raise ValueError("reconciliation verification manifest is invalid")
    if job.verification_status == "passed":
        if job.output is not None or job.failed_row_count != 0:
            raise ValueError("reconciliation verification manifest is invalid")
        return
    if job.output is None or job.failed_row_count < 1:
        raise ValueError("reconciliation verification manifest is invalid")


def _strict_manifest_count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 10_000_000:
        raise ValueError("reconciliation verification manifest is invalid")
    return value


def _manifest_identity(value: object) -> tuple[int, int]:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or any(type(item) is not int or item < 0 for item in value)
    ):
        raise ValueError("reconciliation manifest output identity is invalid")
    return value[0], value[1]


def _apply_manifest(
    output: Path,
    identity: tuple[int, int],
    output_digest: str,
    apply_key: str,
    payload_hash: str,
    evidence: dict[str, object],
) -> dict[str, object]:
    if not all(
        isinstance(value, str) and 1 <= len(value) <= 128 for value in (apply_key, payload_hash)
    ):
        raise ValueError("reconciliation apply key is invalid")
    return {
        "output_path": output.name,
        "output_digest": output_digest,
        "output_identity": list(identity),
        "apply_key": apply_key,
        "payload_hash": payload_hash,
        "evidence": evidence,
    }


def _load_apply_manifest(job: AdminJob, value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("reconciliation apply plan is missing")
    required = ("output_path", "output_digest", "apply_key", "payload_hash", "evidence")
    if set(value) != {*required, "output_identity"}:
        raise ValueError("reconciliation apply plan is incomplete")
    output_path = value["output_path"]
    if output_path != "result.xlsx":
        raise ValueError("reconciliation apply output path is invalid")
    apply_key = value["apply_key"]
    payload_hash = value["payload_hash"]
    if not all(
        isinstance(item, str) and 1 <= len(item) <= 128 for item in (apply_key, payload_hash)
    ):
        raise ValueError("reconciliation apply key is invalid")
    return {
        "output_path": output_path,
        "output_digest": _manifest_digest(value["output_digest"]),
        "output_identity": _manifest_identity(value.get("output_identity")),
        "apply_key": apply_key,
        "payload_hash": payload_hash,
        "evidence": _load_apply_evidence(value["evidence"]),
    }


def _apply_evidence(
    job: AdminJob, state: ReconciliationReviewState, decisions, applied
) -> dict[str, object]:
    fields = (
        "catalog_digest",
        "target_identity_digest",
        "calculation_digest",
        "rules_hash",
    )
    if not all(getattr(applied, field_name, "") for field_name in fields):
        # Narrow compatibility seam for in-process injected executors. It is
        # never emitted by the authoritative adapter and cannot pretend to be
        # historical-period evidence.
        return {
            "contract": "ReconciliationApplyReplay-2.0",
            "catalog_digest": hashlib.sha256(b"legacy-catalog").hexdigest(),
            "target_identity_digest": job.target_identity_digest or job.target_digest,
            "calculation_digest": hashlib.sha256(b"legacy-calculation").hexdigest(),
            "rules_hash": hashlib.sha256(b"legacy-rules").hexdigest(),
            "actionable": True,
            "decisions": _dump_replay_decisions(
                decisions, job.target_identity_digest or job.target_digest
            ),
            "input_snapshots": _apply_snapshot_names(job),
            "legacy_injected": True,
        }
    rebuilt = rebuild_apply_evidence(job, state, decisions)
    if rebuilt["target_identity_digest"] != job.target_identity_digest:
        raise RuntimeError("RECONCILIATION_APPLY_EVIDENCE_CHANGED")
    for field_name in fields:
        supplied = getattr(applied, field_name, "")
        if supplied and supplied != rebuilt[field_name]:
            raise RuntimeError("RECONCILIATION_APPLY_EVIDENCE_CHANGED")
    supplied_actionable = getattr(applied, "actionable", rebuilt["actionable"])
    if supplied_actionable is not None and supplied_actionable != rebuilt["actionable"]:
        raise RuntimeError("RECONCILIATION_APPLY_EVIDENCE_CHANGED")
    return {
        "contract": "ReconciliationApplyReplay-2.0",
        "catalog_digest": rebuilt["catalog_digest"],
        "target_identity_digest": rebuilt["target_identity_digest"],
        "calculation_digest": rebuilt["calculation_digest"],
        "rules_hash": rebuilt["rules_hash"],
        "actionable": rebuilt["actionable"],
        "decisions": _dump_replay_decisions(decisions, rebuilt["target_identity_digest"]),
        "input_snapshots": _apply_snapshot_names(job),
    }


def _load_apply_evidence(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("contract") != "ReconciliationApplyReplay-2.0":
        raise ValueError("reconciliation apply evidence is invalid")
    required = {
        "contract",
        "catalog_digest",
        "target_identity_digest",
        "calculation_digest",
        "rules_hash",
        "actionable",
        "decisions",
        "input_snapshots",
    }
    if set(value) != required:
        raise ValueError("reconciliation apply evidence is unsupported")
    fields = ("catalog_digest", "target_identity_digest", "calculation_digest", "rules_hash")
    if any(_optional_manifest_digest(value.get(field_name)) is None for field_name in fields):
        raise ValueError("reconciliation apply evidence is invalid")
    if not isinstance(value.get("actionable"), bool):
        raise ValueError("reconciliation apply evidence is invalid")
    decisions = _load_replay_decisions(value.get("decisions"))
    snapshots = value.get("input_snapshots")
    if (
        not isinstance(snapshots, list)
        or not snapshots
        or any(not isinstance(item, str) or "/" in item or not item for item in snapshots)
    ):
        raise ValueError("reconciliation apply evidence is invalid")
    return {
        "catalog_digest": _manifest_digest(value["catalog_digest"]),
        "target_identity_digest": _manifest_digest(value["target_identity_digest"]),
        "calculation_digest": _manifest_digest(value["calculation_digest"]),
        "rules_hash": _manifest_digest(value["rules_hash"]),
        "actionable": value["actionable"],
        "decisions": decisions,
        "input_snapshots": tuple(snapshots),
    }


def _replay_category_token(target_identity_digest: str, category: str) -> str:
    _manifest_digest(target_identity_digest)
    if not isinstance(category, str) or not category:
        raise ValueError("reconciliation apply category is invalid")
    payload = (
        b"ReconciliationReplayCategory-1.0\0"
        + target_identity_digest.encode("ascii")
        + b"\0"
        + category.encode("utf-8")
    )
    return hashlib.sha256(payload).hexdigest()


def _dump_replay_decisions(decisions, target_identity_digest: str) -> list[dict[str, str | None]]:
    return [
        {
            "action": decision.action.value,
            "group_id": decision.group_id,
            "mode": decision.mode.value if decision.mode else None,
            "row_id": decision.row_id,
            "target_category_token": (
                _replay_category_token(target_identity_digest, decision.target_category)
                if decision.target_category is not None
                else None
            ),
            "version": decision.version,
        }
        for decision in sorted(
            decisions, key=lambda item: (item.group_id or "", item.row_id or "", item.action.value)
        )
    ]


def _load_replay_decisions(value: object) -> tuple[dict[str, str | None], ...]:
    from report_processor.reconciliation_review import ReviewAction, ReviewMode

    if not isinstance(value, list) or len(value) > MAX_MANUAL_DISCREPANCY_DECISIONS:
        raise ValueError("reconciliation apply decisions are invalid")
    decisions: list[dict[str, str | None]] = []
    for record in value:
        if not isinstance(record, dict) or set(record) != {
            "action",
            "group_id",
            "mode",
            "row_id",
            "target_category_token",
            "version",
        }:
            raise ValueError("reconciliation apply decisions are invalid")
        try:
            action = ReviewAction(record["action"])
            mode = ReviewMode(record["mode"]) if record["mode"] is not None else None
        except (TypeError, ValueError) as error:
            raise ValueError("reconciliation apply decisions are invalid") from error
        values = ("group_id", "row_id", "version")
        if any(
            record[item] is not None
            and (not isinstance(record[item], str) or not 1 <= len(record[item]) <= 128)
            for item in values
        ):
            raise ValueError("reconciliation apply decisions are invalid")
        token = record["target_category_token"]
        if token is not None:
            token = _manifest_digest(token)
        if action is ReviewAction.ACCEPT:
            if mode is None or token is None:
                raise ValueError("reconciliation apply decisions are invalid")
        elif mode is not None or token is not None:
            raise ValueError("reconciliation apply decisions are invalid")
        decisions.append(
            {
                "action": action.value,
                "mode": mode.value if mode is not None else None,
                "target_category_token": token,
                "group_id": record["group_id"],
                "row_id": record["row_id"],
                "version": record["version"],
            }
        )
    return tuple(decisions)


def _resolve_replay_decisions(
    records: tuple[dict[str, str | None], ...],
    state: ReconciliationReviewState,
    target_identity_digest: str,
):
    from report_processor.reconciliation_review import ReviewAction, ReviewDecision, ReviewMode

    categories_by_token: dict[str, str] = {}
    for category in state.categories:
        token = _replay_category_token(target_identity_digest, category)
        if token in categories_by_token:
            raise RuntimeError("reconciliation apply category token is ambiguous")
        categories_by_token[token] = category
    decisions = []
    for record in records:
        token = record["target_category_token"]
        category = None if token is None else categories_by_token.get(token)
        if token is not None and category is None:
            raise RuntimeError("reconciliation apply category token changed")
        try:
            decisions.append(
                ReviewDecision(
                    ReviewAction(record["action"]),
                    ReviewMode(record["mode"]) if record["mode"] is not None else None,
                    category,
                    group_id=record["group_id"],
                    row_id=record["row_id"],
                    version=record["version"],
                )
            )
        except (TypeError, ValueError) as error:
            raise RuntimeError("reconciliation apply decisions changed") from error
    return tuple(decisions)


def _apply_snapshot_names(job: AdminJob) -> list[str]:
    sources = job.sources or (job.source,)
    return [
        *(
            f"apply-input-source-{index:02d}{source.suffix.casefold()}"
            for index, source in enumerate(sources, 1)
        ),
        f"apply-input-target{job.target.suffix.casefold()}",
    ]


def _verify_recovered_ready_job(job: AdminJob, manifest: dict[str, object]) -> None:
    if job.output is None:
        if job.operation != "verify" or job.verification_status != "passed":
            raise RuntimeError("reconciliation ready result is unavailable")
        return
    expected_digest = _manifest_digest(manifest.get("output_digest"))
    identity = _manifest_identity(manifest.get("output_identity"))
    _verify_output_facts(job.output, identity, expected_digest)
    job.output_identity = identity
    job.output_digest = expected_digest
    if job.result_name is None:
        raise RuntimeError("reconciliation output name is missing")


def _rebuild_apply_plan(job: AdminJob, state: ReconciliationReviewState):
    """Derive the replay inputs from immutable uploads and autosaved decisions."""
    decisions = tuple(state.core_decisions())
    rebuilt = rebuild_apply_evidence(job, state, decisions)
    payload_hash = hashlib.sha256(
        f"{rebuilt['plan_hash']}:output-sha256:{job.output_digest}".encode()
    ).hexdigest()
    return decisions, rebuilt["feedback"], rebuilt["apply_key"], payload_hash


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


def _materialize_apply_snapshot(job: AdminJob) -> AdminJob:
    """Bind authoritative readers to private immutable copies, not mutable uploads."""
    sources = job.sources or (job.source,)
    digests = job.source_digests or (job.source_digest,)
    snapshots: list[Path] = []
    for index, (source, digest) in enumerate(zip(sources, digests, strict=True), 1):
        destination = job.directory / f"apply-input-source-{index:02d}{source.suffix.casefold()}"
        _copy_or_verify_snapshot(source, destination, digest)
        snapshots.append(destination)
    target = job.directory / f"apply-input-target{job.target.suffix.casefold()}"
    _copy_or_verify_snapshot(job.target, target, job.target_digest)
    return replace(job, source=snapshots[0], sources=tuple(snapshots), target=target)


def _copy_or_verify_snapshot(source: Path, destination: Path, expected_digest: str) -> None:
    if destination.exists() or destination.is_symlink():
        identity, digest = _file_identity_and_digest(destination)
        del identity
        if digest != expected_digest:
            raise RuntimeError("input snapshot changed during recovery")
        return
    _copy_verified_snapshot(source, destination, expected_digest)


def _copy_verified_snapshot(source: Path, destination: Path, expected_digest: str) -> None:
    source_fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    destination_fd: int | None = None
    digest = hashlib.sha256()
    try:
        info = os.fstat(source_fd)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("input upload is not a regular file")
        destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        while chunk := os.read(source_fd, 1024 * 1024):
            digest.update(chunk)
            os.write(destination_fd, chunk)
        os.fsync(destination_fd)
        os.fchmod(destination_fd, 0o600)
        if digest.hexdigest() != expected_digest:
            raise RuntimeError("input upload changed during snapshot")
    except BaseException:
        if destination_fd is not None:
            os.close(destination_fd)
            destination_fd = None
        # Never unlink by pathname here: an attacker can replace it between
        # our failed write and cleanup. The uniquely named private snapshot is
        # not returned to readers and expires with the job directory.
        raise
    finally:
        os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)


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
    output: Path,
    output_identity: tuple[int, int],
    output_digest: str,
) -> None:
    _verify_inputs(job)
    identity, digest, mode = _current_output_facts(output)
    if identity != output_identity or digest != output_digest or mode != 0o600:
        raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")


def _current_output_facts(path: Path) -> tuple[tuple[int, int], str, int]:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        identity = (info.st_dev, info.st_ino)
        path_info = os.lstat(path)
        if stat.S_ISLNK(path_info.st_mode) or (path_info.st_dev, path_info.st_ino) != identity:
            raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")
        return identity, digest.hexdigest(), stat.S_IMODE(info.st_mode)
    finally:
        os.close(descriptor)


def _verify_output_facts(
    path: Path, expected_identity: tuple[int, int], expected_digest: str
) -> None:
    identity, digest, mode = _current_output_facts(path)
    if identity != expected_identity or digest != expected_digest or mode != 0o600:
        raise RuntimeError("RECONCILIATION_OUTPUT_INVALID")


def _verify_served_output(job: AdminJob) -> None:
    if job.output is None or job.output_identity is None:
        raise KeyError(job.job_id)
    try:
        identity, digest, _mode = _current_output_facts(job.output)
    except (OSError, RuntimeError) as error:
        raise KeyError(job.job_id) from error
    if identity != job.output_identity:
        raise KeyError(job.job_id)
    if job.output_digest is None or digest != job.output_digest:
        raise KeyError(job.job_id)
    try:
        path_info = os.lstat(job.output)
    except OSError as error:
        raise KeyError(job.job_id) from error
    if stat.S_ISLNK(path_info.st_mode) or (path_info.st_dev, path_info.st_ino) != identity:
        raise KeyError(job.job_id)


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
    # POSIX has no unlink-by-file-descriptor. A stat/unlink sequence can erase a
    # concurrent replacement, so terminal private job cleanup intentionally
    # retains the path. It is inaccessible as a failed result and removed only
    # with the job directory's controlled retention lifecycle.
    del owned_identity
    job.output = None
    job.result_name = None

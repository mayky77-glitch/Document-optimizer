"""Private, in-memory lifecycle for deterministic drawing-card jobs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import threading
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from report_processor.drawing_card.lifecycle import DrawingCardWorkflowCancelled
from report_processor.drawing_card.matching.matcher import ReviewApproval
from report_processor.drawing_card.models import (
    DrawingSourceRow,
    MatchDecision,
    WorkflowRequest,
    WorkflowResult,
)
from report_processor.drawing_card.periods import discover_workbook_periods
from report_processor.drawing_card.review import (
    append_feedback,
    build_review_clusters,
    cluster_approvals,
    import_review_approvals,
    inline_review_rows,
    review_approval,
    write_approvals,
)
from report_processor.drawing_card.review.clusters import ReviewCluster
from report_processor.drawing_card.statuses import Status
from report_processor.drawing_card.workflow import default_template_path, run_workflow
from report_processor.metadata.period_models import DocumentPeriod
from report_processor.metadata.period_patterns import MONTHS

from .drawing_card_job_store import MANIFEST_CONTRACT, DrawingCardJobStore
from .drawing_card_review_payload import drawing_card_cluster_payload

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_SOURCES = 32
MAX_RETAINED_TERMINAL_JOBS = 64
_SOURCE_SUFFIXES = {".xlsx", ".xlsm", ".xlsb"}
_RESULT_NAME = "drawing-card.xlsx"
_REVIEW_NAME = "manual_review.xlsx"
_MACHINE_CONSENSUS_NAME = "machine-consensus.jsonl"
_PUBLISHABLE_WORKFLOW_STATUSES = {
    Status.OK,
    Status.COMPLETED_WITH_WARNINGS,
    Status.PARTIALLY_READY,
}
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_CANONICAL_PERIOD_RE = re.compile(r"(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])")
_RUSSIAN_PERIOD_RE = re.compile(
    rf"(?P<month>{'|'.join(re.escape(name) for name in sorted(MONTHS, key=len, reverse=True))})"
    r"\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


@dataclass(slots=True, repr=False)
class DrawingCardJob:
    job_id: str
    directory: Path
    sources: tuple[Path, ...]
    source_hashes: tuple[str, ...]
    mode: Literal["create", "update"]
    period: str | None
    existing_card: Path | None
    existing_card_hash: str | None = None
    existing_name: str | None = None
    status: str = "processing"
    result: Path | None = None
    result_hash: str | None = None
    review: Path | None = None
    errors: tuple[str, ...] = ()
    summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    warning_counts: dict[str, int] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    blocker_counts: dict[str, int] = field(default_factory=dict)
    funnel: dict[str, object] = field(default_factory=dict)
    schema_recognition: tuple[dict[str, object], ...] = ()
    exclusion_audit: Path | None = field(default=None, repr=False)
    category_units: dict[str, tuple[str, ...]] = field(default_factory=dict)
    review_items: dict[str, dict[str, object]] = field(default_factory=dict)
    review_rows: dict[str, DrawingSourceRow] = field(default_factory=dict, repr=False)
    review_decisions: dict[str, MatchDecision] = field(default_factory=dict, repr=False)
    inline_approvals: dict[str, ReviewApproval] = field(default_factory=dict, repr=False)
    cluster_actions: dict[str, dict[str, ReviewApproval]] = field(default_factory=dict, repr=False)
    rag_mode: Literal["off", "semantic"] = "semantic"
    run_count: int = 0
    # Lifecycle fields are intentionally primitive: they can be mirrored in a
    # private manifest without serialising workbook values or local paths.
    phase: str = "upload"
    processed_files: int = 0
    total_files: int | None = None
    processed_rows: int = 0
    total_rows: int | None = None
    started_at: str = ""
    updated_at: str = ""
    terminal_cause: str | None = None
    attempt: int = 0
    idempotency_key: str | None = None
    cancel_event: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )

    def __repr__(self) -> str:
        return (
            "DrawingCardJob("
            f"job_id={self.job_id!r}, status={self.status!r}, "
            f"mode={self.mode!r}, run_count={self.run_count!r})"
        )

    @property
    def result_available(self) -> bool:
        return self.status == "ready" and self.result is not None and self.result.is_file()


class DrawingCardPersistenceError(RuntimeError):
    """A private job state mutation could not be durably committed."""


class DrawingCardService:
    """Keep uploaded sources and all workflow artifacts in an opaque private job."""

    def __init__(
        self,
        workspace_root: Path,
        runner: Callable[[WorkflowRequest], WorkflowResult] | None = None,
        *,
        background: bool = False,
        max_background_workers: int = 2,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)
        self.runner = runner or run_workflow
        self.background = background
        self._jobs: dict[str, DrawingCardJob] = {}
        self._store = DrawingCardJobStore(self.workspace_root)
        self._lock = threading.RLock()
        self._worker_slots = threading.BoundedSemaphore(max(1, max_background_workers))
        self._idempotency: dict[str, str] = {}
        self._pending_idempotency: dict[str, threading.Event] = {}
        self._restore_jobs()

    def create_job(
        self,
        *,
        sources: list[tuple[str, bytes]],
        mode: Literal["create", "update"] = "create",
        existing_name: str | None = None,
        existing_content: bytes | None = None,
        period: str | None = None,
        rag_mode: Literal["off", "semantic"] = "semantic",
        background: bool | None = None,
        idempotency_key: str | None = None,
    ) -> DrawingCardJob:
        if mode not in {"create", "update"}:
            raise ValueError("mode must be create or update")
        if mode == "update":
            if existing_name is None or existing_content is None:
                raise ValueError("update requires an existing .xlsx drawing card")
            _validate_existing(existing_name, existing_content)
        elif existing_name is not None or existing_content is not None:
            raise ValueError("existing card is only valid for update")
        _validate_sources(sources, existing_content=existing_content)
        if rag_mode not in {"off", "semantic"}:
            raise ValueError("rag_mode must be off or semantic")
        clean_period = _validate_period(period)
        use_background = self.background if background is None else background
        clean_idempotency_key = _validate_idempotency_key(idempotency_key)
        reservation: threading.Event | None = None
        owns_reservation = False
        with self._lock:
            if clean_idempotency_key is not None:
                existing_job_id = self._idempotency.get(clean_idempotency_key)
                if existing_job_id is not None:
                    existing_job = self.get_job(existing_job_id)
                    if not _same_idempotent_request(
                        existing_job,
                        sources=sources,
                        mode=mode,
                        period=clean_period,
                        rag_mode=rag_mode,
                        existing_name=existing_name,
                        existing_content=existing_content,
                    ):
                        raise ValueError("idempotency key conflicts with another request")
                    return existing_job
                reservation = self._pending_idempotency.get(clean_idempotency_key)
                if reservation is None:
                    reservation = threading.Event()
                    self._pending_idempotency[clean_idempotency_key] = reservation
                    owns_reservation = True
        if clean_idempotency_key is not None and reservation is not None and reservation.is_set():
            # A previous creator completed between lock release and this check.
            with self._lock:
                existing_job = self.get_job(self._idempotency[clean_idempotency_key])
                if not _same_idempotent_request(
                    existing_job,
                    sources=sources,
                    mode=mode,
                    period=clean_period,
                    rag_mode=rag_mode,
                    existing_name=existing_name,
                    existing_content=existing_content,
                ):
                    raise ValueError("idempotency key conflicts with another request")
                return existing_job
        if clean_idempotency_key is not None and reservation is not None and not owns_reservation:
            reservation.wait()
            with self._lock:
                existing_job_id = self._idempotency.get(clean_idempotency_key)
                if existing_job_id is None:
                    raise ValueError("idempotent upload was not created")
                existing_job = self.get_job(existing_job_id)
                if not _same_idempotent_request(
                    existing_job,
                    sources=sources,
                    mode=mode,
                    period=clean_period,
                    rag_mode=rag_mode,
                    existing_name=existing_name,
                    existing_content=existing_content,
                ):
                    raise ValueError("idempotency key conflicts with another request")
                return existing_job

        job_id = "job_" + secrets.token_urlsafe(18)
        directory = self.workspace_root / job_id
        directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        try:
            source_paths = tuple(
                _write_private(directory / "sources" / f"{index:02d}-{name}", content)
                for index, (name, content) in enumerate(sources, 1)
            )
            existing = (
                _write_private(directory / "existing_card.xlsx", existing_content)
                if existing_content is not None
                else None
            )
            job = DrawingCardJob(
                job_id=job_id,
                directory=directory,
                sources=source_paths,
                source_hashes=tuple(_digest(content) for _name, content in sources),
                mode=mode,
                period=clean_period,
                existing_card=existing,
                existing_card_hash=(
                    _digest(existing_content) if existing_content is not None else None
                ),
                existing_name=existing_name,
                rag_mode=rag_mode,
                status="queued" if use_background else "processing",
                total_files=len(source_paths),
                started_at=_utc_now(),
                updated_at=_utc_now(),
                idempotency_key=clean_idempotency_key,
            )
            with self._lock:
                self._jobs[job_id] = job
                if clean_idempotency_key is not None:
                    self._idempotency[clean_idempotency_key] = job_id
                    pending = self._pending_idempotency.pop(clean_idempotency_key, None)
                    if pending is not None:
                        pending.set()
                self._persist_job(job)
            if use_background:
                self._schedule(job)
                return job
            result = self._run(job)
            self._prune_terminal_jobs()
            return result
        except Exception:
            with self._lock:
                self._jobs.pop(job_id, None)
                if clean_idempotency_key is not None:
                    self._idempotency.pop(clean_idempotency_key, None)
                    pending = self._pending_idempotency.pop(clean_idempotency_key, None)
                    if pending is not None:
                        pending.set()
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> DrawingCardJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise KeyError(job_id) from error

    def discover_periods(self, sources: list[tuple[str, bytes]]) -> tuple[str, ...]:
        """Inspect filenames and workbook values read-only without creating a job."""
        _validate_sources(sources)
        return discover_workbook_periods(sources, temporary_root=self.workspace_root)

    def _prune_terminal_jobs(self) -> None:
        terminal = sorted(
            (
                job
                for job in self._jobs.values()
                if job.status in {"ready", "failed", "blocked", "cancelled"}
            ),
            key=lambda job: (job.updated_at, job.job_id),
        )
        for job in terminal[:-MAX_RETAINED_TERMINAL_JOBS]:
            self._jobs.pop(job.job_id, None)
            if self._idempotency.get(job.idempotency_key) == job.job_id:
                self._idempotency.pop(job.idempotency_key, None)
            self._store.delete(job.job_id)

    def get_result(self, job_id: str) -> tuple[Path, str]:
        job = self.get_job(job_id)
        if not job.result_available or job.result is None:
            raise KeyError(job_id)
        return job.result, _RESULT_NAME

    def get_review(self, job_id: str) -> tuple[Path, str]:
        job = self.get_job(job_id)
        if job.status != "review_required" or job.review is None or not job.review.is_file():
            raise KeyError(job_id)
        return job.review, _REVIEW_NAME

    def list_exclusion_audit(
        self, *, job_id: str, page: int = 1, page_size: int = 100
    ) -> dict[str, object]:
        """Return a bounded, path-free page from the private row disposition ledger."""
        job = self.get_job(job_id)
        if page < 1 or not 1 <= page_size <= 200:
            raise ValueError("invalid audit page")
        path = job.exclusion_audit
        if path is None or not path.is_file() or not _inside_job(path, job):
            raise KeyError(job_id)
        items: list[dict[str, object]] = []
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(raw, dict) or raw.get("disposition") not in {
                    "HIERARCHY_AGGREGATE_EXCLUDED",
                    "HIERARCHY_RESOURCE_DETAIL_EXCLUDED",
                    "DUPLICATE_EXCLUDED",
                    "UNCLASSIFIED",
                }:
                    continue
                items.append(_controlled_exclusion_record(raw))
        start = (page - 1) * page_size
        return {
            "items": items[start : start + page_size],
            "page": page,
            "page_size": page_size,
            "total": len(items),
        }

    def apply_review(
        self, *, job_id: str, review_name: str, review_content: bytes
    ) -> DrawingCardJob:
        job = self.get_job(job_id)
        if job.status != "review_required":
            raise ValueError("job does not await manual review")
        _validate_review(review_name, review_content)
        review_path = _write_private(job.directory / "completed_review.xlsx", review_content)
        try:
            import_review_approvals(review_path)
        except (OSError, ValueError) as error:
            review_path.unlink(missing_ok=True)
            raise ValueError("invalid manual review workbook") from error
        job.review = review_path
        result = self._run(job, review_decisions=review_path)
        self._prune_terminal_jobs()
        return result

    def list_review_items(
        self, *, job_id: str, page: int = 1, page_size: int = 50
    ) -> dict[str, object]:
        """Return a bounded, Russian inline-review page without workspace metadata."""
        job = self.get_job(job_id)
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("page must be positive and page_size must be between 1 and 100")
        item_ids = sorted(job.review_items)
        start = (page - 1) * page_size
        items = []
        for review_id in item_ids[start : start + page_size]:
            item = dict(job.review_items[review_id])
            approval = job.inline_approvals.get(review_id)
            if approval is not None and approval.category is not None:
                item["target_unit"] = _first_category_unit(
                    job.category_units, approval.category.value
                )
            item["решение"] = (
                {
                    "action": approval.action,
                    "category": approval.category.value if approval.category else None,
                }
                if approval is not None
                else None
            )
            items.append(item)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": len(item_ids),
            "unresolved_count": len(set(item_ids) - set(job.inline_approvals)),
            "can_apply": bool(item_ids) and set(item_ids) <= set(job.inline_approvals),
        }

    def list_review_clusters(
        self, *, job_id: str, page: int = 1, page_size: int = 50
    ) -> dict[str, object]:
        """Return current cluster identities; callers must echo the version to act."""
        job = self.get_job(job_id)
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("page must be positive and page_size must be between 1 and 100")
        clusters = self._current_clusters(job)
        start = (page - 1) * page_size
        visible = clusters[start : start + page_size]
        items = [self._cluster_payload(job, cluster) for cluster in visible]
        unresolved = [cluster for cluster in clusters if not self._cluster_resolved(job, cluster)]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_clusters": len(clusters),
            "total_rows": sum(len(cluster.member_ids) for cluster in clusters),
            "unresolved_clusters": len(unresolved),
            "unresolved_rows": sum(len(cluster.member_ids) for cluster in unresolved),
            "can_apply": bool(clusters) and set(job.review_items) <= set(job.inline_approvals),
        }

    def put_review_cluster(
        self,
        *,
        job_id: str,
        cluster_id: str,
        version: str,
        action: str,
        category: str | None = None,
    ) -> DrawingCardJob:
        """Atomically fan out one choice only to the exact current cluster."""
        job = self.get_job(job_id)
        cluster = self._require_current_cluster(job, cluster_id, version)
        if job.status != "review_required":
            raise ValueError("job does not await inline review")
        approvals = cluster_approvals(cluster, action, category)
        # ``cluster_approvals`` validates every member before this one mutation.
        before_approvals, before_actions = dict(job.inline_approvals), dict(job.cluster_actions)
        job.inline_approvals.update(approvals)
        job.cluster_actions[cluster.cluster_id] = approvals
        self._persist_review_mutation(job, before_approvals, before_actions)
        return job

    def undo_review_cluster(self, *, job_id: str, cluster_id: str, version: str) -> DrawingCardJob:
        """Undo only the still-current fanout; row edits make this safely stale."""
        job = self.get_job(job_id)
        cluster = self._require_current_cluster(job, cluster_id, version)
        applied = job.cluster_actions.get(cluster.cluster_id)
        if applied is None or tuple(applied) != cluster.member_ids:
            raise ValueError("stale cluster identity")
        if any(
            job.inline_approvals.get(row_id) != approval for row_id, approval in applied.items()
        ):
            raise ValueError("stale cluster identity")
        before_approvals, before_actions = dict(job.inline_approvals), dict(job.cluster_actions)
        for row_id in applied:
            job.inline_approvals.pop(row_id, None)
        job.cluster_actions.pop(cluster.cluster_id, None)
        self._persist_review_mutation(job, before_approvals, before_actions)
        return job

    def put_review_item(
        self, *, job_id: str, review_id: str, action: str, category: str | None = None
    ) -> DrawingCardJob:
        """Create or replace one decision; replacement makes a choice reversible."""
        job = self.get_job(job_id)
        if job.status != "review_required" or review_id not in job.review_items:
            raise ValueError("unknown review item")
        before_approvals, before_actions = dict(job.inline_approvals), dict(job.cluster_actions)
        job.inline_approvals[review_id] = review_approval(review_id, action, category)
        self._discard_cluster_actions_for(job, review_id)
        self._persist_review_mutation(job, before_approvals, before_actions)
        return job

    def delete_review_item(self, *, job_id: str, review_id: str) -> DrawingCardJob:
        job = self.get_job(job_id)
        if review_id not in job.review_items:
            raise ValueError("unknown review item")
        before_approvals, before_actions = dict(job.inline_approvals), dict(job.cluster_actions)
        job.inline_approvals.pop(review_id, None)
        self._discard_cluster_actions_for(job, review_id)
        self._persist_review_mutation(job, before_approvals, before_actions)
        return job

    def bulk_review(self, *, job_id: str, action: str) -> DrawingCardJob:
        """Apply a reversible bulk decision only where a category was proposed."""
        if action not in {"approve_all_proposed", "reject_all"}:
            raise ValueError("unsupported bulk review action")
        job = self.get_job(job_id)
        if job.status != "review_required":
            raise ValueError("job does not await inline review")
        before_approvals, before_actions = dict(job.inline_approvals), dict(job.cluster_actions)
        for review_id, item in job.review_items.items():
            proposed = item.get("предлагаемая_категория")
            if action == "approve_all_proposed" and proposed:
                job.inline_approvals[review_id] = review_approval(
                    review_id, "approve", str(proposed)
                )
                self._discard_cluster_actions_for(job, review_id)
            elif action == "reject_all":
                job.inline_approvals[review_id] = review_approval(review_id, "reject", None)
                self._discard_cluster_actions_for(job, review_id)
        self._persist_review_mutation(job, before_approvals, before_actions)
        return job

    def apply_inline_review(self, *, job_id: str) -> DrawingCardJob:
        """Rerun only after every review row has an explicit decision."""
        job = self.get_job(job_id)
        if job.status != "review_required" or set(job.review_items) != set(job.inline_approvals):
            raise ValueError("unresolved review items remain")
        initial_review_rows = dict(job.review_rows)
        initial_inline_approvals = dict(job.inline_approvals)
        approvals_path = (
            self._attempt_directory(job, job.attempt + 1) / "inline_review_decisions.json"
        )
        approvals_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_approvals(approvals_path, job.inline_approvals)
        self._persist_job(job)
        rerun = self._run(job, review_decisions=approvals_path, strict=True)
        if rerun.status == "ready":
            append_feedback(
                self.workspace_root / "review-feedback.jsonl",
                initial_review_rows,
                initial_inline_approvals,
            )
        self._prune_terminal_jobs()
        return rerun

    def cancel_job(self, job_id: str) -> DrawingCardJob:
        """Request cooperative cancellation of a queued or active background job."""
        job = self.get_job(job_id)
        if job.status not in {"queued", "processing"}:
            raise ValueError("job cannot be cancelled")
        job.cancel_event.set()
        job.updated_at = _utc_now()
        self._persist_job(job)
        # A queued task can be made terminal without waiting for a worker slot.
        if job.status == "queued":
            self._finish_cancelled(job)
        return job

    def retry_job(self, job_id: str, *, background: bool | None = None) -> DrawingCardJob:
        """Start a fresh attempt without destroying earlier private artifacts."""
        job = self.get_job(job_id)
        if job.status not in {"cancelled", "failed", "blocked"}:
            raise ValueError("job cannot be retried")
        before = self._retry_snapshot(job)
        job.cancel_event = threading.Event()
        use_background = self.background if background is None else background
        job.status = "queued" if use_background else "processing"
        job.result = None
        job.result_hash = None
        job.review = None
        job.errors = ()
        job.summary = {}
        job.warnings = []
        job.warning_counts = {}
        job.blockers = []
        job.blocker_counts = {}
        job.funnel = {}
        job.schema_recognition = ()
        job.exclusion_audit = None
        job.review_items = {}
        job.review_rows = {}
        job.review_decisions = {}
        job.terminal_cause = None
        job.updated_at = _utc_now()
        attempt_directory = self._attempt_directory(job, job.attempt + 1)
        attempt_existed = attempt_directory.exists()
        decisions_path = self._retry_decisions_path(job)
        try:
            self._persist_job(job)
        except DrawingCardPersistenceError:
            self._restore_retry_snapshot(job, before)
            self._cleanup_retry_artifact(decisions_path, attempt_directory, attempt_existed)
            raise
        if use_background:
            self._schedule(job, review_decisions=decisions_path)
            return job
        return self._run(job, review_decisions=decisions_path)

    def _run(
        self,
        job: DrawingCardJob,
        *,
        review_decisions: Path | None = None,
        strict: bool = True,
    ) -> DrawingCardJob:
        if not _inputs_unchanged(job):
            job.status = "failed"
            job.errors = (_input_integrity_error(job),)
            job.terminal_cause = _normalize_terminal_cause(job.errors[0])
            job.updated_at = _utc_now()
            self._persist_job(job)
            return job
        if job.cancel_event.is_set():
            return self._finish_cancelled(job)
        job.status = "processing"
        job.errors = ()
        job.result = None
        job.result_hash = None
        job.run_count += 1
        job.attempt += 1
        attempt_directory = self._attempt_directory(job, job.attempt)
        attempt_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(attempt_directory, 0o700)
        output = attempt_directory / _RESULT_NAME
        job.phase = "upload"
        job.processed_files = 0
        job.processed_rows = 0
        job.total_files = len(job.sources)
        job.total_rows = None
        job.terminal_cause = None
        job.updated_at = _utc_now()
        self._persist_job(job)

        def on_progress(progress: object) -> None:
            phase = getattr(progress, "phase", "upload")
            job.phase = str(phase)
            job.processed_files = int(getattr(progress, "processed_files", 0))
            job.total_files = getattr(progress, "total_files", None)
            job.processed_rows = int(getattr(progress, "processed_rows", 0))
            job.total_rows = getattr(progress, "total_rows", None)
            job.started_at = str(getattr(progress, "started_at", job.started_at))
            job.updated_at = str(getattr(progress, "updated_at", _utc_now()))
            terminal_cause = getattr(progress, "terminal_cause", None)
            if terminal_cause is not None:
                job.terminal_cause = _normalize_terminal_cause(terminal_cause)
            self._persist_job(job)

        request = WorkflowRequest(
            inputs=job.sources,
            template=default_template_path() if job.mode == "create" else None,
            existing_card=job.existing_card,
            output=output,
            mode=job.mode,
            period=job.period,
            rag_mode=job.rag_mode,
            review_decisions=review_decisions,
            feedback_examples=self.workspace_root / "review-feedback.jsonl",
            machine_consensus=self._machine_consensus_path(),
            strict=strict,
            work_dir=attempt_directory / "runs",
            progress_callback=on_progress,
            cancel_requested=job.cancel_event.is_set,
        )
        try:
            result = self.runner(request)
        except DrawingCardWorkflowCancelled:
            return self._finish_cancelled(job)
        except Exception:
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
            output.unlink(missing_ok=True)
            job.terminal_cause = "processing_failed"
            job.updated_at = _utc_now()
            self._persist_job(job)
            return job
        if job.cancel_event.is_set():
            return self._finish_cancelled(job)
        if not _inside_job(result.work_dir, job):
            job.status = "failed"
            job.errors = ("UNSAFE_WORKSPACE",)
            job.terminal_cause = "unsafe_workspace"
            job.updated_at = _utc_now()
            self._persist_job(job)
            return job
        _private_tree(result.work_dir)
        job.summary = {
            "source_files": len(job.sources),
            "extracted_rows": result.extracted_row_count,
            "card_rows": len(result.card_rows),
            "manual_review": result.manual_review_count,
            "hierarchy_issues": len(result.hierarchy_issues),
        }
        job.funnel = dict(result.funnel)
        job.schema_recognition = tuple(dict(item) for item in result.schema_recognition)
        audit_path = result.work_dir / "row_dispositions.jsonl"
        job.exclusion_audit = (
            audit_path if audit_path.is_file() and _inside_job(audit_path, job) else None
        )
        job.warnings = _controlled_warnings(result.warnings)
        job.warning_counts = _controlled_warning_counts(result)
        job.blockers = _controlled_warnings(result.blockers)
        job.blocker_counts = {
            code: int(count)
            for code, count in result.blocker_counts.items()
            if code in job.blockers and int(count) > 0
        }
        if "MANUAL_REVIEW_REQUIRED" in job.blockers and result.manual_review_count:
            job.blocker_counts["MANUAL_REVIEW_REQUIRED"] = result.manual_review_count
        job.category_units = result.category_units
        job.review_items = inline_review_rows(
            result.source_rows, result.decisions, result.category_units
        )
        job.review_rows = {row.row_id: row for row in result.source_rows}
        job.review_decisions = {decision.row_id: decision for decision in result.decisions}
        job.funnel["manual_review_groups"] = len(self._current_clusters(job))
        job.cluster_actions.clear()
        if not _inputs_unchanged(job):
            job.status = "failed"
            job.errors = (_input_integrity_error(job),)
            output.unlink(missing_ok=True)
            job.terminal_cause = _normalize_terminal_cause(job.errors[0])
            job.updated_at = _utc_now()
            self._persist_job(job)
            return job
        review = result.work_dir / _REVIEW_NAME
        if result.manual_review_count and review.is_file() and _inside_job(review, job):
            if not _is_canonical_attempt_review(review, job):
                job.status = "failed"
                job.errors = ("UNSAFE_REVIEW",)
                job.terminal_cause = "unsafe_review"
                job.updated_at = _utc_now()
                self._persist_job(job)
                return job
            os.chmod(review, 0o600)
            job.review = review
            # A rerun can produce a different review set.  Its approvals must never
            # be inferred from decisions for the preceding set of rows.
            job.inline_approvals.clear()
            job.status = "review_required"
        elif (
            result.output_path is not None
            and result.output_path.is_file()
            and result.status in _PUBLISHABLE_WORKFLOW_STATUSES
        ):
            if not _inside_job(result.output_path, job):
                job.status = "failed"
                job.errors = ("UNSAFE_OUTPUT",)
                job.terminal_cause = "unsafe_output"
                job.updated_at = _utc_now()
                self._persist_job(job)
                return job
            if not _is_canonical_attempt_result(result.output_path, job):
                job.status = "failed"
                job.errors = ("UNSAFE_OUTPUT",)
                job.terminal_cause = "unsafe_output"
                job.updated_at = _utc_now()
                self._persist_job(job)
                return job
            os.chmod(result.output_path, 0o600)
            job.result = result.output_path
            job.result_hash = _digest(result.output_path.read_bytes())
            job.review = None
            job.status = "ready"
        elif result.status == "BLOCKED":
            job.status = "blocked"
            terminal_causes = tuple(
                code for code in ("NO_CARD_ROWS", "OUTPUT_BASE_MISSING") if code in job.warnings
            )
            job.errors = (*terminal_causes, "WORKFLOW_BLOCKED")
            job.terminal_cause = "workflow_blocked"
        else:
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
            job.terminal_cause = "processing_failed"
        job.phase = "ready" if job.status == "ready" else job.phase
        job.updated_at = _utc_now()
        self._persist_job(job)
        return job

    def _machine_consensus_path(self) -> Path | None:
        """Use one canonical private replay input; absence is the rollback switch."""
        path = self.workspace_root / _MACHINE_CONSENSUS_NAME
        return path if path.is_file() and not path.is_symlink() else None

    def _schedule(self, job: DrawingCardJob, *, review_decisions: Path | None = None) -> None:
        """Run one job off-request while keeping the direct API synchronous by default."""

        def worker() -> None:
            with self._worker_slots:
                if job.cancel_event.is_set():
                    self._finish_cancelled(job)
                    return
                self._run(job, review_decisions=review_decisions)
                self._prune_terminal_jobs()

        threading.Thread(target=worker, name=f"drawing-card-{job.job_id}", daemon=True).start()

    def _schedule_review_recovery(self, job: DrawingCardJob) -> None:
        """Rebuild private review context from retained sources after restart."""
        approvals = dict(job.inline_approvals)
        job.status = "queued"
        decisions_path = self._retry_decisions_path(job)
        self._persist_job(job)

        def worker() -> None:
            with self._worker_slots:
                recovered = self._run(job, review_decisions=decisions_path)
                if recovered.status == "review_required":
                    recovered.inline_approvals = {
                        row_id: approval
                        for row_id, approval in approvals.items()
                        if row_id in recovered.review_items
                    }
                    self._persist_job(recovered)

        threading.Thread(
            target=worker, name=f"drawing-card-recovery-{job.job_id}", daemon=True
        ).start()

    def _attempt_directory(self, job: DrawingCardJob, attempt: int) -> Path:
        return job.directory / "attempts" / f"{attempt:04d}"

    def _retry_decisions_path(self, job: DrawingCardJob) -> Path | None:
        if not job.inline_approvals:
            return None
        path = self._attempt_directory(job, job.attempt + 1) / "inline_review_decisions.json"
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write_approvals(path, job.inline_approvals)
        return path

    @staticmethod
    def _cleanup_retry_artifact(
        decisions_path: Path | None, attempt_directory: Path, attempt_existed: bool
    ) -> None:
        if decisions_path is not None:
            decisions_path.unlink(missing_ok=True)
        if not attempt_existed:
            with suppress(OSError):
                attempt_directory.rmdir()

    @staticmethod
    def _retry_snapshot(job: DrawingCardJob) -> dict[str, object]:
        """Capture every retry-mutated field before its durable state transition."""
        return {
            "cancel_event": job.cancel_event,
            "status": job.status,
            "result": job.result,
            "result_hash": job.result_hash,
            "review": job.review,
            "errors": job.errors,
            "summary": job.summary,
            "warnings": job.warnings,
            "warning_counts": job.warning_counts,
            "blockers": job.blockers,
            "blocker_counts": job.blocker_counts,
            "funnel": job.funnel,
            "schema_recognition": job.schema_recognition,
            "exclusion_audit": job.exclusion_audit,
            "review_items": job.review_items,
            "review_rows": job.review_rows,
            "review_decisions": job.review_decisions,
            "terminal_cause": job.terminal_cause,
            "updated_at": job.updated_at,
        }

    @staticmethod
    def _restore_retry_snapshot(job: DrawingCardJob, snapshot: dict[str, object]) -> None:
        for field_name, value in snapshot.items():
            setattr(job, field_name, value)

    def _finish_cancelled(self, job: DrawingCardJob) -> DrawingCardJob:
        attempt = self._attempt_directory(job, job.attempt) if job.attempt else None
        if attempt is not None:
            for path in attempt.rglob("*"):
                if path.is_file() and path.name in {_RESULT_NAME, _REVIEW_NAME}:
                    path.unlink(missing_ok=True)
        job.result = None
        job.result_hash = None
        job.review = None
        job.status = "cancelled"
        job.errors = ("CANCELLED",)
        job.terminal_cause = "cancelled"
        job.updated_at = _utc_now()
        self._persist_job(job)
        return job

    def _persist_job(self, job: DrawingCardJob) -> None:
        """Commit a bounded, path-relative private snapshot before returning state."""
        try:
            self._store.save(job.job_id, self._manifest_for(job))
        except (OSError, ValueError) as error:
            raise DrawingCardPersistenceError("drawing-card state was not saved") from error

    def _persist_review_mutation(
        self,
        job: DrawingCardJob,
        approvals: dict[str, ReviewApproval],
        cluster_actions: dict[str, dict[str, ReviewApproval]],
    ) -> None:
        try:
            self._persist_job(job)
        except DrawingCardPersistenceError:
            job.inline_approvals = approvals
            job.cluster_actions = cluster_actions
            raise

    def _manifest_for(self, job: DrawingCardJob) -> dict[str, object]:
        def relative(path: Path | None) -> str | None:
            if path is None or not _inside_job(path, job):
                return None
            return path.resolve().relative_to(job.directory.resolve()).as_posix()

        return {
            "contract": MANIFEST_CONTRACT,
            "job_id": job.job_id,
            "mode": job.mode,
            "period": job.period,
            "rag_mode": job.rag_mode,
            "source_paths": [relative(path) for path in job.sources],
            "source_hashes": list(job.source_hashes),
            "existing_card_path": relative(job.existing_card),
            "existing_card_hash": job.existing_card_hash,
            "existing_name": job.existing_name,
            "status": job.status,
            "result_path": relative(job.result),
            "result_hash": job.result_hash,
            "review_path": relative(job.review),
            "exclusion_audit_path": relative(job.exclusion_audit),
            "attempt": job.attempt,
            "run_count": job.run_count,
            "phase": job.phase,
            "processed_files": job.processed_files,
            "total_files": job.total_files,
            "processed_rows": job.processed_rows,
            "total_rows": job.total_rows,
            "started_at": job.started_at,
            "updated_at": job.updated_at,
            "terminal_cause": job.terminal_cause,
            "cancel_requested": job.cancel_event.is_set(),
            "idempotency_key": job.idempotency_key,
            "errors": list(job.errors),
            "summary": _safe_summary(job.summary),
            "warnings": list(job.warnings),
            "warning_counts": {key: int(value) for key, value in job.warning_counts.items()},
            "blockers": list(job.blockers),
            "blocker_counts": {key: int(value) for key, value in job.blocker_counts.items()},
            "funnel": _safe_funnel(job.funnel),
            "inline_approvals": {
                review_id: {
                    "action": approval.action,
                    "category": approval.category.value if approval.category else None,
                }
                for review_id, approval in job.inline_approvals.items()
            },
        }

    def _restore_jobs(self) -> None:
        for job_id, manifest in self._store.load_all(
            terminal_retention=MAX_RETAINED_TERMINAL_JOBS
        ).items():
            try:
                job = self._job_from_manifest(job_id, manifest)
            except (OSError, TypeError, ValueError):
                continue
            # A hostile or stale duplicate manifest must not resurrect a second
            # active worker for the same client request.
            if job.idempotency_key and job.idempotency_key in self._idempotency:
                self._store.delete(job_id)
                continue
            self._jobs[job_id] = job
            if job.idempotency_key:
                self._idempotency[job.idempotency_key] = job_id
            if job.cancel_event.is_set():
                self._finish_cancelled(job)
            elif self.background and job.status in {"queued", "processing"}:
                job.status = "queued"
                self._schedule(job)
            elif self.background and job.status == "review_required":
                self._schedule_review_recovery(job)
        self._prune_terminal_jobs()

    def _job_from_manifest(self, job_id: str, manifest: dict[str, object]) -> DrawingCardJob:
        directory = self.workspace_root / job_id
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("unsafe job directory")
        source_paths = tuple(
            _restored_path(directory, value) for value in _required_list(manifest, "source_paths")
        )
        hashes = tuple(str(value) for value in _required_list(manifest, "source_hashes"))
        if (
            len(source_paths) != len(hashes)
            or not source_paths
            or not all(path.is_file() and not path.is_symlink() for path in source_paths)
        ):
            raise ValueError("unsafe source paths")
        job = DrawingCardJob(
            job_id=job_id,
            directory=directory,
            sources=source_paths,
            source_hashes=hashes,
            mode=_manifest_mode(manifest.get("mode")),
            period=_validate_period(manifest.get("period")),
            existing_card=_optional_restored_path(directory, manifest.get("existing_card_path")),
            existing_card_hash=_optional_digest(manifest.get("existing_card_hash")),
            existing_name=_safe_existing_name(manifest.get("existing_name")),
            status=_manifest_status(manifest.get("status")),
            rag_mode=_manifest_rag_mode(manifest.get("rag_mode")),
            attempt=_bounded_int(manifest.get("attempt")),
            run_count=_bounded_int(manifest.get("run_count")),
            phase=str(manifest.get("phase", "upload"))[:64],
            processed_files=_bounded_int(manifest.get("processed_files")),
            total_files=_optional_bounded_int(manifest.get("total_files")),
            processed_rows=_bounded_int(manifest.get("processed_rows")),
            total_rows=_optional_bounded_int(manifest.get("total_rows")),
            started_at=_safe_timestamp(manifest.get("started_at")),
            updated_at=_safe_timestamp(manifest.get("updated_at")),
            terminal_cause=_safe_terminal(manifest.get("terminal_cause")),
            idempotency_key=_validate_idempotency_key(manifest.get("idempotency_key")),
            errors=tuple(_safe_codes(manifest.get("errors"))),
            summary=_safe_summary(manifest.get("summary")),
            warnings=_safe_codes(manifest.get("warnings")),
            warning_counts=_safe_int_map(manifest.get("warning_counts")),
            blockers=_safe_codes(manifest.get("blockers")),
            blocker_counts=_safe_int_map(manifest.get("blocker_counts")),
            funnel=_safe_funnel(manifest.get("funnel")),
        )
        if _manifest_cancel_requested(manifest.get("cancel_requested")):
            job.cancel_event.set()
        job.result = _optional_restored_path(directory, manifest.get("result_path"))
        job.result_hash = _optional_digest(manifest.get("result_hash"))
        if job.result is not None and (not job.result.is_file() or job.result.is_symlink()):
            raise ValueError("unsafe result path")
        job.review = _optional_restored_path(directory, manifest.get("review_path"))
        if job.review is not None and (not job.review.is_file() or job.review.is_symlink()):
            raise ValueError("unsafe review path")
        job.exclusion_audit = _optional_restored_path(
            directory, manifest.get("exclusion_audit_path")
        )
        if job.exclusion_audit is not None and (
            not job.exclusion_audit.is_file() or job.exclusion_audit.is_symlink()
        ):
            raise ValueError("unsafe audit path")
        if job.existing_card is not None and (
            not job.existing_card.is_file() or job.existing_card.is_symlink()
        ):
            raise ValueError("unsafe existing card")
        if job.mode == "update" and (
            job.existing_card is None
            or job.existing_card_hash is None
            or not _existing_card_unchanged(job)
        ):
            raise ValueError("existing card hash changed")
        if job.mode == "create" and (
            job.existing_card is not None or job.existing_card_hash is not None
        ):
            raise ValueError("create job has an existing card")
        if job.status == "ready" and (
            job.result is None
            or job.result_hash is None
            or not _is_canonical_attempt_result(job.result, job)
            or _digest(job.result.read_bytes()) != job.result_hash
        ):
            raise ValueError("ready job has an unsafe result")
        if (
            job.status == "review_required"
            and job.review is not None
            and not _is_canonical_attempt_review(job.review, job)
        ):
            raise ValueError("review job has an unsafe review")
        if job.status != "review_required" and job.review is not None:
            raise ValueError("non-review job has a review artifact")
        for review_id, raw in _safe_approval_map(manifest.get("inline_approvals")).items():
            job.inline_approvals[review_id] = review_approval(
                review_id, raw["action"], raw["category"]
            )
        if not _inputs_unchanged(job):
            raise ValueError("source hash changed")
        return job

    @staticmethod
    def _current_clusters(job: DrawingCardJob) -> tuple[ReviewCluster, ...]:
        return build_review_clusters(job.review_rows, job.review_decisions)

    @staticmethod
    def _cluster_resolved(job: DrawingCardJob, cluster: ReviewCluster) -> bool:
        return set(cluster.member_ids) <= set(job.inline_approvals)

    def _require_current_cluster(
        self, job: DrawingCardJob, cluster_id: str, version: str
    ) -> ReviewCluster:
        if not isinstance(cluster_id, str) or cluster_id != version:
            raise ValueError("stale cluster identity")
        for cluster in self._current_clusters(job):
            if cluster.cluster_id == cluster_id:
                return cluster
        raise ValueError("stale cluster identity")

    def _cluster_payload(self, job: DrawingCardJob, cluster: ReviewCluster) -> dict[str, object]:
        return drawing_card_cluster_payload(
            cluster=cluster,
            rows=job.review_rows,
            approvals=job.inline_approvals,
            category_units=job.category_units,
        )

    @staticmethod
    def _discard_cluster_actions_for(job: DrawingCardJob, review_id: str) -> None:
        for cluster_id, approvals in tuple(job.cluster_actions.items()):
            if review_id in approvals:
                job.cluster_actions.pop(cluster_id, None)


def _validate_sources(sources: object, *, existing_content: bytes | None = None) -> None:
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES:
        raise ValueError("provide from 1 to 32 source workbooks")
    total_size = 0
    for name, content in sources:
        _validate_workbook(name, content, allowed_suffixes=_SOURCE_SUFFIXES)
        total_size += len(content)
    if (
        total_size + (len(existing_content) if existing_content is not None else 0)
        > MAX_UPLOAD_BYTES
    ):
        raise ValueError("combined upload is too large")


def _validate_existing(name: str, content: bytes) -> None:
    _validate_workbook(name, content, allowed_suffixes={".xlsx"})


def _validate_review(name: str, content: bytes) -> None:
    _validate_workbook(name, content, allowed_suffixes={".xlsx"})


def _validate_workbook(name: object, content: object, *, allowed_suffixes: set[str]) -> None:
    if not isinstance(name, str) or not name or "\x00" in name:
        raise ValueError("invalid filename")
    if Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("invalid filename")
    suffix = Path(name).suffix.casefold()
    if suffix not in allowed_suffixes:
        raise ValueError("unsupported workbook type")
    if not isinstance(content, bytes) or not content or len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("invalid workbook content")
    if not content.startswith(_ZIP_SIGNATURES):
        raise ValueError("invalid workbook content")


def _validate_period(period: str | None) -> str | None:
    if period is None:
        return None
    if not isinstance(period, str) or not (clean := period.strip()) or len(clean) > 64:
        raise ValueError("invalid period")
    if match := _CANONICAL_PERIOD_RE.fullmatch(clean):
        year, month = match.group("year"), match.group("month")
    elif match := _RUSSIAN_PERIOD_RE.fullmatch(clean):
        year = match.group("year")
        month = str(MONTHS[match.group("month").casefold()])
    else:
        raise ValueError("invalid period")
    try:
        return DocumentPeriod(year=int(year), month=int(month)).normalized
    except ValueError as error:
        raise ValueError("invalid period") from error


def _write_private(path: Path, content: bytes) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    with path.open("xb") as stream:
        stream.write(content)
    os.chmod(path, 0o600)
    return path


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _optional_digest(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("invalid persisted digest")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _validate_idempotency_key(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", value):
        raise ValueError("invalid idempotency key")
    return value


def _manifest_cancel_requested(value: object) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError("invalid persisted cancellation state")
    return value


def _required_list(manifest: dict[str, object], key: str) -> list[object]:
    value = manifest.get(key)
    if not isinstance(value, list):
        raise ValueError(f"invalid {key}")
    return value


def _restored_path(directory: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("invalid restored path")
    candidate = directory / value
    try:
        if not candidate.resolve().is_relative_to(directory.resolve()):
            raise ValueError("restored path escapes job")
    except OSError as error:
        raise ValueError("unsafe restored path") from error
    return candidate


def _optional_restored_path(directory: Path, value: object) -> Path | None:
    return None if value is None else _restored_path(directory, value)


def _bounded_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10_000_000:
        raise ValueError("invalid persisted counter")
    return value


def _optional_bounded_int(value: object) -> int | None:
    return None if value is None else _bounded_int(value)


def _manifest_mode(value: object) -> Literal["create", "update"]:
    if value not in {"create", "update"}:
        raise ValueError("invalid persisted mode")
    return value


def _manifest_rag_mode(value: object) -> Literal["off", "semantic"]:
    if value not in {"off", "semantic"}:
        raise ValueError("invalid persisted rag mode")
    return value


def _manifest_status(value: object) -> str:
    allowed = {"queued", "processing", "ready", "review_required", "failed", "blocked", "cancelled"}
    if value not in allowed:
        raise ValueError("invalid persisted status")
    return str(value)


def _safe_timestamp(value: object) -> str:
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError("invalid persisted timestamp")
    return value


def _safe_terminal(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", value):
        raise ValueError("invalid terminal cause")
    return value


def _normalize_terminal_cause(value: object) -> str:
    """Turn workflow enums/codes into the persisted lowercase terminal vocabulary."""
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")
    return normalized[:64] if normalized else "unknown"


def _safe_codes(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("invalid persisted codes")
    return [
        str(item)
        for item in value
        if isinstance(item, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", item)
    ][:50]


def _safe_int_map(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("invalid persisted counters")
    return {
        key: count
        for key, raw in value.items()
        if isinstance(key, str)
        and re.fullmatch(r"[A-Z][A-Z0-9_]*", key)
        and isinstance(raw, int)
        and not isinstance(raw, bool)
        and 0 <= (count := raw) <= 10_000_000
    }


def _safe_summary(value: object) -> dict[str, int]:
    allowed = {
        "source_files",
        "extracted_rows",
        "card_rows",
        "manual_review",
        "hierarchy_issues",
    }
    if not isinstance(value, dict):
        return {}
    return {
        key: count
        for key, raw in value.items()
        if key in allowed
        and isinstance(raw, int)
        and not isinstance(raw, bool)
        and 0 <= (count := raw) <= 10_000_000
    }


def _safe_existing_name(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or Path(value).name != value or "\x00" in value:
        raise ValueError("invalid persisted existing name")
    return value


def _safe_funnel(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    # Funnel is operational metadata only.  Keep string keys and scalar counts;
    # no row payload, path or workbook value can survive a restart snapshot.
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str)
        and len(key) <= 96
        and isinstance(item, (str, int, float, bool, type(None)))
    }


def _safe_approval_map(value: object) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, str | None]] = {}
    for review_id, raw in value.items():
        if not isinstance(review_id, str) or len(review_id) > 256 or not isinstance(raw, dict):
            continue
        action, category = raw.get("action"), raw.get("category")
        if isinstance(action, str) and (category is None or isinstance(category, str)):
            result[review_id] = {"action": action, "category": category}
    return result


def _same_idempotent_request(
    job: DrawingCardJob,
    *,
    sources: list[tuple[str, bytes]],
    mode: Literal["create", "update"],
    period: str | None,
    rag_mode: Literal["off", "semantic"],
    existing_name: str | None,
    existing_content: bytes | None,
) -> bool:
    return (
        job.source_hashes == tuple(_digest(content) for _name, content in sources)
        and tuple(path.name.partition("-")[2] for path in job.sources)
        == tuple(name for name, _content in sources)
        and job.mode == mode
        and job.period == period
        and job.rag_mode == rag_mode
        and job.existing_name == existing_name
        and (
            (job.existing_card is None and existing_content is None)
            or (
                job.existing_card is not None
                and existing_content is not None
                and _digest(job.existing_card.read_bytes()) == _digest(existing_content)
            )
        )
    )


def _sources_unchanged(job: DrawingCardJob) -> bool:
    try:
        return tuple(_digest(path.read_bytes()) for path in job.sources) == job.source_hashes
    except OSError:
        return False


def _existing_card_unchanged(job: DrawingCardJob) -> bool:
    if job.mode == "create":
        return job.existing_card is None and job.existing_card_hash is None
    try:
        return (
            job.existing_card is not None
            and job.existing_card_hash is not None
            and _digest(job.existing_card.read_bytes()) == job.existing_card_hash
        )
    except OSError:
        return False


def _inputs_unchanged(job: DrawingCardJob) -> bool:
    return _sources_unchanged(job) and _existing_card_unchanged(job)


def _input_integrity_error(job: DrawingCardJob) -> str:
    return (
        "EXISTING_CARD_HASH_CHANGED" if not _existing_card_unchanged(job) else "SOURCE_HASH_CHANGED"
    )


def _is_canonical_attempt_result(path: Path, job: DrawingCardJob) -> bool:
    expected = job.directory / "attempts" / f"{job.attempt:04d}" / _RESULT_NAME
    try:
        return (
            expected.is_file()
            and not _has_symlink_component(expected, job.directory)
            and path.resolve() == expected.resolve()
        )
    except OSError:
        return False


def _is_canonical_attempt_review(path: Path, job: DrawingCardJob) -> bool:
    """Accept only a non-symlinked review workbook from the current run."""
    try:
        relative = path.resolve().relative_to(job.directory.resolve())
        expected_prefix = ("attempts", f"{job.attempt:04d}", "runs")
        return (
            len(relative.parts) == 5
            and relative.parts[:3] == expected_prefix
            and relative.name == _REVIEW_NAME
            and path.is_file()
            and not _has_symlink_component(job.directory / relative, job.directory)
        )
    except (OSError, ValueError):
        return False


def _has_symlink_component(path: Path, root: Path) -> bool:
    """Reject symlinks below ``root`` while allowing platform root aliases."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            return True
    return False


def _private_tree(directory: Path) -> None:
    """Apply private permissions after a workflow produces local artifacts."""
    if not directory.is_dir():
        return
    for path in directory.rglob("*"):
        if path.is_dir():
            os.chmod(path, 0o700)
        elif path.is_file():
            os.chmod(path, 0o600)
    os.chmod(directory, 0o700)


def _inside_job(path: Path, job: DrawingCardJob) -> bool:
    try:
        return path.resolve().is_relative_to(job.directory.resolve())
    except OSError:
        return False


def _controlled_warnings(warnings: list[str]) -> list[str]:
    codes = (_controlled_warning_code(item) for item in warnings)
    return list(dict.fromkeys(code for code in codes if code))[:50]


def _controlled_warning_counts(result: WorkflowResult) -> dict[str, int]:
    codes = (_controlled_warning_code(item) for item in result.warnings)
    counts = Counter(code for code in codes if code)
    hierarchy_counts = Counter(
        str(getattr(issue, "code", ""))
        for issue in result.hierarchy_issues
        if getattr(issue, "code", None)
    )
    counts.update({code: 0 for code in hierarchy_counts})
    for code, count in hierarchy_counts.items():
        counts[code] = count
    if result.manual_review_count:
        counts["MANUAL_REVIEW_REQUIRED"] = result.manual_review_count
    return {code: int(count) for code, count in counts.most_common(50)}


def _controlled_warning_code(item: object) -> str | None:
    code = str(item).partition(":")[0]
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]*", code) else None


def _controlled_exclusion_record(raw: dict[str, object]) -> dict[str, object]:
    """Whitelist the user-facing exclusion fields; never return paths or cell contents."""
    hazards = raw.get("hazard_flags")
    return {
        "row_id": str(raw.get("row_id", ""))[:128],
        "disposition": str(raw.get("disposition", ""))[:64],
        "reason_code": str(raw.get("reason_code", ""))[:64],
        "rule_id": str(raw["rule_id"])[:128] if raw.get("rule_id") is not None else None,
        "filename": Path(str(raw.get("safe_basename", ""))).name[:255],
        "sheet_name": str(raw.get("sheet_name", ""))[:255],
        "row_number": int(raw.get("row_number", 0)),
        "position_code": (
            str(raw["position_code"])[:128] if raw.get("position_code") is not None else None
        ),
        "row_role": str(raw.get("row_role", "unknown"))[:64],
        "hazard_flags": [
            code for item in hazards if (code := _controlled_warning_code(item)) is not None
        ][:20]
        if isinstance(hazards, list)
        else [],
    }


def _first_category_unit(category_units: dict[str, tuple[str, ...]], category: str) -> str | None:
    units = category_units.get(category, ())
    return units[0] if units else None

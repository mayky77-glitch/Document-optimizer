"""Private, in-memory lifecycle for deterministic drawing-card jobs."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

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
    status: str = "processing"
    result: Path | None = None
    review: Path | None = None
    errors: tuple[str, ...] = ()
    summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    warning_counts: dict[str, int] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    blocker_counts: dict[str, int] = field(default_factory=dict)
    category_units: dict[str, tuple[str, ...]] = field(default_factory=dict)
    review_items: dict[str, dict[str, object]] = field(default_factory=dict)
    review_rows: dict[str, DrawingSourceRow] = field(default_factory=dict, repr=False)
    review_decisions: dict[str, MatchDecision] = field(default_factory=dict, repr=False)
    inline_approvals: dict[str, ReviewApproval] = field(default_factory=dict, repr=False)
    cluster_actions: dict[str, dict[str, ReviewApproval]] = field(default_factory=dict, repr=False)
    rag_mode: Literal["off", "semantic"] = "semantic"
    run_count: int = 0

    def __repr__(self) -> str:
        return (
            "DrawingCardJob("
            f"job_id={self.job_id!r}, status={self.status!r}, "
            f"mode={self.mode!r}, run_count={self.run_count!r})"
        )

    @property
    def result_available(self) -> bool:
        return self.status == "ready" and self.result is not None and self.result.is_file()


class DrawingCardService:
    """Keep uploaded sources and all workflow artifacts in an opaque private job."""

    def __init__(
        self,
        workspace_root: Path,
        runner: Callable[[WorkflowRequest], WorkflowResult] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)
        self.runner = runner or run_workflow
        self._jobs: dict[str, DrawingCardJob] = {}

    def create_job(
        self,
        *,
        sources: list[tuple[str, bytes]],
        mode: Literal["create", "update"] = "create",
        existing_name: str | None = None,
        existing_content: bytes | None = None,
        period: str | None = None,
        rag_mode: Literal["off", "semantic"] = "semantic",
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

        job_id = secrets.token_urlsafe(18)
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
                rag_mode=rag_mode,
            )
            self._jobs[job_id] = job
            result = self._run(job)
            self._prune_terminal_jobs()
            return result
        except Exception:
            self._jobs.pop(job_id, None)
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
        terminal = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in {"ready", "failed", "blocked"}
        ]
        active_count = len(self._jobs) - len(terminal)
        terminal_limit = max(0, MAX_RETAINED_TERMINAL_JOBS - active_count)
        for job_id in terminal[:-terminal_limit] if terminal_limit else terminal:
            self._jobs.pop(job_id, None)

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
        job.inline_approvals.update(approvals)
        job.cluster_actions[cluster.cluster_id] = approvals
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
        for row_id in applied:
            job.inline_approvals.pop(row_id, None)
        job.cluster_actions.pop(cluster.cluster_id, None)
        return job

    def put_review_item(
        self, *, job_id: str, review_id: str, action: str, category: str | None = None
    ) -> DrawingCardJob:
        """Create or replace one decision; replacement makes a choice reversible."""
        job = self.get_job(job_id)
        if job.status != "review_required" or review_id not in job.review_items:
            raise ValueError("unknown review item")
        job.inline_approvals[review_id] = review_approval(review_id, action, category)
        self._discard_cluster_actions_for(job, review_id)
        return job

    def delete_review_item(self, *, job_id: str, review_id: str) -> DrawingCardJob:
        job = self.get_job(job_id)
        if review_id not in job.review_items:
            raise ValueError("unknown review item")
        job.inline_approvals.pop(review_id, None)
        self._discard_cluster_actions_for(job, review_id)
        return job

    def bulk_review(self, *, job_id: str, action: str) -> DrawingCardJob:
        """Apply a reversible bulk decision only where a category was proposed."""
        if action not in {"approve_all_proposed", "reject_all"}:
            raise ValueError("unsupported bulk review action")
        job = self.get_job(job_id)
        if job.status != "review_required":
            raise ValueError("job does not await inline review")
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
        return job

    def apply_inline_review(self, *, job_id: str) -> DrawingCardJob:
        """Rerun only after every review row has an explicit decision."""
        job = self.get_job(job_id)
        if job.status != "review_required" or set(job.review_items) != set(job.inline_approvals):
            raise ValueError("unresolved review items remain")
        initial_review_rows = dict(job.review_rows)
        initial_inline_approvals = dict(job.inline_approvals)
        approvals_path = job.directory / "inline_review_decisions.json"
        write_approvals(approvals_path, job.inline_approvals)
        rerun = self._run(job, review_decisions=approvals_path, strict=True)
        if rerun.status == "ready":
            append_feedback(
                self.workspace_root / "review-feedback.jsonl",
                initial_review_rows,
                initial_inline_approvals,
            )
        self._prune_terminal_jobs()
        return rerun

    def _run(
        self,
        job: DrawingCardJob,
        *,
        review_decisions: Path | None = None,
        strict: bool = True,
    ) -> DrawingCardJob:
        if not _sources_unchanged(job):
            job.status = "failed"
            job.errors = ("SOURCE_HASH_CHANGED",)
            return job
        job.status = "processing"
        job.errors = ()
        job.result = None
        job.run_count += 1
        output = job.directory / _RESULT_NAME
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
            work_dir=job.directory / "runs",
        )
        try:
            result = self.runner(request)
        except Exception:
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
            output.unlink(missing_ok=True)
            return job
        if not _inside_job(result.work_dir, job):
            job.status = "failed"
            job.errors = ("UNSAFE_WORKSPACE",)
            return job
        _private_tree(result.work_dir)
        job.summary = {
            "source_files": len(job.sources),
            "extracted_rows": result.extracted_row_count,
            "card_rows": len(result.card_rows),
            "manual_review": result.manual_review_count,
            "hierarchy_issues": len(result.hierarchy_issues),
        }
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
        job.cluster_actions.clear()
        if not _sources_unchanged(job):
            job.status = "failed"
            job.errors = ("SOURCE_HASH_CHANGED",)
            output.unlink(missing_ok=True)
            return job
        review = result.work_dir / _REVIEW_NAME
        if result.manual_review_count and review.is_file() and _inside_job(review, job):
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
                return job
            os.chmod(result.output_path, 0o600)
            job.result = result.output_path
            job.review = None
            job.status = "ready"
        elif result.status == "BLOCKED":
            job.status = "blocked"
            terminal_causes = tuple(
                code for code in ("NO_CARD_ROWS", "OUTPUT_BASE_MISSING") if code in job.warnings
            )
            job.errors = (*terminal_causes, "WORKFLOW_BLOCKED")
        else:
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
        return job

    def _machine_consensus_path(self) -> Path | None:
        """Use one canonical private replay input; absence is the rollback switch."""
        path = self.workspace_root / _MACHINE_CONSENSUS_NAME
        return path if path.is_file() and not path.is_symlink() else None

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


def _sources_unchanged(job: DrawingCardJob) -> bool:
    return tuple(_digest(path.read_bytes()) for path in job.sources) == job.source_hashes


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


def _first_category_unit(category_units: dict[str, tuple[str, ...]], category: str) -> str | None:
    units = category_units.get(category, ())
    return units[0] if units else None

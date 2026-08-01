"""Private job lifecycle and the public processing execution boundary."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import shutil
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .presentation import journal_payload, processing_presentation

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_SOURCES = 32
MAX_RETAINED_TERMINAL_JOBS = 64
MAX_MANUAL_DISCREPANCY_DECISIONS = 5_000
_ALLOWED_SUFFIXES = {".xlsx", ".xlsm"}
_ALLOWED_MODES = {"inspect", "dry-run", "write"}
_STAGE_PATTERN = re.compile(r"^[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё._ -]{0,63}$")
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
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
    sources: tuple[Path, ...] = ()
    source_digests: tuple[str, ...] = ()
    status: str = "pending"
    output: Path | None = None
    summary: dict[str, object] = field(default_factory=dict)
    discrepancies: list[dict[str, object]] = field(default_factory=list)
    suggestions: list[dict[str, object]] = field(default_factory=list)
    decisions: list[dict[str, str]] = field(default_factory=list)
    errors: tuple[str, ...] = ()
    result_name: str | None = None

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
        self.execute = execute or _default_execute
        self.jobs: dict[str, AdminJob] = {}
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)

    def create_job(
        self,
        *,
        source_name: str | None = None,
        source_content: bytes | None = None,
        sources: list[tuple[str, bytes]] | None = None,
        target_name: str,
        target_content: bytes,
        stage: str,
        mode: str = "write",
    ) -> AdminJob:
        upload_sources = _validated_sources(sources, source_name, source_content)
        validate_workbook_upload(target_name, target_content)
        if (
            sum(len(content) for _name, content in upload_sources) + len(target_content)
            > MAX_UPLOAD_BYTES
        ):
            raise ValueError("combined upload is too large")
        clean_stage = validate_stage(stage)
        clean_mode = validate_mode(mode)
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
            job = AdminJob(
                job_id=job_id,
                directory=directory,
                source=source_paths[0],
                target=target,
                stage=clean_stage,
                mode=clean_mode,
                source_digest=_digest(upload_sources[0][1]),
                target_digest=_digest(target_content),
                sources=source_paths,
                source_digests=tuple(_digest(content) for _name, content in upload_sources),
            )
            self.jobs[job_id] = job
            registered = True
            result = self.run(job_id)
            self._prune_terminal_jobs()
            return result
        except (OSError, TypeError, ValueError):
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
            execution_result = self.execute(job)
            self._apply_execution_result(job, execution_result)
            _verify_inputs(job)
        except (OSError, TypeError, ValueError, RuntimeError):
            _remove_partial_output(job)
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
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

    def record_manual_discrepancy_decision(
        self,
        *,
        job_id: str,
        group_id: str,
        discrepancy_ids: list[str],
        decision: str,
    ) -> AdminJob:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("group is required")
        if not isinstance(discrepancy_ids, list) or not discrepancy_ids:
            raise ValueError("discrepancy IDs are required")
        if len(discrepancy_ids) > MAX_MANUAL_DISCREPANCY_DECISIONS:
            raise ValueError("too many discrepancy IDs")
        if any(not isinstance(item, str) or not item for item in discrepancy_ids):
            raise ValueError("invalid discrepancy ID")
        if len(set(discrepancy_ids)) != len(discrepancy_ids):
            raise ValueError("duplicate discrepancy ID")
        job = self.get_job(job_id)
        from .presentation import manual_review_groups

        groups = manual_review_groups(job.discrepancies, job.decisions)
        group = next((item for item in groups if item["group_id"] == group_id), None)
        if group is None or set(discrepancy_ids) != set(group["discrepancy_ids"]):
            raise ValueError("decision must match one open group exactly")
        # All validation occurs before mutation so rejected requests remain atomic.
        job.decisions.extend(
            {
                "discrepancy_id": discrepancy_id,
                "decision": decision,
                "effect": "review_journal_only",
            }
            for discrepancy_id in discrepancy_ids
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


def _has_unresolved_reviews(job: AdminJob) -> bool:
    return bool(job.unresolved_suggestion_ids or job.unresolved_manual_discrepancy_ids)


def validate_workbook_upload(name: str, content: bytes) -> None:
    if not isinstance(name, str) or not name or "\x00" in name or not _safe_basename(name):
        raise ValueError("invalid filename")
    if Path(name).suffix.casefold() not in _ALLOWED_SUFFIXES:
        raise ValueError("only .xlsx and .xlsm workbooks are accepted")
    if not isinstance(content, bytes) or not content:
        raise ValueError("empty upload")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("upload too large")
    if not content.startswith(_ZIP_SIGNATURES):
        raise ValueError("invalid Excel container signature")


def validate_stage(stage: object) -> str:
    if not isinstance(stage, str):
        raise ValueError("invalid stage")
    clean = stage.strip()
    if not _STAGE_PATTERN.fullmatch(clean):
        raise ValueError("invalid stage")
    return clean


def validate_mode(mode: object) -> str:
    if not isinstance(mode, str) or mode not in _ALLOWED_MODES:
        raise ValueError("invalid mode")
    return mode


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


def _verify_inputs(job: AdminJob) -> None:
    sources = job.sources or (job.source,)
    digests = job.source_digests or (job.source_digest,)
    if len(sources) != len(digests) or any(
        _file_digest(source) != digest for source, digest in zip(sources, digests, strict=True)
    ):
        raise RuntimeError("source upload changed during processing")
    if _file_digest(job.target) != job.target_digest:
        raise RuntimeError("target upload changed during processing")


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _exit_code(result: object) -> int:
    value = getattr(result, "exit_code", -1)
    return int(value.value if hasattr(value, "value") else value)


def _remove_partial_output(job: AdminJob) -> None:
    candidate = job.directory / "result.xlsx"
    candidate.unlink(missing_ok=True)
    job.output = None
    job.result_name = None


def _validated_sources(
    sources: list[tuple[str, bytes]] | None,
    source_name: str | None,
    source_content: bytes | None,
) -> list[tuple[str, bytes]]:
    """Accept the legacy singular upload or the bounded bulk contract, never both."""
    if sources is not None and (source_name is not None or source_content is not None):
        raise ValueError("provide sources or legacy source_name/source_content, not both")
    values = sources if sources is not None else [(source_name, source_content)]
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_SOURCES:
        raise ValueError("provide from 1 to 32 source workbooks")
    validated: list[tuple[str, bytes]] = []
    basenames: set[str] = set()
    for value in values:
        if not isinstance(value, tuple) or len(value) != 2:
            raise ValueError("invalid source upload")
        name, content = value
        validate_workbook_upload(name, content)
        basename = unicodedata.normalize("NFC", name)
        canonical_name = basename.casefold()
        if canonical_name in basenames:
            raise ValueError("duplicate source filename")
        basenames.add(canonical_name)
        validated.append((basename, content))
    return sorted(validated, key=lambda item: (item[0].casefold(), _digest(item[1])))


def _safe_basename(name: str) -> bool:
    return name == Path(name).name and "/" not in name and "\\" not in name

"""Private, in-memory lifecycle for deterministic drawing-card jobs."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from report_processor.drawing_card.models import WorkflowRequest, WorkflowResult
from report_processor.drawing_card.review import import_review_approvals
from report_processor.drawing_card.workflow import default_template_path, run_workflow

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_SOURCES = 32
_SOURCE_SUFFIXES = {".xlsx", ".xlsm", ".xlsb"}
_RESULT_NAME = "drawing-card.xlsx"
_REVIEW_NAME = "manual_review.xlsx"
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


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
            )
            self._jobs[job_id] = job
            return self._run(job)
        except Exception:
            self._jobs.pop(job_id, None)
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> DrawingCardJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise KeyError(job_id) from error

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
        return self._run(job, review_decisions=review_path)

    def _run(self, job: DrawingCardJob, *, review_decisions: Path | None = None) -> DrawingCardJob:
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
            rag_mode="off",
            review_decisions=review_decisions,
            strict=True,
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
        }
        job.warnings = _controlled_warnings(result.warnings)
        if not _sources_unchanged(job):
            job.status = "failed"
            job.errors = ("SOURCE_HASH_CHANGED",)
            output.unlink(missing_ok=True)
            return job
        review = result.work_dir / _REVIEW_NAME
        if result.manual_review_count and review.is_file() and _inside_job(review, job):
            os.chmod(review, 0o600)
            job.review = review
            job.status = "review_required"
        elif (
            result.output_path is not None
            and result.output_path.is_file()
            and result.status == "OK"
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
            job.errors = ("WORKFLOW_BLOCKED",)
        else:
            job.status = "failed"
            job.errors = ("PROCESSING_FAILED",)
        return job


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
    if suffix in {".xlsx", ".xlsm"} and not content.startswith(_ZIP_SIGNATURES):
        raise ValueError("invalid workbook content")
    if suffix == ".xlsb" and not content.startswith(_OLE_SIGNATURE):
        raise ValueError("invalid workbook content")


def _validate_period(period: str | None) -> str | None:
    if period is None:
        return None
    if not isinstance(period, str) or not (clean := period.strip()) or len(clean) > 64:
        raise ValueError("invalid period")
    return clean


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
    return list(dict.fromkeys(str(item).partition(":")[0] for item in warnings if item))[:50]

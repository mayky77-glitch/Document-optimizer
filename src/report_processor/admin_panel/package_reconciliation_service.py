"""Private local jobs for uploaded Excel/PDF package reconciliation."""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from report_processor.package_reconciliation.pipeline import reconcile_package
from report_processor.package_reconciliation.report import ReconciliationReport, report_payload

MAX_PACKAGE_FILES = 128
MAX_PACKAGE_UPLOAD_BYTES = 256 * 1024 * 1024
_ALLOWED_SUFFIXES = frozenset({".pdf", ".xlsx", ".xlsm", ".ods"})
_WORKBOOK_SUFFIXES = frozenset({".xlsx", ".xlsm", ".ods"})
_RESULT_NAME = "package-reconciliation.json"

PackageRunner = Callable[[Path], ReconciliationReport]


@dataclass(slots=True, repr=False)
class PackageReconciliationJob:
    """Opaque job state. Private paths and report internals stay server-side."""

    job_id: str
    directory: Path
    input_root: Path
    input_digest: str
    status: str = "processing"
    result: Path | None = None
    payload: dict[str, object] | None = None
    errors: tuple[str, ...] = ()

    @property
    def result_available(self) -> bool:
        return self.status == "ready" and self.result is not None and self.result.is_file()


class PackageReconciliationService:
    """Persist one validated browser folder upload, then run the accepted pipeline."""

    def __init__(self, workspace_root: Path, runner: PackageRunner | None = None) -> None:
        self.workspace_root = Path(workspace_root)
        if self.workspace_root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.workspace_root, 0o700)
        self.runner = runner or reconcile_package
        self._jobs: dict[str, PackageReconciliationJob] = {}

    def create_job(self, *, files: Sequence[tuple[str, bytes]]) -> PackageReconciliationJob:
        validated = _validated_files(files)
        job_id = secrets.token_urlsafe(18)
        directory = self.workspace_root / job_id
        input_root = directory / "package"
        directory.mkdir(mode=0o700, parents=False, exist_ok=False)
        try:
            digest = hashlib.sha256()
            for relative, content in validated:
                digest.update(relative.as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(content)
                _write_private(input_root / Path(*relative.parts), content)
            job = PackageReconciliationJob(
                job_id=job_id,
                directory=directory,
                input_root=input_root,
                input_digest=digest.hexdigest(),
            )
            self._jobs[job_id] = job
            self._run(job)
            return job
        except Exception:
            self._jobs.pop(job_id, None)
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> PackageReconciliationJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise KeyError(job_id) from error

    def get_result(self, job_id: str) -> tuple[Path, str]:
        job = self.get_job(job_id)
        if not job.result_available or job.result is None:
            raise KeyError(job_id)
        return job.result, _RESULT_NAME

    def payload_for(self, job_id: str) -> dict[str, object]:
        return package_job_payload(self.get_job(job_id))

    def _run(self, job: PackageReconciliationJob) -> None:
        try:
            report = self.runner(job.input_root)
            payload = _safe_report_payload(report_payload(report))
            result = _write_private_json(job.directory / _RESULT_NAME, payload)
            job.payload = payload
            job.result = result
            job.status = "ready"
        except (OSError, TypeError, ValueError, RuntimeError):
            job.status = "failed"
            job.errors = ("PACKAGE_PROCESSING_FAILED",)
        except Exception:
            job.status = "failed"
            job.errors = ("PACKAGE_PROCESSING_FAILED",)


def package_job_payload(job: PackageReconciliationJob) -> dict[str, object]:
    """Return bounded evidence only: relative document names, never OCR or local paths."""
    response: dict[str, object] = {
        "job_id": job.job_id,
        "status": job.status,
        "summary": _summary(job.payload),
        "results": _public_results(job.payload),
        "download_url": (
            f"/api/package-reconciliation/jobs/{job.job_id}/result"
            if job.result_available
            else None
        ),
    }
    if job.status == "failed":
        response["error"] = "Не удалось обработать пакет. Проверьте состав и файлы пакета."
    return response


def _validated_files(files: Sequence[tuple[str, bytes]]) -> tuple[tuple[PurePosixPath, bytes], ...]:
    if not 1 <= len(files) <= MAX_PACKAGE_FILES:
        raise ValueError("invalid package file count")
    total = 0
    seen: set[str] = set()
    output: list[tuple[PurePosixPath, bytes]] = []
    for name, content in files:
        relative = _relative_upload_path(name)
        key = unicodedata.normalize("NFC", relative.as_posix()).casefold()
        if key in seen:
            raise ValueError("duplicate package path")
        seen.add(key)
        if not isinstance(content, bytes) or not content:
            raise ValueError("invalid package file")
        total += len(content)
        if total > MAX_PACKAGE_UPLOAD_BYTES:
            raise ValueError("combined package upload is too large")
        output.append((relative, content))
    if not any(path.suffix.casefold() in _WORKBOOK_SUFFIXES for path, _content in output):
        raise ValueError("package workbook is required")
    return tuple(output)


def _relative_upload_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("invalid package path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or len(path.parts) != len(value.split("/"))
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("invalid package path")
    if path.suffix.casefold() not in _ALLOWED_SUFFIXES:
        raise ValueError("unsupported package file type")
    return path


def _write_private(path: Path, content: bytes) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("private package path is unsafe")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _write_private_json(path: Path, payload: dict[str, object]) -> Path:
    import json

    return _write_private(path, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())


def _safe_report_payload(payload: dict[str, object]) -> dict[str, object]:
    """Freeze download contract to paths and fields safe for local browser display."""
    results = payload.get("results")
    if not isinstance(results, list) or len(results) > 100_000:
        raise ValueError("invalid package report")
    safe_results = []
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("invalid package report")
        safe = _public_result(result)
        for key in ("workbook_path", "pdf_path"):
            value = safe.get(key)
            if value is not None:
                _relative_upload_path(value)
        for value in safe.get("candidate_paths", []):
            _relative_upload_path(value)
        safe_results.append(safe)
    contract_version = payload.get("contract_version")
    if not isinstance(contract_version, str) or not 1 <= len(contract_version) <= 100:
        raise ValueError("invalid package report")
    return {"contract_version": contract_version, "results": safe_results}


def _summary(payload: dict[str, object] | None) -> dict[str, int]:
    if payload is None or not isinstance(payload.get("results"), list):
        return {}
    counts: dict[str, int] = {}
    for result in payload["results"]:
        if isinstance(result, dict) and isinstance(result.get("status"), str):
            status = result["status"]
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _public_results(payload: dict[str, object] | None) -> list[dict[str, object]]:
    if payload is None or not isinstance(payload.get("results"), list):
        return []
    return [_public_result(result) for result in payload["results"] if isinstance(result, dict)]


def _public_result(result: dict[str, object]) -> dict[str, object]:
    allowed = {
        "status",
        "workbook_path",
        "sheet_name",
        "row_number",
        "work_code",
        "pdf_path",
        "confidence",
        "reason_codes",
        "quantity_comparison",
        "workbook_quantity",
        "workbook_unit",
        "pdf_quantity",
        "pdf_unit",
        "cost_comparison",
        "candidate_paths",
    }
    return {key: value for key, value in result.items() if key in allowed}

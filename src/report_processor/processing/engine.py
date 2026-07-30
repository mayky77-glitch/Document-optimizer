"""Thin deterministic controller for the frozen ProcessingEngine-17.0 contract."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path

from .adapters import DefaultProcessingAdapters, ProcessingAdapters, ProcessingContext, StageOutcome
from .contracts import (
    PROCESSING_CONTRACT_VERSION,
    PROCESSING_ENGINE_VERSION,
    PROCESSING_STATE_VERSION,
    FileSnapshot,
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
)

_VERSIONS = {
    "request_result": PROCESSING_CONTRACT_VERSION,
    "engine": PROCESSING_ENGINE_VERSION,
    "state": PROCESSING_STATE_VERSION,
    "manifest": "FileManifest-2.0/enriched-3.0",
    "extraction": "ExtractionResult-6.0",
    "training": "TrainingData-7.0",
    "normalization": "Normalization-8.0",
    "target": "TargetReport-9.0",
    "rules": "RuleConfigurationVersion-1.0",
    "analytics": "AnalyticalStore-11.0/AnalyticalSchema-1",
    "matching": "MatchingContract-12.0",
    "calculation": "CalculationContract-13.0",
    "quality_control": "QualityControlContract-14.0",
    "writer": "ExcelWriterContract-15.1",
    "audit": "StageJournal-16.0",
}


class ProcessingEngine:
    """Controller with injectable adapters; default delegates through public Block APIs."""

    def __init__(self, adapters: ProcessingAdapters | None = None) -> None:
        self._adapters = adapters or DefaultProcessingAdapters()

    def process_report(self, request: ProcessReportRequest) -> ProcessingResult:
        return _process(request, self._adapters)

    def process_reports(
        self, requests: Iterable[ProcessReportRequest]
    ) -> tuple[ProcessingResult, ...]:
        return tuple(self.process_report(request) for request in requests)


def process_report(request: ProcessReportRequest) -> ProcessingResult:
    """Process one request through the default engine."""

    return ProcessingEngine().process_report(request)


def _process(request: ProcessReportRequest, adapters: ProcessingAdapters) -> ProcessingResult:

    try:
        _validate_request(request)
    except (TypeError, ValueError, OSError):
        return _result(
            request,
            ProcessingState.FAILED,
            ProcessingExitCode.INVALID_INPUT,
            errors=("INVALID_INPUT",),
        )
    snapshots = (_snapshot(request.source_path), _snapshot(request.target_path))
    run_key = _run_key(request, snapshots)
    try:
        cached = _read_cache(request, run_key, snapshots)
    except _CacheMismatchError:
        return _result(
            request,
            ProcessingState.FAILED,
            ProcessingExitCode.WRITE_OR_VERIFICATION_FAILED,
            run_key,
            errors=("RESUME_VALIDATION_FAILED",),
            snapshots=snapshots,
        )
    if cached is not None:
        return cached
    if not _is_adapter(adapters):
        return _result(
            request,
            ProcessingState.FAILED,
            ProcessingExitCode.CONTROLLED_INTERNAL_ERROR,
            run_key,
            errors=("Недопустимый ProcessingAdapters",),
            snapshots=snapshots,
        )
    try:
        with tempfile.TemporaryDirectory(prefix="report-processor-") as temporary_directory:
            context = ProcessingContext(
                request.mode,
                request.strict,
                run_key,
                temporary_directory,
                {
                    "request": request,
                    "source_sha256": snapshots[0].sha256,
                    "target_sha256": snapshots[1].sha256,
                },
            )
            outcomes = [_run_stage(adapters.inspect, context, "inspect")]
            quality_result = None
            if request.mode is not ProcessMode.INSPECT:
                outcomes.append(_run_stage(adapters.calculate, context, "calculate"))
                outcomes.append(_run_stage(adapters.audit, context, "audit"))
                decision = _decision(outcomes)
                if request.mode is ProcessMode.WRITE and _may_write(decision, request.strict):
                    outcomes.append(_run_stage(adapters.write, context, "write"))
                elif request.mode is ProcessMode.WRITE or _requires_quality_stop(
                    decision, outcomes, request.strict
                ):
                    quality_result = _quality_result(
                        request, run_key, snapshots, outcomes, decision
                    )
            _verify_unchanged(snapshots)
            result = quality_result or _success_result(request, run_key, snapshots, outcomes)
    except _InputChangedError:
        result = _result(
            request,
            ProcessingState.FAILED,
            ProcessingExitCode.WRITE_OR_VERIFICATION_FAILED,
            run_key,
            errors=("INPUT_SNAPSHOT_CHANGED",),
            snapshots=snapshots,
        )
    except Exception:  # controlled boundary: a bad adapter cannot stop bulk execution
        result = _result(
            request,
            ProcessingState.FAILED,
            ProcessingExitCode.CONTROLLED_INTERNAL_ERROR,
            run_key,
            errors=("PROCESSING_STAGE_FAILED",),
            snapshots=snapshots,
        )
    _write_cache(request, result)
    return result


def process_reports(requests: Iterable[ProcessReportRequest]) -> tuple[ProcessingResult, ...]:
    """Keep caller order and isolate every controlled request failure."""

    return ProcessingEngine().process_reports(requests)


def highest_exit_code(results: Iterable[ProcessingResult]) -> ProcessingExitCode:
    return max((result.exit_code for result in results), default=ProcessingExitCode.SUCCESS)


def _validate_request(request: ProcessReportRequest) -> None:
    if not isinstance(request, ProcessReportRequest):
        raise TypeError("request должен быть ProcessReportRequest")
    for path in (request.source_path, request.target_path):
        if not path.is_file():
            raise ValueError(f"Входной файл не найден: {path}")
    if request.source_path.resolve() == request.target_path.resolve():
        raise ValueError("source_path и target_path должны различаться")
    if request.rules_path is not None and not request.rules_path.is_file():
        raise ValueError("rules_path должен указывать на файл")
    if request.mode is not ProcessMode.WRITE and request.output_path is not None:
        raise ValueError("inspect и dry-run не публикуют XLSX")


def _snapshot(path: Path) -> FileSnapshot:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return FileSnapshot(path, digest.hexdigest(), stat.st_size, stat.st_mtime_ns)


def _verify_unchanged(snapshots: tuple[FileSnapshot, ...]) -> None:
    for snapshot in snapshots:
        current = _snapshot(snapshot.path)
        if current != snapshot:
            raise _InputChangedError(f"Входной файл изменился: {snapshot.path}")


def _run_key(request: ProcessReportRequest, snapshots: tuple[FileSnapshot, ...]) -> str:
    payload = {
        "inputs": [item.sha256 for item in snapshots],
        "stage": request.stage,
        "month": request.month,
        "mode": request.mode.value,
        "strict": request.strict,
        "options": dict(request.options),
        "rules_hash": _rules_hash(request),
        "versions": _VERSIONS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _outcome(value: object, stage: str) -> StageOutcome:
    if not isinstance(value, StageOutcome):
        raise TypeError(f"{stage} должен вернуть StageOutcome")
    return value


def _run_stage(callback, context: ProcessingContext, name: str) -> StageOutcome:
    outcome = _outcome(callback(context), name)
    context.values.update(outcome.artifacts)
    return outcome


def _decision(outcomes: list[StageOutcome]) -> str | None:
    return next((item.decision for item in reversed(outcomes) if item.decision), None)


def _may_write(decision: str | None, strict: bool) -> bool:
    if decision == "allow_write":
        return True
    return decision == "allow_write_with_warnings" and not strict


def _requires_quality_stop(
    decision: str | None, outcomes: Iterable[StageOutcome], strict: bool
) -> bool:
    if decision in {"require_manual_review", "block_write"}:
        return True
    return strict and any(outcome.warnings for outcome in outcomes)


def _quality_result(request, run_key, snapshots, outcomes, decision) -> ProcessingResult:
    warnings, artifacts = _collect(outcomes)
    if decision == "require_manual_review" or (request.strict and warnings):
        return _result(
            request,
            ProcessingState.MANUAL_REVIEW_REQUIRED,
            ProcessingExitCode.MANUAL_REVIEW_REQUIRED,
            run_key,
            warnings,
            snapshots=snapshots,
            artifacts=artifacts,
        )
    return _result(
        request,
        ProcessingState.QUALITY_BLOCKED,
        ProcessingExitCode.QUALITY_BLOCKED,
        run_key,
        warnings,
        snapshots=snapshots,
        artifacts=artifacts,
    )


def _success_result(request, run_key, snapshots, outcomes) -> ProcessingResult:
    warnings, artifacts = _collect(outcomes)
    state = ProcessingState.SUCCEEDED_WITH_WARNINGS if warnings else ProcessingState.SUCCEEDED
    code = ProcessingExitCode.SUCCESS_WITH_WARNINGS if warnings else ProcessingExitCode.SUCCESS
    return _result(
        request, state, code, run_key, warnings, snapshots=snapshots, artifacts=artifacts
    )


def _collect(outcomes: Iterable[StageOutcome]) -> tuple[tuple[str, ...], dict[str, object]]:
    warnings = tuple(item for outcome in outcomes for item in outcome.warnings)
    artifacts = {key: value for outcome in outcomes for key, value in outcome.artifacts.items()}
    return warnings, artifacts


def _result(
    request,
    state,
    exit_code,
    run_key="",
    warnings=(),
    errors=(),
    snapshots=(),
    artifacts=None,
    resumed=False,
):
    return ProcessingResult(
        request,
        state,
        exit_code,
        run_key,
        tuple(warnings),
        tuple(errors),
        tuple(snapshots),
        artifacts or {},
        resumed,
    )


def _is_adapter(value: object) -> bool:
    names = ("inspect", "calculate", "audit", "write")
    return all(callable(getattr(value, name, None)) for name in names)


def _cache_path(request: ProcessReportRequest, run_key: str) -> Path | None:
    del run_key
    return (
        request.cache_directory / f"{_cache_identity(request)}.json"
        if request.cache_directory
        else None
    )


def _read_cache(request, run_key, snapshots) -> ProcessingResult | None:
    if not request.resume:
        return None
    path = _cache_path(request, run_key)
    if path is None or not path.is_file():
        raise _CacheMismatchError
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["versions"] != _VERSIONS:
            raise _CacheMismatchError
        if payload["inputs"] != [item.sha256 for item in snapshots]:
            raise _CacheMismatchError
        if payload["rules_hash"] != _rules_hash(request):
            raise _CacheMismatchError
        if payload["boundary"] not in {"DATA_COMMITTED", "EXPORT_PREPARED", "EXPORT_VERIFIED"}:
            raise _CacheMismatchError
        _validate_audit_resume(request, payload)
        return _result(
            request,
            ProcessingState(payload["state"]),
            ProcessingExitCode(payload["exit_code"]),
            run_key,
            payload["warnings"],
            payload["errors"],
            snapshots,
            payload["artifacts"],
            True,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise _CacheMismatchError from error


def _write_cache(request: ProcessReportRequest, result: ProcessingResult) -> None:
    if (path := _cache_path(request, result.run_key)) is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "versions": _VERSIONS,
        "inputs": [item.sha256 for item in result.input_snapshots],
        "state": result.state.value,
        "exit_code": int(result.exit_code),
        "warnings": result.warnings,
        "errors": result.errors,
        "artifacts": _json_safe(result.artifacts),
        "rules_hash": _rules_hash(request),
        "boundary": _boundary(result),
    }
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _json_safe(value: Mapping[str, object]) -> Mapping[str, object]:
    return {key: item for key, item in value.items() if isinstance(item, (str, int, float, bool))}


def _rules_hash(request: ProcessReportRequest) -> str:
    if request.rules_path is None:
        from report_processor.business_rules import load_default_rule_set

        result = load_default_rule_set()
        if not result.valid or result.rule_set is None:
            raise _CacheMismatchError
        return result.rule_set.content_hash
    return _snapshot(request.rules_path).sha256


def _boundary(result: ProcessingResult) -> str:
    boundary = result.artifacts.get("audit_boundary")
    if boundary in {"PENDING", "DATA_COMMITTED", "EXPORT_PREPARED", "EXPORT_VERIFIED"}:
        return str(boundary)
    return "PENDING" if result.request.mode is ProcessMode.INSPECT else "DATA_COMMITTED"


def _cache_identity(request: ProcessReportRequest) -> str:
    payload = {
        "source_ref": hashlib.sha256(str(request.source_path.resolve()).encode()).hexdigest(),
        "target_ref": hashlib.sha256(str(request.target_path.resolve()).encode()).hexdigest(),
        "mode": request.mode.value,
        "strict": request.strict,
        "stage": request.stage,
        "month": request.month,
        "options": dict(request.options),
        "versions": _VERSIONS,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _validate_audit_resume(request: ProcessReportRequest, payload: Mapping[str, object]) -> None:
    run_id = payload.get("artifacts", {}).get("audit_run_id")
    if run_id is None:
        return
    if not isinstance(run_id, str) or request.audit_directory is None:
        raise _CacheMismatchError
    from report_processor.audit import AuditJournal

    try:
        with AuditJournal(request.audit_directory / "journal.sqlite3") as journal:
            events = journal.validate_run(run_id)
    except Exception as error:
        raise _CacheMismatchError from error
    if not events or events[-1].controlled_state_code != payload["boundary"]:
        raise _CacheMismatchError


class _InputChangedError(RuntimeError):
    pass


class _CacheMismatchError(RuntimeError):
    pass

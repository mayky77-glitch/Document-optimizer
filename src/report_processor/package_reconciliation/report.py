"""Canonical, path-safe report serialization for package reconciliation."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath

from .matcher import RowReconciliation

REPORT_VERSION = "ExcelPdfReconciliation-1.0"


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    results: tuple[RowReconciliation, ...]
    contract_version: str = REPORT_VERSION


def report_payload(report: ReconciliationReport) -> dict[str, object]:
    return {
        "contract_version": report.contract_version,
        "results": [_result_payload(result) for result in report.results],
    }


def write_report_atomically(report: ReconciliationReport, output_path: Path) -> None:
    """Write JSON in target directory, atomically, private to current user."""
    output = Path(output_path)
    if not output.parent.exists() or not output.parent.is_dir():
        raise ValueError("output parent directory must exist")
    payload = (
        json.dumps(report_payload(report), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    descriptor, temporary = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
        os.chmod(output, 0o600)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def _result_payload(result: RowReconciliation) -> dict[str, object]:
    value = asdict(result)
    return {key: _json_value(item) for key, item in value.items()}


def _json_value(value: object) -> object:
    if isinstance(value, (PurePosixPath, Path)):
        return value.as_posix()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value

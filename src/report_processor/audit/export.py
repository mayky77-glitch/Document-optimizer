"""Deterministic, validated snapshot exports with no-clobber publication."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path
from typing import Literal

from .models import AuditErrorCode
from .serialization import EXPORT_ALLOWLIST, canonical_json, redact

ExportFormat = Literal["json", "jsonl", "csv"]


class AuditExportError(RuntimeError):
    pass


def _fsync_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def deterministic_bytes(rows: Iterable[Mapping[str, object]], format: ExportFormat) -> bytes:
    safe_rows = sorted((redact(row) for row in rows), key=canonical_json)
    if format == "json":
        return (canonical_json(safe_rows) + "\n").encode("utf-8")
    if format == "jsonl":
        return "".join(canonical_json(row) + "\n" for row in safe_rows).encode("utf-8")
    if format == "csv":
        fields = sorted(set().union(*(row.keys() for row in safe_rows)))
        import io

        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(
            buffer, fieldnames=fields, lineterminator="\n", extrasaction="raise"
        )
        writer.writeheader()
        writer.writerows(safe_rows)
        return buffer.getvalue().encode("utf-8")
    raise ValueError(f"unsupported export format: {format}")


def validate_bytes(
    data: bytes, format: ExportFormat, expected_count: int, expected_hash: str
) -> None:
    if sha256(data).hexdigest() != expected_hash:
        raise AuditExportError(AuditErrorCode.EXPORT_HASH_MISMATCH.value)
    text = data.decode("utf-8")
    if format == "json":
        rows = json.loads(text)
    elif format == "jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line]
    else:
        rows = list(csv.DictReader(text.splitlines()))
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise AuditExportError(AuditErrorCode.SNAPSHOT_CHANGED.value)
    if any(not set(row).issubset(EXPORT_ALLOWLIST) for row in rows):
        raise AuditExportError("export contains non-allowlisted fields")


def export_snapshot(
    rows: Iterable[Mapping[str, object]], destination: Path | str, format: ExportFormat
) -> str:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise AuditExportError(AuditErrorCode.EXPORT_DESTINATION_EXISTS.value)
    materialized = sorted((redact(row) for row in rows), key=canonical_json)
    data = deterministic_bytes(materialized, format)
    content_hash = sha256(data).hexdigest()
    fd, temp_name = tempfile.mkstemp(prefix=".audit-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temp_name)
    linked_by_us = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        reopened = temporary.read_bytes()
        validate_bytes(reopened, format, len(materialized), content_hash)
        try:
            os.link(temporary, destination)
            linked_by_us = True
        except FileExistsError as exc:
            raise AuditExportError(AuditErrorCode.EXPORT_DESTINATION_EXISTS.value) from exc
        published = destination.read_bytes()
        validate_bytes(published, format, len(materialized), content_hash)
        _fsync_directory(destination.parent)
        return content_hash
    except BaseException:
        if linked_by_us:
            destination.unlink(missing_ok=True)
            _fsync_directory(destination.parent)
        raise
    finally:
        temporary.unlink(missing_ok=True)

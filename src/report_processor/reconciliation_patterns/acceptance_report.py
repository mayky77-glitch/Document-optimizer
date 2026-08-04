"""Private, deterministic evidence report for sealed shadow-acceptance decisions."""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
from contextlib import suppress
from dataclasses import fields
from pathlib import Path

from .acceptance import (
    RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    ShadowAcceptanceDecision,
    ShadowAcceptanceStatus,
)
from .replay import replay_fingerprint

RECONCILIATION_SHADOW_ACCEPTANCE_REPORT_VERSION = "ReconciliationShadowAcceptanceReport-1.0"
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ShadowAcceptanceReportError(ValueError):
    """Stable report-boundary failure that never echoes untrusted data."""

    def __init__(self, code: str) -> None:
        super().__init__("shadow acceptance report is invalid")
        self.code = code


def _schema_error() -> None:
    raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID")


def _sealed_decision(decision: object) -> ShadowAcceptanceDecision:
    if type(decision) is not ShadowAcceptanceDecision:
        _schema_error()
    if decision.version != RECONCILIATION_SHADOW_ACCEPTANCE_VERSION:
        _schema_error()
    if not isinstance(decision.status, ShadowAcceptanceStatus):
        _schema_error()
    if (
        not isinstance(decision.reason_codes, tuple)
        or any(
            not isinstance(code, str) or not _CODE.fullmatch(code) for code in decision.reason_codes
        )
        or decision.reason_codes != tuple(sorted(set(decision.reason_codes)))
    ):
        _schema_error()
    for name in (
        "replay_fingerprint",
        "promotion_fingerprint",
        "hard_gate_fingerprint",
        "threshold_fingerprint",
        "operational_fingerprint",
    ):
        value = getattr(decision, name)
        if value is not None and (not isinstance(value, str) or not _HASH.fullmatch(value)):
            _schema_error()
    if not isinstance(decision.fingerprint, str) or not _HASH.fullmatch(decision.fingerprint):
        _schema_error()
    values = {
        field.name: getattr(decision, field.name)
        for field in fields(decision)
        if field.name != "fingerprint"
    }
    if decision.fingerprint != replay_fingerprint(values):
        _schema_error()
    return decision


def shadow_acceptance_report_payload(decision: ShadowAcceptanceDecision) -> dict[str, object]:
    """Return only the controlled acceptance aggregate, not its source evidence."""
    sealed = _sealed_decision(decision)
    return {
        "schema_version": RECONCILIATION_SHADOW_ACCEPTANCE_REPORT_VERSION,
        "status": sealed.status.value,
        "reason_codes": list(sealed.reason_codes),
        "decision_fingerprint": sealed.fingerprint,
    }


def shadow_acceptance_report_bytes(decision: ShadowAcceptanceDecision) -> bytes:
    """Encode the controlled aggregate as canonical, newline-terminated JSON."""
    try:
        encoded = json.dumps(
            shadow_acceptance_report_payload(decision),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID") from exc
    return encoded + b"\n"


def _validate_output_path(path: object) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or path.name in {"", ".", ".."}:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    try:
        parent_status = path.parent.lstat()
    except OSError as exc:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE") from exc
    if stat.S_ISLNK(parent_status.st_mode) or not stat.S_ISDIR(parent_status.st_mode):
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    for ancestor in (path.parent, *path.parent.parents):
        if (ancestor / ".git").exists():
            raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    return path


def _existing_output_is_safe(parent_fd: int, name: str, *, overwrite: bool) -> None:
    try:
        existing = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE") from exc
    if not stat.S_ISREG(existing.st_mode):
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    if not overwrite:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_EXISTS")


def _write_all(fd: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("short output write")
        offset += written


def write_shadow_acceptance_report(
    path: Path, decision: ShadowAcceptanceDecision, *, overwrite: bool
) -> bytes:
    """Atomically publish a mode-0600 report outside a Git worktree."""
    payload = shadow_acceptance_report_bytes(decision)
    output = _validate_output_path(path)
    parent_fd = -1
    temp_fd = -1
    temp_name = ""
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        parent_fd = os.open(output.parent, flags)
        _existing_output_is_safe(parent_fd, output.name, overwrite=overwrite)
        temp_name = f".{output.name}.{secrets.token_hex(16)}.tmp"
        temp_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        temp_fd = os.open(temp_name, temp_flags, 0o600, dir_fd=parent_fd)
        os.fchmod(temp_fd, 0o600)
        _write_all(temp_fd, payload)
        os.fsync(temp_fd)
        if not stat.S_ISREG(os.fstat(temp_fd).st_mode):
            raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
        os.close(temp_fd)
        temp_fd = -1
        os.replace(temp_name, output.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        os.fsync(parent_fd)
        return payload
    except ShadowAcceptanceReportError:
        raise
    except OSError as exc:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_IO") from exc
    finally:
        if temp_fd >= 0:
            os.close(temp_fd)
        if temp_name and parent_fd >= 0:
            with suppress(FileNotFoundError):
                os.unlink(temp_name, dir_fd=parent_fd)
        if parent_fd >= 0:
            os.close(parent_fd)

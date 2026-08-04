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
from .acceptance_runner import ShadowAcceptanceInputs, run_shadow_acceptance
from .replay import replay_fingerprint

RECONCILIATION_SHADOW_ACCEPTANCE_REPORT_VERSION = "ReconciliationShadowAcceptanceReport-1.0"
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_REPORT_BYTES = 16 * 1024


class ShadowAcceptanceReportError(ValueError):
    """Stable report-boundary failure that never echoes untrusted data."""

    def __init__(self, code: str) -> None:
        super().__init__("shadow acceptance report is invalid")
        self.code = code


def _schema_error() -> None:
    raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID")


def _sealed_decision(
    decision: object, inputs: ShadowAcceptanceInputs | None
) -> ShadowAcceptanceDecision:
    if type(decision) is not ShadowAcceptanceDecision:
        _schema_error()
    try:
        decision.__post_init__()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID") from exc
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
    if decision.status is ShadowAcceptanceStatus.PASS and any(
        value is None
        for value in (
            decision.replay_fingerprint,
            decision.promotion_fingerprint,
            decision.hard_gate_fingerprint,
            decision.threshold_fingerprint,
            decision.operational_fingerprint,
        )
    ):
        _schema_error()
    values = {
        field.name: getattr(decision, field.name)
        for field in fields(decision)
        if field.name != "fingerprint"
    }
    if decision.fingerprint != replay_fingerprint(values):
        _schema_error()
    if decision.status is ShadowAcceptanceStatus.PASS:
        if type(inputs) is not ShadowAcceptanceInputs:
            _schema_error()
        try:
            expected = run_shadow_acceptance(inputs)
        except ValueError as exc:
            raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID") from exc
        if expected != decision:
            _schema_error()
    return decision


def shadow_acceptance_report_payload(
    decision: ShadowAcceptanceDecision, *, inputs: ShadowAcceptanceInputs | None = None
) -> dict[str, object]:
    """Return only the controlled acceptance aggregate, not its source evidence."""
    sealed = _sealed_decision(decision, inputs)
    return {
        "schema_version": RECONCILIATION_SHADOW_ACCEPTANCE_REPORT_VERSION,
        "status": sealed.status.value,
        "reason_codes": list(sealed.reason_codes),
        "decision_fingerprint": sealed.fingerprint,
    }


def shadow_acceptance_report_bytes(
    decision: ShadowAcceptanceDecision, *, inputs: ShadowAcceptanceInputs | None = None
) -> bytes:
    """Encode the controlled aggregate as canonical, newline-terminated JSON."""
    try:
        encoded = json.dumps(
            shadow_acceptance_report_payload(decision, inputs=inputs),
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID") from exc
    payload = encoded + b"\n"
    if len(payload) > _MAX_REPORT_BYTES:
        raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID")
    return payload


def _open_verified_output_parent(path: object) -> tuple[Path, list[int]]:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or path.name in {"", ".", ".."}
        or any(component in {".", ".."} for component in path.parts)
    ):
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        descriptor = os.open(path.anchor, flags)
        descriptors.append(descriptor)
        for component in path.parent.parts[1:]:
            descriptor = os.open(component, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
        _verify_no_git_ancestor(descriptors)
    except OSError as exc:
        _close_descriptors(descriptors)
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE") from exc
    except ShadowAcceptanceReportError:
        _close_descriptors(descriptors)
        raise
    return path, descriptors


def _verify_no_git_ancestor(descriptors: list[int]) -> None:
    for descriptor in descriptors:
        try:
            os.stat(".git", dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE") from exc
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")


def _close_descriptors(descriptors: list[int]) -> None:
    for descriptor in reversed(descriptors):
        with suppress(OSError):
            os.close(descriptor)


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
    path: Path,
    decision: ShadowAcceptanceDecision,
    *,
    overwrite: bool,
    inputs: ShadowAcceptanceInputs | None = None,
) -> bytes:
    """Atomically publish a mode-0600 report outside a Git worktree."""
    if type(overwrite) is not bool:
        raise ShadowAcceptanceReportError("REPORT_OUTPUT_UNSAFE")
    payload = shadow_acceptance_report_bytes(decision, inputs=inputs)
    if len(payload) > _MAX_REPORT_BYTES:
        raise ShadowAcceptanceReportError("REPORT_SCHEMA_INVALID")
    output, descriptors = _open_verified_output_parent(path)
    parent_fd = descriptors[-1]
    temp_fd = -1
    temp_name = ""
    try:
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
        _verify_no_git_ancestor(descriptors)
        if overwrite:
            os.replace(temp_name, output.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        else:
            try:
                os.link(
                    temp_name,
                    output.name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise ShadowAcceptanceReportError("REPORT_OUTPUT_EXISTS") from exc
            os.unlink(temp_name, dir_fd=parent_fd)
            temp_name = ""
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
        _close_descriptors(descriptors)

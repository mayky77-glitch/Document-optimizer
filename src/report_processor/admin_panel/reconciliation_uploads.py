"""Validation and safe metadata for reconciliation workbook uploads."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

MAX_UPLOAD_BYTES = 256 * 1024 * 1024
MAX_SOURCES = 32
ALLOWED_SUFFIXES = frozenset({".xlsx", ".xlsm"})
ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
STAGE_PATTERN = re.compile(r"^[0-9A-Za-zА-Яа-яЁё][0-9A-Za-zА-Яа-яЁё._ -]{0,63}$")


def validate_workbook_upload(name: str, content: bytes) -> None:
    if not isinstance(name, str) or not name or "\x00" in name or not _safe_basename(name):
        raise ValueError("invalid filename")
    if Path(name).suffix.casefold() not in ALLOWED_SUFFIXES:
        raise ValueError("only .xlsx and .xlsm workbooks are accepted")
    if not isinstance(content, bytes) or not content:
        raise ValueError("empty upload")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("upload too large")
    if not content.startswith(ZIP_SIGNATURES):
        raise ValueError("invalid Excel container signature")


def validated_sources(
    sources: list[tuple[str, bytes]] | None, source_name: str | None, source_content: bytes | None
) -> list[tuple[str, bytes]]:
    if sources is not None and (source_name is not None or source_content is not None):
        raise ValueError("provide sources or legacy source_name/source_content, not both")
    values = sources if sources is not None else [(source_name, source_content)]
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_SOURCES:
        raise ValueError("provide from 1 to 32 source workbooks")
    result: list[tuple[str, bytes]] = []
    names: set[str] = set()
    digests: set[str] = set()
    for item in values:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError("invalid source upload")
        name, content = item
        validate_workbook_upload(name, content)
        basename = unicodedata.normalize("NFC", name)
        if basename.casefold() in names:
            raise ValueError("duplicate source filename")
        content_digest = digest(content)
        if content_digest in digests:
            raise ValueError("duplicate source content")
        names.add(basename.casefold())
        digests.add(content_digest)
        result.append((basename, content))
    return sorted(result, key=lambda item: (item[0].casefold(), digest(item[1])))


def validate_stage(stage: object) -> str:
    if not isinstance(stage, str) or not STAGE_PATTERN.fullmatch(stage.strip()):
        raise ValueError("invalid stage")
    return stage.strip()


def validate_mode(mode: object) -> str:
    if not isinstance(mode, str) or mode not in {"inspect", "dry-run", "write"}:
        raise ValueError("invalid mode")
    return mode


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_basename(name: str) -> bool:
    return name == Path(name).name and "/" not in name and "\\" not in name

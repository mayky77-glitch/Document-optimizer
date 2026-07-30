from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath

_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACES = re.compile(r"\s+")
_UNSAFE_STEM = re.compile(r"[^\w.-]+", re.UNICODE)


def is_unsafe_archive_path(value: str) -> bool:
    if not value or "\x00" in value:
        return True
    if value.startswith(("/", "\\")):
        return True

    windows_path = PureWindowsPath(value)
    if windows_path.is_absolute() or windows_path.drive or windows_path.root:
        return True

    posix_path = PurePosixPath(value.replace("\\", "/"))
    if posix_path.is_absolute():
        return True
    return any(part == ".." for part in posix_path.parts)


def safe_local_filename(
    file_id: str,
    original_path: str,
    extension: str,
    max_length: int = 120,
) -> str:
    raw_name = original_path.replace("\\", "/").rsplit("/", 1)[-1]
    suffix = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    stem = raw_name[: -len(suffix)] if suffix and raw_name.lower().endswith(suffix) else raw_name
    stem = _INVALID_FILENAME.sub("_", stem)
    stem = _SPACES.sub("_", stem.strip())
    stem = _UNSAFE_STEM.sub("_", stem).strip(" ._")
    if not stem or stem.upper() in _RESERVED_NAMES:
        stem = "source"

    prefix = re.sub(r"[^a-zA-Z0-9]", "", file_id)[:8] or "file"
    available = max(1, max_length - len(prefix) - len(suffix) - 1)
    stem = stem[:available].rstrip(" ._") or "source"
    return f"{prefix}_{stem}{suffix}"

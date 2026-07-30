"""Filesystem-safe fixture helpers for processing tests."""

from __future__ import annotations

import hashlib
from pathlib import Path


def fingerprint(path: Path) -> tuple[str, int, int]:
    """Return the immutable input properties required by ProcessingContract-17.0."""
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns

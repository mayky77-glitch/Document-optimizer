"""Object identity resolution with explicit conflict reporting."""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

from ..models import ManifestEntry, ObjectIdentityResult
from ..statuses import Status
from .normalization import extract_filename_object_candidates, extract_object_candidates


def load_object_map(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return {str(key): str(value).zfill(4) for key, value in payload.items()}
    mapping: dict[str, str] = {}
    for item in payload:
        mapping[str(item["pattern"])] = str(item["object_index"]).zfill(4)
    return mapping


def _mapping_value(entry: ManifestEntry, mapping: dict[str, str]) -> str | None:
    for pattern, value in mapping.items():
        if fnmatch.fnmatch(entry.logical_path, pattern) or fnmatch.fnmatch(entry.filename, pattern):
            return value
    return None


def _append_candidates(
    target: list[tuple[str, str, float]],
    values: tuple[str, ...],
    source: str,
    confidence: float,
) -> None:
    for value in values:
        target.append((str(value).zfill(4), source, confidence))


def resolve_object_identity(
    entry: ManifestEntry,
    *,
    mapping: dict[str, str] | None = None,
    column_values: tuple[str, ...] = (),
    structured_values: tuple[str, ...] = (),
    explicit_value: str | None = None,
) -> ObjectIdentityResult:
    mapping = mapping or {}
    sources: list[tuple[str, str, float]] = []
    if explicit_value:
        sources.append((str(explicit_value).zfill(4), "cli", 1.0))
    mapped = _mapping_value(entry, mapping)
    if mapped:
        sources.append((mapped, "mapping", 0.98))
    for value in column_values:
        _append_candidates(sources, extract_object_candidates(value), "column", 0.94)
    for value in structured_values:
        _append_candidates(
            sources,
            extract_object_candidates(value),
            "structured_cell",
            0.90,
        )
    filename_candidates = (
        (entry.object_index_hint,)
        if entry.object_index_hint
        else extract_filename_object_candidates(entry.filename)
    )
    _append_candidates(sources, filename_candidates, "filename", 0.80)
    parent = str(Path(entry.logical_path).parent)
    _append_candidates(
        sources,
        extract_filename_object_candidates(parent),
        "folder_or_zip_path",
        0.70,
    )

    ordered: list[tuple[str, str, float]] = []
    seen: set[tuple[str, str]] = set()
    for item in sources:
        key = (item[0], item[1])
        if key not in seen:
            seen.add(key)
            ordered.append(item)
    candidates = tuple(dict.fromkeys(item[0] for item in ordered))
    if not ordered:
        return ObjectIdentityResult(None, None, 0.0, (), Status.OBJECT_NOT_FOUND, ())
    selected = ordered[0]
    conflicts = tuple(candidate for candidate in candidates if candidate != selected[0])
    if conflicts:
        return ObjectIdentityResult(
            None,
            None,
            selected[2],
            candidates,
            Status.OBJECT_CONFLICT,
            (f"OBJECT_IDENTITY_CONFLICT:{','.join(candidates)}",),
        )
    return ObjectIdentityResult(selected[0], selected[1], selected[2], candidates, Status.OK, ())

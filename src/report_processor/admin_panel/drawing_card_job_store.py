"""Private, bounded persistence for drawing-card job manifests.

The store deliberately knows nothing about the drawing-card service.  A caller
supplies a JSON-compatible manifest and receives the same controlled mapping
back.  Paths are an exception: they are accepted only in path-named fields and
are always relative to the opaque job directory.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path, PurePosixPath

MANIFEST_CONTRACT = "DrawingCardPrivateManifest-1.0"
MANIFEST_FILENAME = "job-manifest.json"
MAX_MANIFEST_BYTES = 1_048_576
MAX_JOB_ID_LENGTH = 96
MAX_MANIFEST_DEPTH = 16
MAX_MANIFEST_ITEMS = 10_000
MAX_SCANNED_JOBS = 4_096
MAX_LOADED_JOBS = 1_024
_ACTIVE_STATUSES = frozenset({"queued", "processing", "review_required"})

_JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_WINDOWS_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\)")


class DrawingCardJobStore:
    """Store schema-versioned JSON manifests below one private workspace.

    The workspace and every job directory are owned by the current user.  Bad
    on-disk data is treated as absent so service restart recovery can continue
    with other jobs safely.
    """

    def __init__(self, workspace_root: Path) -> None:
        root = Path(workspace_root)
        if root.is_symlink():
            raise ValueError("workspace root cannot be a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not root.is_dir():
            raise ValueError("workspace root must be a directory")
        os.chmod(root, 0o700)
        self.workspace_root = root.resolve(strict=True)

    def save(self, job_id: str, manifest: Mapping[str, object]) -> dict[str, object]:
        """Validate and atomically persist one manifest, returning its safe copy."""
        safe_job_id = _validate_job_id(job_id)
        normalized = _validate_manifest(manifest)
        directory = self._job_directory(safe_job_id)
        directory.mkdir(mode=0o700, parents=False, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("job directory is unsafe")
        os.chmod(directory, 0o700)
        _atomic_write(directory / MANIFEST_FILENAME, normalized)
        return _copy_manifest(normalized)

    def load(self, job_id: str) -> dict[str, object] | None:
        """Load one valid manifest; corrupt or hostile data is invisible."""
        try:
            safe_job_id = _validate_job_id(job_id)
            directory = self._job_directory(safe_job_id)
            if directory.is_symlink() or not directory.is_dir():
                return None
            return _read_manifest(directory / MANIFEST_FILENAME)
        except ValueError:
            return None

    def load_all(self) -> dict[str, dict[str, object]]:
        """Return bounded manifests, prioritising recoverable active work.

        A bounded scan prevents an untrusted workspace from creating unbounded
        restart work.  Within that scan, queued/processing/review jobs are
        selected before terminal manifests so retention history cannot crowd
        out work that must resume.
        """
        active: list[tuple[str, dict[str, object]]] = []
        terminal: list[tuple[str, dict[str, object]]] = []
        try:
            children = sorted(self.workspace_root.iterdir(), key=lambda item: item.name)
        except OSError:
            return {}
        for child in children[:MAX_SCANNED_JOBS]:
            if child.is_symlink() or not child.is_dir():
                continue
            try:
                job_id = _validate_job_id(child.name)
            except ValueError:
                continue
            manifest = _read_manifest(child / MANIFEST_FILENAME)
            if manifest is not None:
                target = active if manifest.get("status") in _ACTIVE_STATUSES else terminal
                target.append((job_id, manifest))
        selected = (*active, *terminal)[:MAX_LOADED_JOBS]
        return dict(selected)

    def delete(self, job_id: str) -> bool:
        """Remove only a single manifest, leaving private job artifacts intact."""
        try:
            safe_job_id = _validate_job_id(job_id)
            directory = self._job_directory(safe_job_id)
            path = directory / MANIFEST_FILENAME
            if directory.is_symlink() or not path.is_file() or path.is_symlink():
                return False
            path.unlink()
            _fsync_directory(directory)
            return True
        except (OSError, ValueError):
            return False

    def _job_directory(self, job_id: str) -> Path:
        candidate = self.workspace_root / job_id
        # The identifier check makes this relationship lexical and stable even
        # before the directory exists.  Do not resolve a potentially hostile
        # symlink here; callers reject symlinked entries separately.
        if candidate.parent != self.workspace_root:
            raise ValueError("job directory escapes workspace")
        return candidate


# Short alias for callers that do not need the product-specific name.
PrivateJobManifestStore = DrawingCardJobStore


def _validate_job_id(value: object) -> str:
    if not isinstance(value, str) or not _JOB_ID.fullmatch(value):
        raise ValueError("invalid job identifier")
    return value


def _validate_manifest(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("manifest must be a mapping")
    normalized = _normalize_json(value, depth=0, path_context=False)
    if not isinstance(normalized, dict) or normalized.get("contract") != MANIFEST_CONTRACT:
        raise ValueError("unsupported manifest contract")
    encoded = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("manifest exceeds size limit")
    return normalized


def _normalize_json(value: object, *, depth: int, path_context: bool) -> object:
    if depth > MAX_MANIFEST_DEPTH:
        raise ValueError("manifest nesting exceeds limit")
    if value is None or isinstance(value, (bool, int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise ValueError("manifest contains a non-finite number")
        return value
    if isinstance(value, str):
        if _looks_absolute(value):
            raise ValueError("manifest contains an absolute path")
        return _safe_relative_path(value).as_posix() if path_context else value
    if isinstance(value, Mapping):
        if len(value) > MAX_MANIFEST_ITEMS:
            raise ValueError("manifest mapping exceeds limit")
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 256:
                raise ValueError("manifest key is invalid")
            result[key] = _normalize_json(item, depth=depth + 1, path_context=_is_path_key(key))
        return result
    if isinstance(value, (list, tuple)):
        if len(value) > MAX_MANIFEST_ITEMS:
            raise ValueError("manifest sequence exceeds limit")
        return [_normalize_json(item, depth=depth + 1, path_context=path_context) for item in value]
    raise ValueError("manifest is not JSON-compatible")


def _is_path_key(key: str) -> bool:
    lowered = key.casefold()
    return lowered in {"path", "paths"} or lowered.endswith(("_path", "_paths"))


def _safe_relative_path(value: str) -> PurePosixPath:
    if (
        not value
        or "\\" in value
        or "//" in value
        or value.endswith("/")
        or "." in value.split("/")
    ):
        raise ValueError("manifest path must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise ValueError("manifest path must be relative to its job")
    return path


def _looks_absolute(value: str) -> bool:
    return value.startswith("/") or bool(_WINDOWS_ABSOLUTE.match(value))


def _read_manifest(path: Path) -> dict[str, object] | None:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MANIFEST_BYTES:
            return None
        raw = path.read_bytes()
        if len(raw) > MAX_MANIFEST_BYTES:
            return None
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, Mapping):
            return None
        return _copy_manifest(_validate_manifest(payload))
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None


def _copy_manifest(value: Mapping[str, object]) -> dict[str, object]:
    # JSON round-trip gives callers no mutable reference into store state and
    # guarantees the public return remains serializable.
    copied = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    assert isinstance(copied, dict)
    return copied


def _atomic_write(path: Path, manifest: Mapping[str, object]) -> None:
    payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)
    except BaseException:
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise


def _fsync_directory(directory: Path) -> None:
    """Durably record a replace where directory fsync is available."""
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except (AttributeError, OSError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Some supported platforms/filesystems do not permit directory fsync.
        pass
    finally:
        os.close(descriptor)

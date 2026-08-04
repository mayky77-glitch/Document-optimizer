"""Job-private atomic persistence for inert active-learning shadow intent."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from report_processor.reconciliation_patterns.active_learning import (
    MAX_MEMBER_REFS,
    MAX_QUEUE_ITEMS,
    MAX_SPLIT_GROUPS,
    ActiveLearningConflictError,
    ActiveLearningContractError,
    ActiveLearningIntent,
    ActiveLearningQueue,
    ActiveLearningShadowAutosave,
    ShadowAction,
    canonical_json_bytes,
    transition_shadow_intent,
)

STORE_VERSION = "ActiveLearningShadowStore-1.0"
MAX_STORE_BYTES = 1_048_576

_ENVELOPE_KEYS = {"version", "current", "previous"}
_AUTOSAVE_KEYS = {"version", "queue_id", "queue_fingerprint", "intents"}
_INTENT_KEYS = {
    "version",
    "queue_id",
    "expected_queue_fingerprint",
    "item_id",
    "expected_item_fingerprint",
    "action",
    "split_member_refs",
}

_THREAD_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


class ActiveLearningStoreError(ActiveLearningContractError):
    """The private shadow file is malformed, insecure, or cannot be persisted."""


class ActiveLearningStoreConflict(ActiveLearningConflictError):
    """A valid request cannot be applied to the supplied shadow queue."""


class ActiveLearningStoreStaleConflict(ActiveLearningStoreConflict):
    """An exact queue, item, or autosave revision no longer matches."""


class ActiveLearningUndoUnavailable(ActiveLearningStoreConflict):
    """The bounded store has no previous shadow state to restore."""


def _closed_mapping(value: object, keys: set[str], *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ActiveLearningStoreError(f"{label} shape is invalid")
    return value


def _split_refs(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list) or len(value) > MAX_SPLIT_GROUPS:
        raise ActiveLearningStoreError("stored split membership is invalid")
    groups: list[tuple[str, ...]] = []
    total = 0
    for group in value:
        if not isinstance(group, list):
            raise ActiveLearningStoreError("stored split group is invalid")
        total += len(group)
        if total > MAX_MEMBER_REFS or any(not isinstance(ref, str) for ref in group):
            raise ActiveLearningStoreError("stored split membership is invalid")
        groups.append(tuple(group))
    return tuple(groups)


def _decode_intent(value: object) -> ActiveLearningIntent:
    payload = _closed_mapping(value, _INTENT_KEYS, label="stored intent")
    try:
        action = ShadowAction(payload["action"])
        return ActiveLearningIntent(
            queue_id=payload["queue_id"],
            expected_queue_fingerprint=payload["expected_queue_fingerprint"],
            item_id=payload["item_id"],
            expected_item_fingerprint=payload["expected_item_fingerprint"],
            action=action,
            split_member_refs=_split_refs(payload["split_member_refs"]),
            version=payload["version"],
        )
    except (TypeError, ValueError, ActiveLearningContractError) as error:
        raise ActiveLearningStoreError("stored intent is invalid") from error


def _decode_autosave(value: object) -> ActiveLearningShadowAutosave:
    payload = _closed_mapping(value, _AUTOSAVE_KEYS, label="stored autosave")
    intents = payload["intents"]
    if not isinstance(intents, list) or len(intents) > MAX_QUEUE_ITEMS:
        raise ActiveLearningStoreError("stored autosave intents are invalid")
    try:
        return ActiveLearningShadowAutosave(
            queue_id=payload["queue_id"],
            queue_fingerprint=payload["queue_fingerprint"],
            intents=tuple(_decode_intent(intent) for intent in intents),
            version=payload["version"],
        )
    except (TypeError, ActiveLearningContractError) as error:
        raise ActiveLearningStoreError("stored autosave is invalid") from error


def _intent_payload(intent: ActiveLearningIntent) -> dict[str, object]:
    return {
        "version": intent.version,
        "queue_id": intent.queue_id,
        "expected_queue_fingerprint": intent.expected_queue_fingerprint,
        "item_id": intent.item_id,
        "expected_item_fingerprint": intent.expected_item_fingerprint,
        "action": intent.action.value,
        "split_member_refs": intent.split_member_refs,
    }


def _autosave_payload(autosave: ActiveLearningShadowAutosave) -> dict[str, object]:
    return {
        "version": autosave.version,
        "queue_id": autosave.queue_id,
        "queue_fingerprint": autosave.queue_fingerprint,
        "intents": tuple(_intent_payload(intent) for intent in autosave.intents),
    }


def _envelope_payload(
    current: ActiveLearningShadowAutosave,
    previous: ActiveLearningShadowAutosave | None,
) -> dict[str, object]:
    return {
        "version": STORE_VERSION,
        "current": _autosave_payload(current),
        "previous": None if previous is None else _autosave_payload(previous),
    }


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ActiveLearningStoreError("stored shadow file has duplicate keys")
        result[key] = value
    return result


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.abspath(os.fspath(path))
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


class ActiveLearningShadowStore:
    """Persist current plus one previous shadow autosave in a private file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(f".{self.path.name}.lock")

    def load(self, queue: ActiveLearningQueue) -> ActiveLearningShadowAutosave:
        with self._locked():
            current, _previous = self._load_envelope(queue)
            return current

    def apply(
        self,
        queue: ActiveLearningQueue,
        intent: ActiveLearningIntent,
        *,
        expected_autosave_fingerprint: str,
    ) -> ActiveLearningShadowAutosave:
        with self._locked():
            current, _previous = self._load_envelope(queue)
            if expected_autosave_fingerprint != current.fingerprint:
                raise ActiveLearningStoreStaleConflict("stale autosave version")
            item = next(
                (candidate for candidate in queue.items if candidate.item_id == intent.item_id),
                None,
            )
            if (
                intent.queue_id != queue.queue_id
                or intent.expected_queue_fingerprint != queue.fingerprint
                or item is None
                or intent.expected_item_fingerprint != item.fingerprint
            ):
                raise ActiveLearningStoreStaleConflict("stale queue or item version")
            try:
                updated = transition_shadow_intent(queue, current, intent)
            except ActiveLearningConflictError as error:
                raise ActiveLearningStoreConflict("shadow intent conflict") from error
            self._write_envelope(updated, current)
            return updated

    def undo(
        self,
        queue: ActiveLearningQueue,
        *,
        expected_autosave_fingerprint: str,
    ) -> ActiveLearningShadowAutosave:
        with self._locked():
            current, previous = self._load_envelope(queue)
            if expected_autosave_fingerprint != current.fingerprint:
                raise ActiveLearningStoreStaleConflict("stale autosave version")
            if previous is None:
                raise ActiveLearningUndoUnavailable("no shadow undo is available")
            self._write_envelope(previous, None)
            return previous

    def _load_envelope(
        self, queue: ActiveLearningQueue
    ) -> tuple[ActiveLearningShadowAutosave, ActiveLearningShadowAutosave | None]:
        if not isinstance(queue, ActiveLearningQueue):
            raise ActiveLearningStoreError("queue must be an active-learning queue")
        if not self.path.exists():
            return ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint), None
        raw = self._read_private()
        try:
            payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
            envelope = _closed_mapping(payload, _ENVELOPE_KEYS, label="shadow envelope")
            if envelope["version"] != STORE_VERSION:
                raise ActiveLearningStoreError("shadow store version mismatch")
            current = _decode_autosave(envelope["current"])
            previous_value = envelope["previous"]
            previous = None if previous_value is None else _decode_autosave(previous_value)
        except (json.JSONDecodeError, UnicodeDecodeError, ActiveLearningContractError) as error:
            if isinstance(error, ActiveLearningStoreError):
                raise
            raise ActiveLearningStoreError("shadow store payload is invalid") from error
        if raw != canonical_json_bytes(_envelope_payload(current, previous)):
            raise ActiveLearningStoreError("shadow store payload is non-canonical")
        if current.queue_id != queue.queue_id or current.queue_fingerprint != queue.fingerprint:
            raise ActiveLearningStoreStaleConflict("stored shadow state is stale")
        if previous is not None and (
            previous.queue_id != queue.queue_id or previous.queue_fingerprint != queue.fingerprint
        ):
            raise ActiveLearningStoreStaleConflict("stored undo state is stale")
        self._rebind_autosave(queue, current, label="current")
        if previous is not None:
            self._rebind_autosave(queue, previous, label="previous")
        return current, previous

    @staticmethod
    def _rebind_autosave(
        queue: ActiveLearningQueue,
        autosave: ActiveLearningShadowAutosave,
        *,
        label: str,
    ) -> None:
        rebound = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
        try:
            for intent in autosave.intents:
                rebound = transition_shadow_intent(queue, rebound, intent)
        except ActiveLearningConflictError as error:
            raise ActiveLearningStoreConflict(
                f"stored {label} intent does not bind the exact queue"
            ) from error
        if rebound != autosave:
            raise ActiveLearningStoreConflict(f"stored {label} intent set is non-canonical")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with _thread_lock(self.lock_path):
            self._ensure_parent()
            descriptor = self._open_lock_file()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                self._validate_lock_file(descriptor)
                yield
            except OSError as error:
                raise ActiveLearningStoreError("shadow store lock failed") from error
            finally:
                with suppress(OSError):
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                with suppress(OSError):
                    os.close(descriptor)

    def _open_lock_file(self) -> int:
        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        created = False
        descriptor: int | None = None
        try:
            try:
                descriptor = os.open(
                    self.lock_path,
                    flags | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                created = True
            except FileExistsError:
                descriptor = os.open(self.lock_path, flags)
            if created:
                os.fchmod(descriptor, 0o600)
            self._validate_lock_file(descriptor)
            return descriptor
        except ActiveLearningStoreError:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
            raise
        except OSError as error:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
            raise ActiveLearningStoreError("shadow store lock cannot be opened") from error

    def _validate_lock_file(self, descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        path_metadata = self.lock_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(path_metadata.st_mode)
            or (metadata.st_dev, metadata.st_ino) != (path_metadata.st_dev, path_metadata.st_ino)
        ):
            raise ActiveLearningStoreError("shadow store lock must be a regular file")
        if stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size != 0:
            raise ActiveLearningStoreError("shadow store lock must be empty mode 0600")

    def _ensure_parent(self) -> None:
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.parent.is_symlink() or not self.path.parent.is_dir():
                raise ActiveLearningStoreError("shadow store parent is invalid")
        except ActiveLearningStoreError:
            raise
        except OSError as error:
            raise ActiveLearningStoreError("shadow store parent cannot be prepared") from error

    def _read_private(self) -> bytes:
        if self.path.is_symlink():
            raise ActiveLearningStoreError("shadow store path must not be a symlink")
        descriptor = -1
        try:
            descriptor = os.open(
                self.path,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ActiveLearningStoreError("shadow store path must be a regular file")
            if stat.S_IMODE(metadata.st_mode) != 0o600:
                raise ActiveLearningStoreError("shadow store file must use mode 0600")
            if metadata.st_size > MAX_STORE_BYTES:
                raise ActiveLearningStoreError("shadow store file exceeds its bound")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                raw = stream.read(MAX_STORE_BYTES + 1)
                if len(raw) > MAX_STORE_BYTES:
                    raise ActiveLearningStoreError("shadow store file exceeds its bound")
                return raw
        except ActiveLearningStoreError:
            raise
        except OSError as error:
            raise ActiveLearningStoreError("shadow store file cannot be read") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _write_envelope(
        self,
        current: ActiveLearningShadowAutosave,
        previous: ActiveLearningShadowAutosave | None,
    ) -> None:
        payload = canonical_json_bytes(_envelope_payload(current, previous))
        if len(payload) > MAX_STORE_BYTES:
            raise ActiveLearningStoreError("shadow store payload exceeds its bound")
        try:
            self._ensure_parent()
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
            )
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                os.chmod(self.path, 0o600)
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except BaseException:
                with suppress(FileNotFoundError):
                    os.unlink(temporary)
                raise
        except ActiveLearningStoreError:
            raise
        except OSError as error:
            raise ActiveLearningStoreError("shadow store file cannot be persisted") from error


__all__ = [
    "STORE_VERSION",
    "ActiveLearningShadowStore",
    "ActiveLearningStoreConflict",
    "ActiveLearningStoreError",
    "ActiveLearningStoreStaleConflict",
    "ActiveLearningUndoUnavailable",
]

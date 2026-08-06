"""Private, append-only exact-feedback ledger for drawing-card review decisions."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from ..sources.normalization import normalize_text, normalize_unit

_SCHEMA_VERSION = "DrawingCardFeedback-2.0"
_INPUT_CONTRACT_VERSION = "DrawingCardReviewDecision-1.0"
_MAX_LEDGER_BYTES = 4 * 1024 * 1024
_MAX_ENTRIES = 10_000
_MAX_LINE_BYTES = 16 * 1024
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_SAFE_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,160}")
_ACTIONS = frozenset({"confirm", "reject", "reclassify", "exclude"})
_SUBJECT_TYPES = frozenset({"row", "packet"})


def _required_text(value: str, name: str) -> str:
    result = str(value).strip()
    if not result or len(result) > 512 or "\x00" in result:
        raise ValueError(f"{name} must be a non-empty bounded string")
    if result.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", result):
        raise ValueError(f"{name} must not contain an absolute path")
    return result


def _utc_timestamp(value: str | datetime) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("created_at must be an ISO-8601 UTC timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("created_at must be UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _hashes(values: Iterable[str], name: str) -> tuple[str, ...]:
    result = tuple(sorted(set(str(value) for value in values)))
    if not result or any(_SHA256_RE.fullmatch(value) is None for value in result):
        raise ValueError(f"{name} must contain SHA-256 hashes")
    return result


def _ids(values: Iterable[str]) -> tuple[str, ...]:
    result = tuple(sorted(set(_required_text(value, "member ID") for value in values)))
    if not result:
        raise ValueError("member_ids must not be empty")
    return result


@dataclass(frozen=True)
class FeedbackContext:
    """Exact decision key. Every field participates in ``lookup_exact``."""

    tenant_id: str
    project_id: str
    normalized_work: str
    work_fingerprint: str
    proposed_category: str
    contract_position: str
    match_mode: str
    source_unit: str | None
    unit_policy: str
    input_hashes: tuple[str, ...]
    model_version: str
    rules_version: str
    subject_type: str
    member_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized_work = normalize_text(self.normalized_work)
        if not normalized_work:
            raise ValueError("normalized_work must not be empty")
        expected_fingerprint = sha256(normalized_work.encode("utf-8")).hexdigest()
        if self.work_fingerprint != expected_fingerprint:
            raise ValueError("work_fingerprint must match normalized_work")
        if self.subject_type not in _SUBJECT_TYPES:
            raise ValueError("subject_type must be row or packet")
        object.__setattr__(self, "tenant_id", _required_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "project_id", _required_text(self.project_id, "project_id"))
        object.__setattr__(self, "normalized_work", normalized_work)
        object.__setattr__(
            self, "proposed_category", _required_text(self.proposed_category, "proposed_category")
        )
        object.__setattr__(
            self, "contract_position", _required_text(self.contract_position, "contract_position")
        )
        object.__setattr__(self, "match_mode", _required_text(self.match_mode, "match_mode"))
        object.__setattr__(self, "source_unit", normalize_unit(self.source_unit))
        object.__setattr__(self, "unit_policy", _required_text(self.unit_policy, "unit_policy"))
        object.__setattr__(self, "input_hashes", _hashes(self.input_hashes, "input_hashes"))
        object.__setattr__(
            self, "model_version", _required_text(self.model_version, "model_version")
        )
        object.__setattr__(
            self, "rules_version", _required_text(self.rules_version, "rules_version")
        )
        object.__setattr__(self, "member_ids", _ids(self.member_ids))


@dataclass(frozen=True)
class FeedbackEntry:
    """A complete immutable decision event retained in private JSONL audit history."""

    context: FeedbackContext
    selected_category: str | None
    action: str
    author: str
    created_at: str | datetime
    event_id: str | None = None
    valid: bool = True
    hazards: tuple[str, ...] = field(default_factory=tuple)
    supersedes_event_id: str | None = None
    reason: str | None = None
    selected_quantity_resolution: str | None = None
    selected_cost_resolution: str | None = None

    def __post_init__(self) -> None:
        if self.action not in _ACTIONS:
            raise ValueError("action must be confirm, reject, reclassify, or exclude")
        if not isinstance(self.context, FeedbackContext):
            raise ValueError("context must be FeedbackContext")
        selected = (
            _required_text(self.selected_category, "selected_category")
            if self.selected_category is not None
            else None
        )
        if self.action in {"confirm", "reclassify"} and selected is None:
            raise ValueError("selected_category is required for confirm and reclassify")
        hazards = tuple(sorted(set(_required_text(item, "hazard") for item in self.hazards)))
        supersedes = (
            _required_text(self.supersedes_event_id, "supersedes_event_id")
            if self.supersedes_event_id is not None
            else None
        )
        reason = _required_text(self.reason, "reason") if self.reason is not None else None
        quantity_resolution, cost_resolution = _selected_resolutions(
            self.context.unit_policy,
            self.action,
            self.selected_quantity_resolution,
            self.selected_cost_resolution,
        )
        created_at = _utc_timestamp(self.created_at)
        object.__setattr__(self, "selected_category", selected)
        object.__setattr__(self, "author", _required_text(self.author, "author"))
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "hazards", hazards)
        object.__setattr__(self, "supersedes_event_id", supersedes)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "selected_quantity_resolution", quantity_resolution)
        object.__setattr__(self, "selected_cost_resolution", cost_resolution)
        event_id = self.event_id or _event_id(self)
        if _SAFE_ID_RE.fullmatch(event_id) is None:
            raise ValueError("event_id has unsupported characters")
        object.__setattr__(self, "event_id", event_id)


def _event_id(entry: FeedbackEntry) -> str:
    payload = _entry_payload(entry, include_event_id=False)
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"dcf2-{digest}"


def _entry_payload(entry: FeedbackEntry, *, include_event_id: bool = True) -> dict[str, object]:
    context = entry.context
    payload: dict[str, object] = {
        "schema_version": _SCHEMA_VERSION,
        "input_contract_version": _INPUT_CONTRACT_VERSION,
        "tenant_id": context.tenant_id,
        "project_id": context.project_id,
        "normalized_work": context.normalized_work,
        "work_fingerprint": context.work_fingerprint,
        "proposed_category": context.proposed_category,
        "selected_category": entry.selected_category,
        "contract_position": context.contract_position,
        "match_mode": context.match_mode,
        "source_unit": context.source_unit,
        "unit_policy": context.unit_policy,
        "action": entry.action,
        "input_hashes": list(context.input_hashes),
        "model_version": context.model_version,
        "rules_version": context.rules_version,
        "author": entry.author,
        "created_at": entry.created_at,
        "subject_type": context.subject_type,
        "member_ids": list(context.member_ids),
        "valid": entry.valid,
        "hazards": list(entry.hazards),
        "supersedes_event_id": entry.supersedes_event_id,
        "reason": entry.reason,
        "selected_quantity_resolution": entry.selected_quantity_resolution,
        "selected_cost_resolution": entry.selected_cost_resolution,
    }
    if include_event_id:
        payload["event_id"] = entry.event_id
    return payload


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _entry_from_payload(payload: object) -> FeedbackEntry:
    if not isinstance(payload, dict):
        raise ValueError("feedback ledger entry must be an object")
    required = set(_entry_payload(_sample_entry(), include_event_id=True))
    legacy_required = required - {
        "selected_quantity_resolution",
        "selected_cost_resolution",
    }
    if set(payload) != required and set(payload) != legacy_required:
        raise ValueError("feedback ledger entry has an unsupported schema")
    if payload["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("feedback ledger schema version is unsupported")
    if payload["input_contract_version"] != _INPUT_CONTRACT_VERSION:
        raise ValueError("feedback input contract version is unsupported")
    context = FeedbackContext(
        tenant_id=payload["tenant_id"],
        project_id=payload["project_id"],
        normalized_work=payload["normalized_work"],
        work_fingerprint=payload["work_fingerprint"],
        proposed_category=payload["proposed_category"],
        contract_position=payload["contract_position"],
        match_mode=payload["match_mode"],
        source_unit=payload["source_unit"],
        unit_policy=payload["unit_policy"],
        input_hashes=tuple(payload["input_hashes"]),
        model_version=payload["model_version"],
        rules_version=payload["rules_version"],
        subject_type=payload["subject_type"],
        member_ids=tuple(payload["member_ids"]),
    )
    entry = FeedbackEntry(
        context=context,
        selected_category=payload["selected_category"],
        action=payload["action"],
        author=payload["author"],
        created_at=payload["created_at"],
        event_id=payload["event_id"],
        valid=payload["valid"],
        hazards=tuple(payload["hazards"]),
        supersedes_event_id=payload["supersedes_event_id"],
        reason=payload["reason"],
        selected_quantity_resolution=payload.get("selected_quantity_resolution"),
        selected_cost_resolution=payload.get("selected_cost_resolution"),
    )
    # The two selected resolution fields were added to the unreleased 2.0
    # ledger.  Keep old, unambiguous entries readable, while all new writes
    # use the complete canonical form.
    if set(payload) == required and _entry_payload(entry) != payload:
        raise ValueError("feedback ledger entry is not canonical")
    return entry


def _selected_resolutions(
    unit_policy: str,
    action: str,
    quantity: str | None,
    cost: str | None,
) -> tuple[str, str]:
    """Require explicit safe saved outcomes for every replayable event.

    The small legacy compatibility branch is intentionally limited to an
    unambiguous original policy.  It makes pre-extension 2.0 records readable
    and canonical on their next write; a policy containing ``review`` never
    gains an inferred financial resolution.
    """
    if action in {"reject", "exclude"}:
        # Normalise stale callers that carried the prior confirmation modes.
        return "exclude", "exclude"
    allowed = {"include", "exclude"}
    if quantity in allowed and cost in allowed:
        return quantity, cost
    legacy = {
        "quantity_cost": ("include", "include"),
        "quantity_only": ("include", "exclude"),
        "cost_only": ("exclude", "include"),
    }.get(unit_policy)
    if legacy is not None and quantity is None and cost is None:
        return legacy
    raise ValueError("confirm and reclassify require explicit safe resolutions")


def _sample_entry() -> FeedbackEntry:
    context = FeedbackContext(
        "schema",
        "schema",
        "schema",
        sha256(b"schema").hexdigest(),
        "schema",
        "schema",
        "schema",
        None,
        "schema",
        ("0" * 64,),
        "schema",
        "schema",
        "row",
        ("schema",),
    )
    return FeedbackEntry(context, None, "exclude", "schema", "2000-01-01T00:00:00Z")


class FeedbackStore:
    """Fixed-schema ledger. Writes are atomic snapshots, never in-place appends."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append_page(self, entries: Iterable[FeedbackEntry]) -> tuple[FeedbackEntry, ...]:
        page = tuple(entries)
        if not page or len(page) > _MAX_ENTRIES:
            raise ValueError("feedback page must contain between 1 and 10000 entries")
        if any(not isinstance(entry, FeedbackEntry) for entry in page):
            raise ValueError("feedback page must contain FeedbackEntry values")
        existing = self._read()
        by_id = {entry.event_id: entry for entry in existing}
        additions: list[FeedbackEntry] = []
        for entry in page:
            previous = by_id.get(entry.event_id)
            if previous is not None:
                if previous != entry:
                    raise ValueError("conflicting duplicate event_id")
                continue
            by_id[entry.event_id] = entry
            additions.append(entry)
        if not additions:
            return page
        self._atomic_write((*existing, *additions))
        return page

    def lookup_exact(self, context: FeedbackContext) -> FeedbackEntry | None:
        if not isinstance(context, FeedbackContext):
            raise ValueError("context must be FeedbackContext")
        entries = self._read()
        latest = next((entry for entry in reversed(entries) if entry.context == context), None)
        # An explicit invalidation is a complete later decision, not a deletion.
        # It must block replay of an older matching event from the same audit trail.
        if latest is not None and not latest.valid and latest.supersedes_event_id:
            return None
        superseded = {entry.supersedes_event_id for entry in entries if entry.supersedes_event_id}
        for entry in reversed(entries):
            if (
                entry.context == context
                and entry.event_id not in superseded
                and entry.valid
                and not entry.hazards
            ):
                return entry
        return None

    def invalidate(
        self, event_id: str, author: str, created_at: str | datetime, reason: str
    ) -> FeedbackEntry:
        target_id = _required_text(event_id, "event_id")
        entries = self._read()
        target = next((entry for entry in reversed(entries) if entry.event_id == target_id), None)
        if target is None:
            raise KeyError(target_id)
        clone = FeedbackEntry(
            context=target.context,
            selected_category=target.selected_category,
            action=target.action,
            author=author,
            created_at=created_at,
            valid=False,
            hazards=target.hazards,
            supersedes_event_id=target.event_id,
            reason=reason,
            selected_quantity_resolution=target.selected_quantity_resolution,
            selected_cost_resolution=target.selected_cost_resolution,
        )
        self.append_page((clone,))
        return clone

    def _read(self) -> tuple[FeedbackEntry, ...]:
        if not self.path.exists():
            return ()
        if self.path.is_symlink():
            raise ValueError("feedback ledger must not be a symlink")
        if self.path.stat().st_size > _MAX_LEDGER_BYTES:
            raise ValueError("feedback ledger exceeds bounded read limit")
        result: list[FeedbackEntry] = []
        with self.path.open("rb") as handle:
            for raw_line in handle:
                if len(raw_line) > _MAX_LINE_BYTES:
                    raise ValueError("feedback ledger line exceeds bounded read limit")
                if not raw_line.strip():
                    raise ValueError("feedback ledger contains an empty line")
                try:
                    result.append(_entry_from_payload(json.loads(raw_line)))
                except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
                    raise ValueError("feedback ledger contains invalid JSON") from error
                if len(result) > _MAX_ENTRIES:
                    raise ValueError("feedback ledger exceeds entry limit")
        return tuple(result)

    def _atomic_write(self, entries: Iterable[FeedbackEntry]) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        content = "".join(_canonical_json(_entry_payload(entry)) + "\n" for entry in entries)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
            self._fsync_directory()
        except BaseException:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise

    def _fsync_directory(self) -> None:
        try:
            descriptor = os.open(self.path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)

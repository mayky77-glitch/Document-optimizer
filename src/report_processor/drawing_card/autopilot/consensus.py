"""Private, exact machine-consensus records; malformed data never activates rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from ..models import DrawingSourceRow, TargetWorkCategory
from ..sources.normalization import normalize_text, normalize_unit

_SCHEMA = "MachineConsensus-1.0"
_DECISIONS = frozenset({"include", "exclude"})


@dataclass(frozen=True, slots=True)
class MachineConsensus:
    normalized_text: str
    unit: str | None
    source_type: str | None
    rules_version: str
    category: TargetWorkCategory | None
    quantity_decision: str
    cost_decision: str
    fingerprint: str

    @property
    def key(self) -> tuple[str, str | None, str | None, str]:
        return (self.normalized_text, self.unit, self.source_type, self.rules_version)


class MachineConsensusStore:
    """Exact lookup store with conflicts and bad records excluded by construction."""

    def __init__(
        self,
        records: tuple[MachineConsensus, ...],
        blocked_keys: frozenset[tuple[str, str | None, str | None, str]] = frozenset(),
    ) -> None:
        grouped: dict[tuple[str, str | None, str | None, str], list[MachineConsensus]] = {}
        for record in records:
            grouped.setdefault(record.key, []).append(record)
        self._records = {
            key: entries[0]
            for key, entries in grouped.items()
            if len({entry.fingerprint for entry in entries}) == 1
        }
        self._conflicts = {
            key
            for key, entries in grouped.items()
            if len({entry.fingerprint for entry in entries}) > 1
        }
        self._blocked_keys = blocked_keys

    def lookup(self, row: DrawingSourceRow, rules_version: str) -> MachineConsensus | None:
        return self._records.get(self._key(row, rules_version))

    def requires_manual_review(self, row: DrawingSourceRow, rules_version: str) -> bool:
        key = self._key(row, rules_version)
        if key in self._conflicts or key in self._blocked_keys:
            return True
        prefix = key[:3]
        return any(
            record_key[:3] == prefix and record_key[3] != rules_version
            for record_key in self._records
        )

    @staticmethod
    def _key(row: DrawingSourceRow, rules_version: str) -> tuple[str, str | None, str | None, str]:
        return (
            normalize_text(row.work_name_raw),
            normalize_unit(row.unit_raw),
            normalize_text(row.source_document_type) or None,
            rules_version,
        )


def load_machine_consensus(path: Path | None) -> MachineConsensusStore:
    """Load a private JSONL artifact. Every invalid line is deliberately ignored."""
    if path is None or not path.is_file() or path.is_symlink():
        return MachineConsensusStore(())
    records: list[MachineConsensus] = []
    blocked_keys: set[tuple[str, str | None, str | None, str]] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return MachineConsensusStore(())
    for line in lines:
        record = _parse_record(line)
        if record is not None:
            records.append(record)
        else:
            key = _record_key(line)
            if key is not None:
                blocked_keys.add(key)
    return MachineConsensusStore(tuple(records), frozenset(blocked_keys))


def _parse_record(line: str) -> MachineConsensus | None:
    try:
        payload = json.loads(line)
        if not isinstance(payload, dict) or payload.get("schema") != _SCHEMA:
            return None
        if payload.get("provenance") != "codex-consensus-v1":
            return None
        if payload.get("active") is not True or payload.get("confirmed") is not False:
            return None
        if payload.get("reusable_as_human_feedback") is not False:
            return None
        if payload.get("confirmed_by") != "machine-consensus":
            return None
        normalized_text = payload["normalized_text"]
        rules_version = payload["rules_version"]
        quantity = payload["quantity_decision"]
        cost = payload["cost_decision"]
        fingerprint = payload["fingerprint"]
        category_value = payload.get("category")
        unit = payload.get("unit")
        source_type = payload.get("source_type")
        if not all(isinstance(item, str) for item in (normalized_text, rules_version, fingerprint)):
            return None
        if (
            not normalized_text
            or not rules_version
            or quantity not in _DECISIONS
            or cost not in _DECISIONS
        ):
            return None
        if not isinstance(unit, str | type(None)) or not isinstance(source_type, str | type(None)):
            return None
        category = TargetWorkCategory(category_value) if category_value is not None else None
        if category is None and (quantity == "include" or cost == "include"):
            return None
        canonical = _canonical_payload(
            normalized_text=normalize_text(normalized_text),
            unit=normalize_unit(unit),
            source_type=normalize_text(source_type) or None,
            rules_version=rules_version,
            category=category.value if category else None,
            quantity_decision=quantity,
            cost_decision=cost,
        )
        if sha256(canonical.encode()).hexdigest() != fingerprint:
            return None
        return MachineConsensus(
            normalized_text=normalize_text(normalized_text),
            unit=normalize_unit(unit),
            source_type=normalize_text(source_type) or None,
            rules_version=rules_version,
            category=category,
            quantity_decision=quantity,
            cost_decision=cost,
            fingerprint=fingerprint,
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _record_key(line: str) -> tuple[str, str | None, str | None, str] | None:
    """Keep enough malformed-record identity to send only that exact row to review."""
    try:
        payload = json.loads(line)
        if not isinstance(payload, dict):
            return None
        normalized_text = payload.get("normalized_text")
        rules_version = payload.get("rules_version")
        unit = payload.get("unit")
        source_type = payload.get("source_type")
        if not isinstance(normalized_text, str) or not normalized_text:
            return None
        if not isinstance(rules_version, str) or not rules_version:
            return None
        if not isinstance(unit, str | type(None)) or not isinstance(source_type, str | type(None)):
            return None
        return (
            normalize_text(normalized_text),
            normalize_unit(unit),
            normalize_text(source_type) or None,
            rules_version,
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def consensus_fingerprint(
    *,
    normalized_text: str,
    unit: str | None,
    source_type: str | None,
    rules_version: str,
    category: str | None,
    quantity_decision: str,
    cost_decision: str,
) -> str:
    """Return the canonical fingerprint required by a machine-consensus record."""
    return sha256(
        _canonical_payload(
            normalized_text=normalize_text(normalized_text),
            unit=normalize_unit(unit),
            source_type=normalize_text(source_type) or None,
            rules_version=rules_version,
            category=category,
            quantity_decision=quantity_decision,
            cost_decision=cost_decision,
        ).encode()
    ).hexdigest()


def _canonical_payload(**values: str | None) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

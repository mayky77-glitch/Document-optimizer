"""Private, job-local autosave for reconciliation batch decisions."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from report_processor.reconciliation_review import ReviewAction, ReviewDecision, ReviewMode

from .reconciliation_state import BatchReviewDecision, ReconciliationReviewState


class ReconciliationBatchStore:
    """Persist only controlled decision values and one compatible version fingerprint."""

    def __init__(self, directory: Path) -> None:
        self.path = Path(directory) / "reconciliation-review.json"

    def save(self, state: ReconciliationReviewState) -> None:
        payload = {
            "contract": "ReconciliationBatchAutosave-1.0",
            "fingerprint": state.version_fingerprint,
            "packages": _dump_batch(state.package_decisions),
            "families": _dump_batch(state.family_decisions),
            "groups": _dump_review(state.group_decisions),
            "rows": _dump_review(state.row_decisions),
        }
        temporary = self.path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(
                    payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)

    def restore(self, state: ReconciliationReviewState) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return False
        if (
            not isinstance(payload, Mapping)
            or payload.get("contract") != "ReconciliationBatchAutosave-1.0"
        ):
            return False
        if payload.get("fingerprint") != state.version_fingerprint:
            return False
        try:
            state.restore(
                package_decisions=_load_batch(payload.get("packages")),
                family_decisions=_load_batch(payload.get("families")),
                group_decisions=_load_review(payload.get("groups"), target="group"),
                row_decisions=_load_review(payload.get("rows"), target="row"),
            )
        except (KeyError, TypeError, ValueError):
            return False
        return True


def _dump_batch(values: Mapping[str, BatchReviewDecision]) -> dict[str, dict[str, str | None]]:
    return {
        key: {
            "action": value.action.value,
            "mode": value.mode.value if value.mode else None,
            "category_id": value.target_category,
            "version": value.version,
        }
        for key, value in sorted(values.items())
    }


def _dump_review(values: Mapping[str, ReviewDecision]) -> dict[str, dict[str, str | None]]:
    return {
        key: {
            "action": value.action.value,
            "mode": value.mode.value if value.mode else None,
            "category_id": value.target_category,
            "version": value.version,
        }
        for key, value in sorted(values.items())
    }


def _load_batch(value: object) -> dict[str, BatchReviewDecision]:
    values = _records(value)
    return {
        key: BatchReviewDecision(
            _action(record), _mode(record), _category(record), _version(record)
        )
        for key, record in values.items()
    }


def _load_review(value: object, *, target: str) -> dict[str, ReviewDecision]:
    values = _records(value)
    return {
        key: ReviewDecision(
            _action(record),
            _mode(record),
            _category(record),
            group_id=key if target == "group" else None,
            row_id=key if target == "row" else None,
            version=_version(record),
        )
        for key, record in values.items()
    }


def _records(value: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        raise ValueError("invalid decision snapshot")
    result: dict[str, Mapping[str, object]] = {}
    for key, record in value.items():
        if not isinstance(key, str) or not key or not isinstance(record, Mapping):
            raise ValueError("invalid decision snapshot")
        result[key] = record
    return result


def _action(record: Mapping[str, object]) -> ReviewAction:
    try:
        return ReviewAction(record.get("action"))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid action") from error


def _mode(record: Mapping[str, object]) -> ReviewMode | None:
    value = record.get("mode")
    if value is None:
        return None
    try:
        return ReviewMode(value)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid mode") from error


def _category(record: Mapping[str, object]) -> str | None:
    value = record.get("category_id")
    if value is None or isinstance(value, str):
        return value
    raise ValueError("invalid category")


def _version(record: Mapping[str, object]) -> str | None:
    value = record.get("version")
    if value is None or isinstance(value, str):
        return value
    raise ValueError("invalid version")

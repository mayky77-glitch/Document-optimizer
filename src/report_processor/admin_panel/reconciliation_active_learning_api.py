"""Unregistered parser and controlled facade for active-learning shadow state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from report_processor.admin_panel.reconciliation_active_learning_store import (
    ActiveLearningShadowStore,
    ActiveLearningStoreConflict,
    ActiveLearningStoreError,
    ActiveLearningStoreStaleConflict,
    ActiveLearningUndoUnavailable,
)
from report_processor.reconciliation_patterns.active_learning import (
    INTENT_VERSION,
    MAX_MEMBER_REFS,
    MAX_SPLIT_GROUPS,
    ActiveLearningContractError,
    ActiveLearningIntent,
    ActiveLearningQueue,
    ActiveLearningShadowAutosave,
    ShadowAction,
)

_INTENT_KEYS = {
    "version",
    "queue_id",
    "expected_queue_fingerprint",
    "item_id",
    "expected_item_fingerprint",
    "action",
    "split_member_refs",
}


class ActiveLearningApiCode(StrEnum):
    OK = "ok"
    INVALID_REQUEST = "invalid_request"
    CONFLICT = "conflict"
    STALE_STATE = "stale_state"
    UNDO_UNAVAILABLE = "undo_unavailable"
    STORE_INVALID = "store_invalid"


@dataclass(frozen=True, slots=True)
class ActiveLearningApiResult:
    code: ActiveLearningApiCode
    autosave: ActiveLearningShadowAutosave | None = None


def _parse_split_refs(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, list) or len(value) > MAX_SPLIT_GROUPS:
        raise ActiveLearningContractError("split_member_refs must be a bounded array")
    groups: list[tuple[str, ...]] = []
    total = 0
    for group in value:
        if not isinstance(group, list):
            raise ActiveLearningContractError("split groups must be arrays")
        total += len(group)
        if total > MAX_MEMBER_REFS or any(not isinstance(ref, str) for ref in group):
            raise ActiveLearningContractError("split membership is invalid")
        groups.append(tuple(group))
    return tuple(groups)


def parse_active_learning_intent(payload: object) -> ActiveLearningIntent:
    """Parse the exact closed JSON shape into a validated core intent."""

    if not isinstance(payload, dict) or set(payload) != _INTENT_KEYS:
        raise ActiveLearningContractError("active-learning intent shape is invalid")
    if payload["version"] != INTENT_VERSION:
        raise ActiveLearningContractError("active-learning intent version mismatch")
    try:
        action = ShadowAction(payload["action"])
    except (TypeError, ValueError) as error:
        raise ActiveLearningContractError("active-learning action is invalid") from error
    return ActiveLearningIntent(
        queue_id=payload["queue_id"],
        expected_queue_fingerprint=payload["expected_queue_fingerprint"],
        item_id=payload["item_id"],
        expected_item_fingerprint=payload["expected_item_fingerprint"],
        action=action,
        split_member_refs=_parse_split_refs(payload["split_member_refs"]),
        version=payload["version"],
    )


def apply_active_learning_payload(
    store: ActiveLearningShadowStore,
    queue: ActiveLearningQueue,
    payload: object,
    *,
    expected_autosave_fingerprint: str,
) -> ActiveLearningApiResult:
    try:
        intent = parse_active_learning_intent(payload)
    except ActiveLearningContractError:
        return ActiveLearningApiResult(ActiveLearningApiCode.INVALID_REQUEST)
    try:
        autosave = store.apply(
            queue,
            intent,
            expected_autosave_fingerprint=expected_autosave_fingerprint,
        )
    except ActiveLearningStoreStaleConflict:
        return ActiveLearningApiResult(ActiveLearningApiCode.STALE_STATE)
    except ActiveLearningStoreConflict:
        return ActiveLearningApiResult(ActiveLearningApiCode.CONFLICT)
    except ActiveLearningStoreError:
        return ActiveLearningApiResult(ActiveLearningApiCode.STORE_INVALID)
    return ActiveLearningApiResult(ActiveLearningApiCode.OK, autosave)


def undo_active_learning(
    store: ActiveLearningShadowStore,
    queue: ActiveLearningQueue,
    *,
    expected_autosave_fingerprint: str,
) -> ActiveLearningApiResult:
    try:
        autosave = store.undo(
            queue,
            expected_autosave_fingerprint=expected_autosave_fingerprint,
        )
    except ActiveLearningUndoUnavailable:
        return ActiveLearningApiResult(ActiveLearningApiCode.UNDO_UNAVAILABLE)
    except ActiveLearningStoreStaleConflict:
        return ActiveLearningApiResult(ActiveLearningApiCode.STALE_STATE)
    except ActiveLearningStoreConflict:
        return ActiveLearningApiResult(ActiveLearningApiCode.CONFLICT)
    except ActiveLearningStoreError:
        return ActiveLearningApiResult(ActiveLearningApiCode.STORE_INVALID)
    return ActiveLearningApiResult(ActiveLearningApiCode.OK, autosave)


__all__ = [
    "ActiveLearningApiCode",
    "ActiveLearningApiResult",
    "apply_active_learning_payload",
    "parse_active_learning_intent",
    "undo_active_learning",
]

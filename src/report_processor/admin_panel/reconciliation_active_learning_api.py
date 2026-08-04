"""Unregistered parser and controlled facade for active-learning shadow state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

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

SHADOW_REQUEST_VERSION: Final = "ActiveLearningShadowRequest-1.0"
_REQUEST_KEYS = {
    "version",
    "queue_id",
    "expected_queue_fingerprint",
    "expected_autosave_fingerprint",
    "item_id",
    "expected_item_fingerprint",
    "action",
    "split_member_refs",
}
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
class ActiveLearningShadowRequest:
    """The exact closed request schema accepted by the unregistered facade."""

    queue_id: str
    expected_queue_fingerprint: str
    expected_autosave_fingerprint: str
    item_id: str
    expected_item_fingerprint: str
    action: ShadowAction
    split_member_refs: tuple[tuple[str, ...], ...]
    version: str = SHADOW_REQUEST_VERSION

    def __post_init__(self) -> None:
        if self.version != SHADOW_REQUEST_VERSION:
            raise ActiveLearningContractError("shadow request version mismatch")
        # The core intent constructor owns all opaque-token and canonical split checks.
        ActiveLearningIntent(
            queue_id=self.queue_id,
            expected_queue_fingerprint=self.expected_queue_fingerprint,
            item_id=self.item_id,
            expected_item_fingerprint=self.expected_item_fingerprint,
            action=self.action,
            split_member_refs=self.split_member_refs,
        )
        ActiveLearningShadowAutosave(
            self.queue_id,
            self.expected_autosave_fingerprint,
        )

    def to_intent(self) -> ActiveLearningIntent:
        return ActiveLearningIntent(
            queue_id=self.queue_id,
            expected_queue_fingerprint=self.expected_queue_fingerprint,
            item_id=self.item_id,
            expected_item_fingerprint=self.expected_item_fingerprint,
            action=self.action,
            split_member_refs=self.split_member_refs,
        )


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


def parse_active_learning_shadow_request(payload: object) -> ActiveLearningShadowRequest:
    """Parse exactly one closed wire shape; no outer CAS token is accepted."""

    if not isinstance(payload, dict) or set(payload) != _REQUEST_KEYS:
        raise ActiveLearningContractError("active-learning shadow request shape is invalid")
    if payload["version"] != SHADOW_REQUEST_VERSION:
        raise ActiveLearningContractError("active-learning shadow request version mismatch")
    try:
        action = ShadowAction(payload["action"])
    except (TypeError, ValueError) as error:
        raise ActiveLearningContractError("active-learning action is invalid") from error
    return ActiveLearningShadowRequest(
        queue_id=payload["queue_id"],
        expected_queue_fingerprint=payload["expected_queue_fingerprint"],
        expected_autosave_fingerprint=payload["expected_autosave_fingerprint"],
        item_id=payload["item_id"],
        expected_item_fingerprint=payload["expected_item_fingerprint"],
        action=action,
        split_member_refs=_parse_split_refs(payload["split_member_refs"]),
    )


def parse_active_learning_intent(payload: object) -> ActiveLearningIntent:
    """Preserve the lower-level core-intent parser for non-web callers.

    The web facade must use :func:`parse_active_learning_shadow_request`; this
    compatibility function deliberately has no autosave token because an intent
    is not itself a wire request.
    """

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
    expected_autosave_fingerprint: str | None = None,
) -> ActiveLearningApiResult:
    try:
        request = parse_active_learning_shadow_request(payload)
        if (
            expected_autosave_fingerprint is not None
            and expected_autosave_fingerprint != request.expected_autosave_fingerprint
        ):
            raise ActiveLearningContractError("outer autosave token does not match request")
    except ActiveLearningContractError:
        return ActiveLearningApiResult(ActiveLearningApiCode.INVALID_REQUEST)
    try:
        autosave = store.apply(
            queue,
            request.to_intent(),
            expected_autosave_fingerprint=request.expected_autosave_fingerprint,
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
    "SHADOW_REQUEST_VERSION",
    "ActiveLearningApiCode",
    "ActiveLearningApiResult",
    "ActiveLearningShadowRequest",
    "apply_active_learning_payload",
    "parse_active_learning_intent",
    "parse_active_learning_shadow_request",
    "undo_active_learning",
]

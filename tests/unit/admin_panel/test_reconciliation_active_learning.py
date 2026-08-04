"""Unit contract for the unregistered active-learning parser and API facade."""

from __future__ import annotations

import json

import pytest

from report_processor.admin_panel.reconciliation_active_learning_api import (
    SHADOW_REQUEST_VERSION,
    ActiveLearningApiCode,
    apply_active_learning_payload,
    parse_active_learning_shadow_request,
    undo_active_learning,
)
from report_processor.admin_panel.reconciliation_active_learning_store import (
    ActiveLearningShadowStore,
)
from report_processor.reconciliation_patterns.active_learning import (
    ActiveLearningMode,
    ActiveLearningPresentation,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
)


def _ref(token: str) -> str:
    return "sha256:" + token * 64


def _item(*, row_override_count: int = 0) -> ActiveLearningQueueItem:
    return ActiveLearningQueueItem(
        kind=QueueItemKind.PATTERN,
        pattern_ref=_ref("1"),
        package_ref=None,
        source_head_ref=_ref("2"),
        item_version_ref=_ref("3"),
        source_fingerprint_refs=(_ref("4"),),
        category_ref=_ref("5"),
        mode=ActiveLearningMode.QUANTITY_COST,
        member_refs=(_ref("6"), _ref("7")),
        coverage_family_count=1,
        coverage_group_count=2,
        affected_row_count=3,
        affected_cost_minor_units=4,
        hard_negative_proximity=5,
        uncertainty_signal_count=6,
        novelty_signal_count=7,
        document_frequency_count=8,
        expected_action_reduction=9,
        row_override_count=row_override_count,
        presentation=ActiveLearningPresentation(
            summary_codes=(PresentationCode.PATTERN_CANDIDATE,),
        ),
        allowed_actions=tuple(ShadowAction),
    )


def _queue(item: ActiveLearningQueueItem | None = None) -> ActiveLearningQueue:
    return ActiveLearningQueue(_ref("8"), (_ref("9"),), (item or _item(),))


def _payload(queue: ActiveLearningQueue, item: ActiveLearningQueueItem) -> dict[str, object]:
    return {
        "version": SHADOW_REQUEST_VERSION,
        "queue_id": queue.queue_id,
        "expected_queue_fingerprint": queue.fingerprint,
        "expected_autosave_fingerprint": "sha256:" + "0" * 64,
        "item_id": item.item_id,
        "expected_item_fingerprint": item.fingerprint,
        "action": ShadowAction.REJECT.value,
        "split_member_refs": [],
    }


def test_parser_accepts_only_the_exact_closed_intent_shape() -> None:
    item = _item()
    queue = _queue(item)
    payload = _payload(queue, item)
    payload["expected_autosave_fingerprint"] = "sha256:" + "a" * 64

    parsed = parse_active_learning_shadow_request(payload)

    assert parsed.action is ShadowAction.REJECT
    assert parsed.split_member_refs == ()
    for malformed in (
        {key: value for key, value in payload.items() if key != "item_id"},
        {**payload, "raw_text": "not allowed"},
        {**payload, "action": "promote"},
        {**payload, "version": "ActiveLearningShadowRequest-1.1"},
        {**payload, "split_member_refs": False},
    ):
        with pytest.raises(ValueError):
            parse_active_learning_shadow_request(malformed)


def test_api_facade_returns_controlled_codes_without_route_registration(tmp_path) -> None:
    item = _item()
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    initial = store.load(queue)
    payload = _payload(queue, item)
    payload["expected_autosave_fingerprint"] = initial.fingerprint

    saved = apply_active_learning_payload(
        store,
        queue,
        payload,
    )
    stale = apply_active_learning_payload(
        store,
        queue,
        payload,
    )
    malformed = apply_active_learning_payload(
        store,
        queue,
        {**payload, "raw_text": "forbidden"},
        expected_autosave_fingerprint=saved.autosave.fingerprint,  # type: ignore[union-attr]
    )
    undone = undo_active_learning(
        store,
        queue,
        expected_autosave_fingerprint=saved.autosave.fingerprint,  # type: ignore[union-attr]
    )
    unavailable = undo_active_learning(
        store,
        queue,
        expected_autosave_fingerprint=undone.autosave.fingerprint,  # type: ignore[union-attr]
    )

    assert saved.code is ActiveLearningApiCode.OK
    assert stale.code is ActiveLearningApiCode.STALE_STATE
    assert malformed.code is ActiveLearningApiCode.INVALID_REQUEST
    assert undone.code is ActiveLearningApiCode.OK
    assert unavailable.code is ActiveLearningApiCode.UNDO_UNAVAILABLE
    assert "Route" not in json.dumps(sorted(vars(__import__(__name__))))


def test_api_row_override_conflict_does_not_create_shadow_state(tmp_path) -> None:
    item = _item(row_override_count=1)
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    initial = store.load(queue)
    payload = _payload(queue, item)
    payload["expected_autosave_fingerprint"] = initial.fingerprint

    result = apply_active_learning_payload(
        store,
        queue,
        payload,
    )

    assert result.code is ActiveLearningApiCode.CONFLICT
    assert not store.path.exists()

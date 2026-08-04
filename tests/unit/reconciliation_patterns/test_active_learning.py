"""Adversarial tests for deterministic active-learning ranking and shadow intents."""

from __future__ import annotations

import dataclasses

import pytest

from report_processor.reconciliation_patterns.active_learning import (
    ActiveLearningConflictError,
    ActiveLearningContractError,
    ActiveLearningIntent,
    ActiveLearningMode,
    ActiveLearningPresentation,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    ActiveLearningShadowAutosave,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
    transition_shadow_intent,
)


def _ref(token: str) -> str:
    return "sha256:" + (token if len(token) == 64 else token * 64)


def _item(token: str, **changes: object) -> ActiveLearningQueueItem:
    values: dict[str, object] = dict(
        kind=QueueItemKind.PATTERN,
        pattern_ref=_ref(token),
        package_ref=None,
        source_head_ref=_ref("0"),
        item_version_ref=_ref("a"),
        source_fingerprint_refs=(_ref("b"),),
        category_ref=_ref("c"),
        mode=ActiveLearningMode.QUANTITY_COST,
        member_refs=(_ref("d"), _ref("e")),
        coverage_family_count=10,
        coverage_group_count=10,
        affected_row_count=9,
        affected_cost_minor_units=8,
        hard_negative_proximity=7,
        uncertainty_signal_count=6,
        novelty_signal_count=5,
        document_frequency_count=4,
        expected_action_reduction=3,
        row_override_count=0,
        presentation=ActiveLearningPresentation(
            summary_codes=(PresentationCode.PATTERN_CANDIDATE,),
            difference_codes=(PresentationCode.CATEGORY_DIFFERENCE,),
            exception_codes=(),
        ),
        allowed_actions=tuple(ShadowAction),
    )
    values.update(changes)
    return ActiveLearningQueueItem(**values)  # type: ignore[arg-type]


def _queue(*items: ActiveLearningQueueItem) -> ActiveLearningQueue:
    return ActiveLearningQueue(_ref("f"), (_ref("0"),), items)


def _intent(
    queue: ActiveLearningQueue,
    item: ActiveLearningQueueItem,
    action: ShadowAction,
    *,
    split: tuple[tuple[str, ...], ...] = (),
) -> ActiveLearningIntent:
    return ActiveLearningIntent(
        queue.queue_id,
        queue.fingerprint,
        item.item_id,
        item.fingerprint,
        action,
        split,
    )


def test_server_ranking_uses_every_fixed_tie_break_and_is_permutation_invariant() -> None:
    baseline = _item("1")
    ranked = (
        dataclasses.replace(baseline, pattern_ref=_ref("2"), expected_action_reduction=4),
        dataclasses.replace(baseline, pattern_ref=_ref("3"), affected_row_count=10),
        dataclasses.replace(baseline, pattern_ref=_ref("4"), affected_cost_minor_units=9),
        dataclasses.replace(baseline, pattern_ref=_ref("5"), hard_negative_proximity=8),
        dataclasses.replace(baseline, pattern_ref=_ref("6"), uncertainty_signal_count=7),
        dataclasses.replace(baseline, pattern_ref=_ref("7"), novelty_signal_count=6),
        dataclasses.replace(baseline, pattern_ref=_ref("8"), document_frequency_count=5),
        baseline,
    )

    queue = _queue(*reversed(ranked))
    permuted = _queue(*ranked)

    assert queue == permuted
    assert queue.items == ranked


def test_opaque_id_is_the_final_stable_tie_break() -> None:
    first, second = _item("1"), _item("2")
    queue = _queue(second, first)

    assert tuple(item.item_id for item in queue.items) == tuple(
        sorted((first.item_id, second.item_id))
    )


@pytest.mark.parametrize(
    "action",
    (ShadowAction.ACCEPT_PATTERN, ShadowAction.CASE_ONLY, ShadowAction.REJECT),
)
def test_non_split_shadow_actions_transition_without_mutating_inputs(action: ShadowAction) -> None:
    item = _item("1")
    queue = _queue(item)
    state = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
    intent = _intent(queue, item, action)

    updated = transition_shadow_intent(queue, state, intent)

    assert state.intents == ()
    assert updated.intents == (intent,)
    assert updated.fingerprint != state.fingerprint


def test_split_requires_complete_sorted_unique_membership() -> None:
    item = _item("1")
    queue = _queue(item)
    state = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
    valid = ((_ref("d"),), (_ref("e"),))

    updated = transition_shadow_intent(
        queue, state, _intent(queue, item, ShadowAction.SPLIT, split=valid)
    )

    assert updated.intents[0].split_member_refs == valid
    for invalid in (
        ((_ref("d"),),),
        ((_ref("d"), _ref("d")), (_ref("e"),)),
        ((_ref("e"),), (_ref("d"),)),
    ):
        with pytest.raises((ActiveLearningContractError, ActiveLearningConflictError)):
            transition_shadow_intent(
                queue, state, _intent(queue, item, ShadowAction.SPLIT, split=invalid)
            )


def test_split_is_impossible_for_an_item_with_fewer_than_two_members() -> None:
    with pytest.raises(ActiveLearningContractError):
        _item("1", member_refs=(_ref("d"),))


def test_stale_queue_or_item_fails_closed_with_zero_mutation() -> None:
    item = _item("1")
    queue = _queue(item)
    state = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
    valid = _intent(queue, item, ShadowAction.REJECT)
    stale_intents = (
        dataclasses.replace(valid, expected_queue_fingerprint=_ref("1")),
        dataclasses.replace(valid, expected_item_fingerprint=_ref("2")),
    )

    for stale in stale_intents:
        with pytest.raises(ActiveLearningConflictError):
            transition_shadow_intent(queue, state, stale)
        assert state.intents == ()


def test_autosave_rejects_an_embedded_intent_for_another_queue_revision() -> None:
    item = _item("1")
    queue = _queue(item)
    stale = dataclasses.replace(
        _intent(queue, item, ShadowAction.REJECT),
        expected_queue_fingerprint=_ref("1"),
    )

    with pytest.raises(ActiveLearningContractError):
        ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint, (stale,))


def test_forbidden_action_and_row_override_fail_closed() -> None:
    restricted = _item("1", allowed_actions=(ShadowAction.REJECT,))
    overridden = _item("2", row_override_count=1)
    for item, action in (
        (restricted, ShadowAction.ACCEPT_PATTERN),
        (overridden, ShadowAction.REJECT),
    ):
        queue = _queue(item)
        state = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
        with pytest.raises(ActiveLearningConflictError):
            transition_shadow_intent(queue, state, _intent(queue, item, action))
        assert state.intents == ()


def test_latest_shadow_intent_replaces_same_item_deterministically() -> None:
    item = _item("1")
    queue = _queue(item)
    state = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
    accepted = transition_shadow_intent(
        queue, state, _intent(queue, item, ShadowAction.ACCEPT_PATTERN)
    )
    rejected = transition_shadow_intent(queue, accepted, _intent(queue, item, ShadowAction.REJECT))

    assert rejected.intents[0].action is ShadowAction.REJECT
    assert rejected.autosave_id == state.autosave_id
    assert rejected.fingerprint != accepted.fingerprint

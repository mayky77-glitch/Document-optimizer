"""Exact public web queue/request contract checks for inert Wave 8 recovery."""

from __future__ import annotations

import dataclasses

import pytest

from report_processor.admin_panel.reconciliation_active_learning_adapter import (
    WEB_QUEUE_VERSION,
    ActiveLearningWebItem,
    ActiveLearningWebQueue,
    ActiveLearningWebSplitProposal,
    project_active_learning_web_queue,
)
from report_processor.admin_panel.reconciliation_active_learning_api import (
    SHADOW_REQUEST_VERSION,
    parse_active_learning_shadow_request,
)
from report_processor.reconciliation_patterns.active_learning import (
    ActiveLearningContractError,
    ActiveLearningMode,
    ActiveLearningPresentation,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    ActiveLearningShadowAutosave,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
)


def _ref(token: str) -> str:
    return "sha256:" + token * 64


def _item() -> ActiveLearningQueueItem:
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
        row_override_count=0,
        presentation=ActiveLearningPresentation(
            summary_codes=(PresentationCode.PATTERN_CANDIDATE,),
            difference_codes=(PresentationCode.CATEGORY_DIFFERENCE,),
        ),
        allowed_actions=tuple(ShadowAction),
    )


def _queue() -> tuple[ActiveLearningQueue, ActiveLearningShadowAutosave, ActiveLearningQueueItem]:
    item = _item()
    queue = ActiveLearningQueue(_ref("8"), (_ref("9"),), (item,))
    return queue, ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint), item


def test_web_queue_is_frozen_closed_privacy_safe_and_keeps_server_order() -> None:
    queue, autosave, item = _queue()
    proposal = ActiveLearningWebSplitProposal(
        item.item_id,
        item.fingerprint,
        ((_ref("6"),), (_ref("7"),)),
    )

    web_queue = project_active_learning_web_queue(queue, autosave, split_proposals=(proposal,))
    payload = web_queue.as_payload()

    assert WEB_QUEUE_VERSION == "ActiveLearningWebQueue-1.0"
    assert web_queue.__dataclass_params__.frozen
    assert "__slots__" in vars(ActiveLearningWebQueue)
    assert tuple(web.item_id for web in web_queue.items) == tuple(
        source.item_id for source in queue.items
    )
    assert set(payload) == {
        "version",
        "queue_id",
        "expected_queue_fingerprint",
        "expected_autosave_fingerprint",
        "items",
    }
    assert set(payload["items"][0]) == {
        "item_id",
        "expected_item_fingerprint",
        "kind",
        "mode",
        "coverage_family_count",
        "coverage_group_count",
        "affected_row_count",
        "affected_cost_minor_units",
        "document_frequency_count",
        "expected_action_reduction",
        "summary_codes",
        "difference_codes",
        "exception_codes",
        "allowed_actions",
        "split_member_refs",
    }
    forbidden = {"title", "category_label", "reason", "slots", "examples", "evidence", "model"}
    assert not forbidden & set(payload["items"][0])
    assert payload["items"][0]["allowed_actions"] == [action.value for action in ShadowAction]


def test_web_projection_hides_split_without_an_exact_complete_proposal() -> None:
    queue, autosave, item = _queue()
    web_queue = project_active_learning_web_queue(queue, autosave)

    assert ShadowAction.SPLIT not in web_queue.items[0].allowed_actions
    assert web_queue.items[0].split_member_refs == ()
    with pytest.raises(ActiveLearningContractError):
        project_active_learning_web_queue(
            queue,
            autosave,
            split_proposals=(
                ActiveLearningWebSplitProposal(
                    item.item_id, item.fingerprint, ((_ref("6"),), (_ref("a"),))
                ),
            ),
        )


def test_exported_web_dtos_reject_forged_or_unbounded_values() -> None:
    queue, autosave, item = _queue()
    valid = project_active_learning_web_queue(queue, autosave).items[0]

    with pytest.raises(ActiveLearningContractError):
        dataclasses.replace(valid, affected_row_count=True)
    with pytest.raises(ActiveLearningContractError):
        dataclasses.replace(valid, allowed_actions=("reject",))  # type: ignore[arg-type]
    forged_values = {field.name: getattr(valid, field.name) for field in dataclasses.fields(valid)}
    forged_values["split_member_refs"] = ((_ref("6"),), (_ref("7"),))
    with pytest.raises(ActiveLearningContractError):
        ActiveLearningWebItem(**forged_values)  # type: ignore[arg-type]
    with pytest.raises(ActiveLearningContractError):
        parse_active_learning_shadow_request(
            {
                "version": SHADOW_REQUEST_VERSION,
                "queue_id": queue.queue_id,
                "expected_queue_fingerprint": queue.fingerprint,
                "expected_autosave_fingerprint": "not-a-token",
                "item_id": item.item_id,
                "expected_item_fingerprint": item.fingerprint,
                "action": ShadowAction.REJECT.value,
                "split_member_refs": [],
            }
        )


def test_projection_to_closed_request_roundtrip_binds_all_three_cas_tokens() -> None:
    queue, autosave, item = _queue()
    proposal = ActiveLearningWebSplitProposal(
        item.item_id,
        item.fingerprint,
        ((_ref("6"),), (_ref("7"),)),
    )
    web_queue = project_active_learning_web_queue(queue, autosave, split_proposals=(proposal,))
    web_item = web_queue.items[0]
    request_payload = {
        "version": SHADOW_REQUEST_VERSION,
        "queue_id": queue.queue_id,
        "expected_queue_fingerprint": queue.fingerprint,
        "expected_autosave_fingerprint": autosave.fingerprint,
        "item_id": web_item.item_id,
        "expected_item_fingerprint": web_item.expected_item_fingerprint,
        "action": ShadowAction.SPLIT.value,
        "split_member_refs": [list(group) for group in web_item.split_member_refs],
    }

    request = parse_active_learning_shadow_request(request_payload)

    assert request.to_intent().item_id == item.item_id
    assert request.expected_autosave_fingerprint == autosave.fingerprint
    for malformed in (
        {
            key: value
            for key, value in request_payload.items()
            if key != "expected_autosave_fingerprint"
        },
        {**request_payload, "evidence": "forbidden"},
        {**request_payload, "version": "ActiveLearningShadowRequest-1.1"},
    ):
        with pytest.raises(ActiveLearningContractError):
            parse_active_learning_shadow_request(malformed)


def test_web_projection_rejects_stale_autosave_before_any_public_dto_exists() -> None:
    queue, autosave, _ = _queue()
    with pytest.raises(ActiveLearningContractError):
        project_active_learning_web_queue(
            queue,
            dataclasses.replace(autosave, queue_fingerprint=_ref("a")),
        )

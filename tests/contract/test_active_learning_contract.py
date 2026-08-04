"""Contract checks for inert Wave 8 active-learning DTOs."""

from __future__ import annotations

import dataclasses

import pytest

from report_processor.reconciliation_patterns import active_learning as al


def _ref(token: str) -> str:
    return "sha256:" + token * 64


def _item() -> al.ActiveLearningQueueItem:
    return al.ActiveLearningQueueItem(
        kind=al.QueueItemKind.PATTERN,
        pattern_ref=_ref("1"),
        package_ref=None,
        source_head_ref=_ref("0"),
        item_version_ref=_ref("2"),
        source_fingerprint_refs=(_ref("3"), _ref("4")),
        category_ref=_ref("5"),
        mode=al.ActiveLearningMode.QUANTITY_COST,
        member_refs=(_ref("6"), _ref("7")),
        coverage_family_count=8,
        coverage_group_count=9,
        affected_row_count=10,
        affected_cost_minor_units=11,
        hard_negative_proximity=12,
        uncertainty_signal_count=13,
        novelty_signal_count=14,
        document_frequency_count=15,
        expected_action_reduction=16,
        row_override_count=0,
        presentation=al.ActiveLearningPresentation(
            summary_codes=(al.PresentationCode.PATTERN_CANDIDATE,),
            difference_codes=(al.PresentationCode.CATEGORY_DIFFERENCE,),
            exception_codes=(),
        ),
        allowed_actions=tuple(al.ShadowAction),
    )


def _queue(item: al.ActiveLearningQueueItem | None = None) -> al.ActiveLearningQueue:
    return al.ActiveLearningQueue(
        queue_ref=_ref("8"),
        source_fingerprint_refs=(_ref("9"),),
        items=(item or _item(),),
    )


def test_public_models_are_frozen_slotted_and_versioned() -> None:
    assert al.QUEUE_VERSION == "ActiveLearningQueue-1.0"
    assert al.INTENT_VERSION == "ActiveLearningIntent-1.0"
    assert al.AUTOSAVE_VERSION == "ActiveLearningShadowAutosave-1.0"
    for model in (
        al.ActiveLearningQueueItem,
        al.ActiveLearningPresentation,
        al.ActiveLearningQueue,
        al.ActiveLearningIntent,
        al.ActiveLearningShadowAutosave,
    ):
        assert model.__dataclass_params__.frozen
        assert "__slots__" in vars(model)


def test_contract_shape_is_privacy_safe_and_integer_only() -> None:
    forbidden = {"text", "path", "coordinate", "vector", "confidence", "score", "name"}
    fields = {
        field.name
        for model in (
            al.ActiveLearningQueueItem,
            al.ActiveLearningPresentation,
            al.ActiveLearningQueue,
            al.ActiveLearningIntent,
            al.ActiveLearningShadowAutosave,
        )
        for field in dataclasses.fields(model)
    }
    assert not any(token in field for token in forbidden for field in fields)
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), affected_cost_minor_units=1.5)  # type: ignore[arg-type]
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), category_ref="concrete works")
    with pytest.raises(al.ActiveLearningContractError):
        al.canonical_json_bytes({"confidence": 0.9})


def test_kind_refs_codes_and_bounds_are_closed() -> None:
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), pattern_ref=None)
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), package_ref=_ref("a"))
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), coverage_family_count=-1)
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), coverage_group_count=al.MAX_INTEGER_AGGREGATE + 1)
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(_item(), member_refs=(_ref("6"),) * 2)
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(
            _item(),
            presentation=al.ActiveLearningPresentation(
                summary_codes=(al.PresentationCode.PATTERN_CANDIDATE,) * 2,
            ),
        )


def test_stable_identity_and_revision_bind_only_consequential_fields() -> None:
    item = _item()
    revised = dataclasses.replace(item, coverage_family_count=item.coverage_family_count + 1)
    assert item.item_id == revised.item_id
    assert item.fingerprint != revised.fingerprint
    new_source_head = dataclasses.replace(item, source_head_ref=_ref("a"))
    assert item.item_id != new_source_head.item_id
    queue = _queue(item)
    revised_queue = _queue(revised)
    assert queue.queue_id == revised_queue.queue_id
    assert queue.fingerprint != revised_queue.fingerprint


def test_package_kind_rejects_pattern_only_actions() -> None:
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(
            _item(),
            kind=al.QueueItemKind.PACKAGE,
            pattern_ref=None,
            package_ref=_ref("a"),
            presentation=al.ActiveLearningPresentation(
                summary_codes=(al.PresentationCode.PACKAGE_CANDIDATE,),
            ),
            allowed_actions=(al.ShadowAction.ACCEPT_PATTERN,),
        )


@pytest.mark.parametrize(
    ("model", "field_name", "bad_version"),
    (
        (_item(), "version", "ActiveLearningQueue-1.1"),
        (_queue(), "version", "ActiveLearningQueue-1.1"),
        (
            al.ActiveLearningIntent(
                _queue().queue_id,
                _queue().fingerprint,
                _item().item_id,
                _item().fingerprint,
                al.ShadowAction.REJECT,
            ),
            "version",
            "ActiveLearningIntent-1.1",
        ),
        (
            al.ActiveLearningShadowAutosave(
                _queue().queue_id,
                _queue().fingerprint,
            ),
            "version",
            "ActiveLearningShadowAutosave-1.1",
        ),
    ),
)
def test_exact_contract_versions_are_mandatory(
    model: object, field_name: str, bad_version: str
) -> None:
    with pytest.raises(al.ActiveLearningContractError):
        dataclasses.replace(model, **{field_name: bad_version})

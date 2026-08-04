"""Controlled, inert web projection for active-learning shadow review.

The projection intentionally contains no business evidence.  It is a transport
boundary between the already-private core queue and an optional, unregistered UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from report_processor.reconciliation_patterns.active_learning import (
    INTENT_VERSION,
    MAX_INTEGER_AGGREGATE,
    ActiveLearningContractError,
    ActiveLearningIntent,
    ActiveLearningMode,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    ActiveLearningShadowAutosave,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
)

WEB_QUEUE_VERSION: Final = "ActiveLearningWebQueue-1.0"


@dataclass(frozen=True, slots=True)
class ActiveLearningWebSplitProposal:
    """An exact, opaque server proposal which may make ``split`` available."""

    item_id: str
    expected_item_fingerprint: str
    split_member_refs: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        ActiveLearningIntent(
            queue_id="active-learning-queue-" + "0" * 64,
            expected_queue_fingerprint="sha256:" + "0" * 64,
            item_id=self.item_id,
            expected_item_fingerprint=self.expected_item_fingerprint,
            action=ShadowAction.SPLIT,
            split_member_refs=self.split_member_refs,
            version=INTENT_VERSION,
        )


@dataclass(frozen=True, slots=True)
class ActiveLearningWebItem:
    item_id: str
    expected_item_fingerprint: str
    kind: QueueItemKind
    mode: ActiveLearningMode
    coverage_family_count: int
    coverage_group_count: int
    affected_row_count: int
    affected_cost_minor_units: int
    document_frequency_count: int
    expected_action_reduction: int
    summary_codes: tuple[PresentationCode, ...]
    difference_codes: tuple[PresentationCode, ...]
    exception_codes: tuple[PresentationCode, ...]
    allowed_actions: tuple[ShadowAction, ...]
    split_member_refs: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        ActiveLearningIntent(
            queue_id="active-learning-queue-" + "0" * 64,
            expected_queue_fingerprint="sha256:" + "0" * 64,
            item_id=self.item_id,
            expected_item_fingerprint=self.expected_item_fingerprint,
            action=ShadowAction.REJECT,
        )
        if not isinstance(self.kind, QueueItemKind) or not isinstance(
            self.mode, ActiveLearningMode
        ):
            raise ActiveLearningContractError("web item kind and mode must be controlled")
        for value in (
            self.coverage_family_count,
            self.coverage_group_count,
            self.affected_row_count,
            self.affected_cost_minor_units,
            self.document_frequency_count,
            self.expected_action_reduction,
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= MAX_INTEGER_AGGREGATE
            ):
                raise ActiveLearningContractError("web item aggregate is out of bounds")
        for codes in (self.summary_codes, self.difference_codes, self.exception_codes):
            if (
                not isinstance(codes, tuple)
                or len(codes) != len(set(codes))
                or any(not isinstance(code, PresentationCode) for code in codes)
            ):
                raise ActiveLearningContractError("web item presentation codes must be controlled")
        if (
            not isinstance(self.allowed_actions, tuple)
            or not self.allowed_actions
            or len(self.allowed_actions) != len(set(self.allowed_actions))
            or any(not isinstance(action, ShadowAction) for action in self.allowed_actions)
        ):
            raise ActiveLearningContractError("web item actions must be controlled")
        if self.kind is QueueItemKind.PACKAGE and any(
            action not in {ShadowAction.SPLIT, ShadowAction.REJECT}
            for action in self.allowed_actions
        ):
            raise ActiveLearningContractError("package web items only allow split or reject")
        if self.split_member_refs:
            ActiveLearningIntent(
                queue_id="active-learning-queue-" + "0" * 64,
                expected_queue_fingerprint="sha256:" + "0" * 64,
                item_id=self.item_id,
                expected_item_fingerprint=self.expected_item_fingerprint,
                action=ShadowAction.SPLIT,
                split_member_refs=self.split_member_refs,
            )
        if ShadowAction.SPLIT in self.allowed_actions and not self.split_member_refs:
            raise ActiveLearningContractError("web split action requires an exact proposal")
        if self.split_member_refs and ShadowAction.SPLIT not in self.allowed_actions:
            raise ActiveLearningContractError("web split proposal requires its action")

    def as_payload(self) -> dict[str, object]:
        """Return the closed JSON-compatible public item shape."""

        return {
            "item_id": self.item_id,
            "expected_item_fingerprint": self.expected_item_fingerprint,
            "kind": self.kind.value,
            "mode": self.mode.value,
            "coverage_family_count": self.coverage_family_count,
            "coverage_group_count": self.coverage_group_count,
            "affected_row_count": self.affected_row_count,
            "affected_cost_minor_units": self.affected_cost_minor_units,
            "document_frequency_count": self.document_frequency_count,
            "expected_action_reduction": self.expected_action_reduction,
            "summary_codes": [code.value for code in self.summary_codes],
            "difference_codes": [code.value for code in self.difference_codes],
            "exception_codes": [code.value for code in self.exception_codes],
            "allowed_actions": [action.value for action in self.allowed_actions],
            "split_member_refs": [list(group) for group in self.split_member_refs],
        }


@dataclass(frozen=True, slots=True)
class ActiveLearningWebQueue:
    queue_id: str
    expected_queue_fingerprint: str
    expected_autosave_fingerprint: str
    items: tuple[ActiveLearningWebItem, ...]
    version: str = WEB_QUEUE_VERSION

    def __post_init__(self) -> None:
        if self.version != WEB_QUEUE_VERSION:
            raise ActiveLearningContractError("web queue version mismatch")
        if not isinstance(self.items, tuple):
            raise ActiveLearningContractError("web queue items must be a tuple")
        if any(not isinstance(item, ActiveLearningWebItem) for item in self.items):
            raise ActiveLearningContractError("web queue items must be controlled records")
        ActiveLearningShadowAutosave(
            self.queue_id,
            self.expected_queue_fingerprint,
        )
        ActiveLearningShadowAutosave(
            self.queue_id,
            self.expected_autosave_fingerprint,
        )
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ActiveLearningContractError("web queue item IDs must be unique")

    def as_payload(self) -> dict[str, object]:
        """Return the exact public queue shape, retaining server-owned item order."""

        return {
            "version": self.version,
            "queue_id": self.queue_id,
            "expected_queue_fingerprint": self.expected_queue_fingerprint,
            "expected_autosave_fingerprint": self.expected_autosave_fingerprint,
            "items": [item.as_payload() for item in self.items],
        }


def _validated_split(
    item: ActiveLearningQueueItem,
    proposal: ActiveLearningWebSplitProposal | None,
) -> tuple[tuple[str, ...], ...]:
    if proposal is None:
        return ()
    if proposal.item_id != item.item_id or proposal.expected_item_fingerprint != item.fingerprint:
        raise ActiveLearningContractError("split proposal does not bind the source item")
    # Reuse the core's canonical split validation, then require the exact source set.
    intent = ActiveLearningIntent(
        queue_id="active-learning-queue-" + "0" * 64,
        expected_queue_fingerprint="sha256:" + "0" * 64,
        item_id=proposal.item_id,
        expected_item_fingerprint=proposal.expected_item_fingerprint,
        action=ShadowAction.SPLIT,
        split_member_refs=proposal.split_member_refs,
        version=INTENT_VERSION,
    )
    members = tuple(member for group in intent.split_member_refs for member in group)
    if tuple(sorted(members)) != item.member_refs:
        raise ActiveLearningContractError("split proposal must preserve exact source membership")
    return intent.split_member_refs


def _web_item(
    item: ActiveLearningQueueItem,
    proposal: ActiveLearningWebSplitProposal | None,
) -> ActiveLearningWebItem:
    split_member_refs = _validated_split(item, proposal)
    allowed_actions = tuple(
        action
        for action in item.allowed_actions
        if action is not ShadowAction.SPLIT or split_member_refs
    )
    return ActiveLearningWebItem(
        item_id=item.item_id,
        expected_item_fingerprint=item.fingerprint,
        kind=item.kind,
        mode=item.mode,
        coverage_family_count=item.coverage_family_count,
        coverage_group_count=item.coverage_group_count,
        affected_row_count=item.affected_row_count,
        affected_cost_minor_units=item.affected_cost_minor_units,
        document_frequency_count=item.document_frequency_count,
        expected_action_reduction=item.expected_action_reduction,
        summary_codes=item.presentation.summary_codes,
        difference_codes=item.presentation.difference_codes,
        exception_codes=item.presentation.exception_codes,
        allowed_actions=allowed_actions,
        split_member_refs=split_member_refs,
    )


def project_active_learning_web_queue(
    queue: ActiveLearningQueue,
    autosave: ActiveLearningShadowAutosave,
    *,
    split_proposals: tuple[ActiveLearningWebSplitProposal, ...] = (),
) -> ActiveLearningWebQueue:
    """Project one exact queue/autosave pair without reordering or enriching it."""

    if not isinstance(queue, ActiveLearningQueue) or not isinstance(
        autosave, ActiveLearningShadowAutosave
    ):
        raise ActiveLearningContractError("web projection requires controlled queue and autosave")
    if autosave.queue_id != queue.queue_id or autosave.queue_fingerprint != queue.fingerprint:
        raise ActiveLearningContractError("web projection requires an exact autosave revision")
    if not isinstance(split_proposals, tuple) or any(
        not isinstance(proposal, ActiveLearningWebSplitProposal) for proposal in split_proposals
    ):
        raise ActiveLearningContractError("split proposals must be controlled records")
    proposals = {proposal.item_id: proposal for proposal in split_proposals}
    if len(proposals) != len(split_proposals):
        raise ActiveLearningContractError("split proposals must have unique item IDs")
    source_item_ids = {item.item_id for item in queue.items}
    if not set(proposals).issubset(source_item_ids):
        raise ActiveLearningContractError("split proposal is not in the source queue")
    if any(
        ShadowAction.SPLIT
        not in next(
            item.allowed_actions for item in queue.items if item.item_id == proposal.item_id
        )
        for proposal in split_proposals
    ):
        raise ActiveLearningContractError("split proposal is not allowed for its source item")
    return ActiveLearningWebQueue(
        queue_id=queue.queue_id,
        expected_queue_fingerprint=queue.fingerprint,
        expected_autosave_fingerprint=autosave.fingerprint,
        items=tuple(_web_item(item, proposals.get(item.item_id)) for item in queue.items),
    )


def project_active_learning_queue(
    *,
    queue_ref: str,
    source_fingerprint_refs: tuple[str, ...],
    items: tuple[ActiveLearningQueueItem, ...],
) -> ActiveLearningQueue:
    """Compatibility helper for creating the deterministic core queue."""

    if not isinstance(items, tuple) or any(
        not isinstance(item, ActiveLearningQueueItem) for item in items
    ):
        raise ActiveLearningContractError("projection requires validated frozen queue items")
    return ActiveLearningQueue(queue_ref, source_fingerprint_refs, items)


__all__ = [
    "WEB_QUEUE_VERSION",
    "ActiveLearningWebItem",
    "ActiveLearningWebQueue",
    "ActiveLearningWebSplitProposal",
    "project_active_learning_queue",
    "project_active_learning_web_queue",
]

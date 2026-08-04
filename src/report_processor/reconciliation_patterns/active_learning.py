"""Privacy-safe active-learning queue and inert shadow-intent contracts.

This module deliberately has no persistence or reconciliation runtime dependencies.  It
orders already-projected opaque records and validates shadow-only operator intent.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum

QUEUE_VERSION = "ActiveLearningQueue-1.0"
INTENT_VERSION = "ActiveLearningIntent-1.0"
AUTOSAVE_VERSION = "ActiveLearningShadowAutosave-1.0"

MAX_QUEUE_ITEMS = 512
MAX_SOURCE_FINGERPRINT_REFS = 128
MAX_MEMBER_REFS = 512
MAX_PRESENTATION_CODES = 32
MAX_SPLIT_GROUPS = 64
MAX_INTEGER_AGGREGATE = 2_147_483_647

_SHA_REF = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ITEM_ID = re.compile(r"active-learning-item-[0-9a-f]{64}\Z")
_QUEUE_ID = re.compile(r"active-learning-queue-[0-9a-f]{64}\Z")


class ActiveLearningContractError(ValueError):
    """An active-learning contract is malformed or non-canonical."""


class ActiveLearningConflictError(ActiveLearningContractError):
    """A valid shadow intent cannot be applied to the exact supplied queue state."""


class QueueItemKind(StrEnum):
    PATTERN = "pattern"
    PACKAGE = "package"


class ActiveLearningMode(StrEnum):
    QUANTITY_COST = "quantity_cost"
    COST_ONLY = "cost_only"


class ShadowAction(StrEnum):
    ACCEPT_PATTERN = "accept_pattern"
    CASE_ONLY = "case_only"
    SPLIT = "split"
    REJECT = "reject"


class PresentationCode(StrEnum):
    """Closed UI message vocabulary; consumers provide localized labels."""

    PATTERN_CANDIDATE = "pattern_candidate"
    PACKAGE_CANDIDATE = "package_candidate"
    CATEGORY_DIFFERENCE = "category_difference"
    MODE_DIFFERENCE = "mode_difference"
    UNIT_DIFFERENCE = "unit_difference"
    CRITICAL_SIGNATURE_DIFFERENCE = "critical_signature_difference"
    TYPED_SIGNATURE_DIFFERENCE = "typed_signature_difference"
    HARD_NEGATIVE = "hard_negative"
    AUTHORITY_UNATTESTED = "authority_unattested"
    CANNOT_LINK = "cannot_link"
    OUTLIER = "outlier"


def _canonical_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ActiveLearningContractError("canonical mappings require string keys")
        return {key: _canonical_value(item) for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical_value(getattr(value, field.name)) for field in fields(value)}
    raise ActiveLearningContractError("unsupported active-learning contract value")


def canonical_json_bytes(value: object) -> bytes:
    """Encode the supported integer-only contract subset deterministically."""

    try:
        return json.dumps(
            _canonical_value(value),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ActiveLearningContractError("canonical contract value required") from error


def sha256_fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _opaque_id(prefix: str, value: object) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"{prefix}-{digest}"


def _require_sha_ref(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or _SHA_REF.fullmatch(value) is None:
        raise ActiveLearningContractError(f"{field_name} must be an opaque sha256 reference")
    return value


def _require_count(value: object, *, field_name: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_INTEGER_AGGREGATE
    ):
        raise ActiveLearningContractError(f"{field_name} is out of bounds")
    return value


def _canonical_refs(
    values: object,
    *,
    field_name: str,
    minimum: int = 0,
    maximum: int = MAX_MEMBER_REFS,
) -> tuple[str, ...]:
    if not isinstance(values, tuple) or not minimum <= len(values) <= maximum:
        raise ActiveLearningContractError(f"{field_name} count is out of bounds")
    refs = tuple(_require_sha_ref(value, field_name=field_name) for value in values)
    if len(refs) != len(set(refs)):
        raise ActiveLearningContractError(f"{field_name} must be unique")
    return tuple(sorted(refs))


def _canonical_codes(values: object, *, field_name: str) -> tuple[PresentationCode, ...]:
    if not isinstance(values, tuple) or len(values) > MAX_PRESENTATION_CODES:
        raise ActiveLearningContractError(f"{field_name} count is out of bounds")
    if any(not isinstance(value, PresentationCode) for value in values):
        raise ActiveLearningContractError(f"{field_name} must contain controlled codes")
    if len(values) != len(set(values)):
        raise ActiveLearningContractError(f"{field_name} must be unique")
    return tuple(sorted(values, key=lambda value: value.value))


def _canonical_actions(values: object, *, kind: QueueItemKind) -> tuple[ShadowAction, ...]:
    if not isinstance(values, tuple) or not values:
        raise ActiveLearningContractError("allowed_actions must be a non-empty tuple")
    if any(not isinstance(value, ShadowAction) for value in values):
        raise ActiveLearningContractError("allowed_actions must contain controlled actions")
    if len(values) != len(set(values)):
        raise ActiveLearningContractError("allowed_actions must be unique")
    if kind is QueueItemKind.PACKAGE and any(
        value not in {ShadowAction.SPLIT, ShadowAction.REJECT} for value in values
    ):
        raise ActiveLearningContractError("package items only allow split or reject")
    order = {value: index for index, value in enumerate(ShadowAction)}
    return tuple(sorted(values, key=order.__getitem__))


@dataclass(frozen=True, slots=True)
class ActiveLearningPresentation:
    """Bounded controlled display facts; labels remain outside the contract."""

    summary_codes: tuple[PresentationCode, ...]
    difference_codes: tuple[PresentationCode, ...] = ()
    exception_codes: tuple[PresentationCode, ...] = ()

    def __post_init__(self) -> None:
        summary = _canonical_codes(self.summary_codes, field_name="summary_codes")
        if not summary:
            raise ActiveLearningContractError("summary_codes must be non-empty")
        object.__setattr__(self, "summary_codes", summary)
        object.__setattr__(
            self,
            "difference_codes",
            _canonical_codes(self.difference_codes, field_name="difference_codes"),
        )
        object.__setattr__(
            self,
            "exception_codes",
            _canonical_codes(self.exception_codes, field_name="exception_codes"),
        )


@dataclass(frozen=True, slots=True)
class ActiveLearningQueueItem:
    kind: QueueItemKind
    pattern_ref: str | None
    package_ref: str | None
    source_head_ref: str
    item_version_ref: str
    source_fingerprint_refs: tuple[str, ...]
    category_ref: str
    mode: ActiveLearningMode
    member_refs: tuple[str, ...]
    coverage_family_count: int
    coverage_group_count: int
    affected_row_count: int
    affected_cost_minor_units: int
    hard_negative_proximity: int
    uncertainty_signal_count: int
    novelty_signal_count: int
    document_frequency_count: int
    expected_action_reduction: int
    row_override_count: int
    presentation: ActiveLearningPresentation
    allowed_actions: tuple[ShadowAction, ...]
    version: str = QUEUE_VERSION

    def __post_init__(self) -> None:
        if self.version != QUEUE_VERSION:
            raise ActiveLearningContractError("queue item version mismatch")
        if not isinstance(self.kind, QueueItemKind):
            raise ActiveLearningContractError("kind must be controlled")
        if self.kind is QueueItemKind.PATTERN:
            _require_sha_ref(self.pattern_ref, field_name="pattern_ref")
            if self.package_ref is not None:
                raise ActiveLearningContractError("pattern items cannot carry package_ref")
        else:
            _require_sha_ref(self.package_ref, field_name="package_ref")
            if self.pattern_ref is not None:
                raise ActiveLearningContractError("package items cannot carry pattern_ref")
        _require_sha_ref(self.source_head_ref, field_name="source_head_ref")
        _require_sha_ref(self.item_version_ref, field_name="item_version_ref")
        object.__setattr__(
            self,
            "source_fingerprint_refs",
            _canonical_refs(
                self.source_fingerprint_refs,
                field_name="source_fingerprint_refs",
                minimum=1,
                maximum=MAX_SOURCE_FINGERPRINT_REFS,
            ),
        )
        _require_sha_ref(self.category_ref, field_name="category_ref")
        if not isinstance(self.mode, ActiveLearningMode):
            raise ActiveLearningContractError("mode must be controlled")
        object.__setattr__(
            self,
            "member_refs",
            _canonical_refs(
                self.member_refs,
                field_name="member_refs",
                minimum=1,
                maximum=MAX_MEMBER_REFS,
            ),
        )
        for field_name in (
            "coverage_family_count",
            "coverage_group_count",
            "affected_row_count",
            "affected_cost_minor_units",
            "hard_negative_proximity",
            "uncertainty_signal_count",
            "novelty_signal_count",
            "document_frequency_count",
            "expected_action_reduction",
            "row_override_count",
        ):
            _require_count(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.presentation, ActiveLearningPresentation):
            raise ActiveLearningContractError("presentation must be controlled")
        required_summary = (
            PresentationCode.PATTERN_CANDIDATE
            if self.kind is QueueItemKind.PATTERN
            else PresentationCode.PACKAGE_CANDIDATE
        )
        if required_summary not in self.presentation.summary_codes:
            raise ActiveLearningContractError("presentation must identify the queue item kind")
        object.__setattr__(
            self,
            "allowed_actions",
            _canonical_actions(self.allowed_actions, kind=self.kind),
        )

    @property
    def item_id(self) -> str:
        return _opaque_id(
            "active-learning-item",
            {
                "kind": self.kind,
                "pattern_ref": self.pattern_ref,
                "package_ref": self.package_ref,
                "source_head_ref": self.source_head_ref,
            },
        )

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "active_learning_item_revision",
                "item_id": self.item_id,
                "item_version_ref": self.item_version_ref,
                "source_fingerprint_refs": self.source_fingerprint_refs,
                "category_ref": self.category_ref,
                "mode": self.mode,
                "member_refs": self.member_refs,
                "coverage_family_count": self.coverage_family_count,
                "coverage_group_count": self.coverage_group_count,
                "affected_row_count": self.affected_row_count,
                "affected_cost_minor_units": self.affected_cost_minor_units,
                "hard_negative_proximity": self.hard_negative_proximity,
                "uncertainty_signal_count": self.uncertainty_signal_count,
                "novelty_signal_count": self.novelty_signal_count,
                "document_frequency_count": self.document_frequency_count,
                "expected_action_reduction": self.expected_action_reduction,
                "row_override_count": self.row_override_count,
                "presentation": self.presentation,
                "allowed_actions": self.allowed_actions,
            }
        )

    @property
    def ranking_key(self) -> tuple[int | str, ...]:
        return (
            -self.expected_action_reduction,
            -self.affected_row_count,
            -self.affected_cost_minor_units,
            -self.hard_negative_proximity,
            -self.uncertainty_signal_count,
            -self.novelty_signal_count,
            -self.document_frequency_count,
            self.item_id,
        )


@dataclass(frozen=True, slots=True)
class ActiveLearningQueue:
    queue_ref: str
    source_fingerprint_refs: tuple[str, ...]
    items: tuple[ActiveLearningQueueItem, ...]
    version: str = QUEUE_VERSION

    def __post_init__(self) -> None:
        if self.version != QUEUE_VERSION:
            raise ActiveLearningContractError("queue version mismatch")
        _require_sha_ref(self.queue_ref, field_name="queue_ref")
        object.__setattr__(
            self,
            "source_fingerprint_refs",
            _canonical_refs(
                self.source_fingerprint_refs,
                field_name="source_fingerprint_refs",
                minimum=1,
                maximum=MAX_SOURCE_FINGERPRINT_REFS,
            ),
        )
        if not isinstance(self.items, tuple) or len(self.items) > MAX_QUEUE_ITEMS:
            raise ActiveLearningContractError("queue item count is out of bounds")
        if any(not isinstance(item, ActiveLearningQueueItem) for item in self.items):
            raise ActiveLearningContractError("queue items must be controlled records")
        if len({item.item_id for item in self.items}) != len(self.items):
            raise ActiveLearningContractError("queue item IDs must be unique")
        object.__setattr__(
            self,
            "items",
            tuple(sorted(self.items, key=lambda item: item.ranking_key)),
        )

    @property
    def queue_id(self) -> str:
        return _opaque_id("active-learning-queue", {"queue_ref": self.queue_ref})

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "active_learning_queue_revision",
                "queue_id": self.queue_id,
                "source_fingerprint_refs": self.source_fingerprint_refs,
                "item_fingerprints": tuple(item.fingerprint for item in self.items),
            }
        )


@dataclass(frozen=True, slots=True)
class ActiveLearningIntent:
    queue_id: str
    expected_queue_fingerprint: str
    item_id: str
    expected_item_fingerprint: str
    action: ShadowAction
    split_member_refs: tuple[tuple[str, ...], ...] = ()
    version: str = INTENT_VERSION

    def __post_init__(self) -> None:
        if self.version != INTENT_VERSION:
            raise ActiveLearningContractError("intent version mismatch")
        if not isinstance(self.queue_id, str) or _QUEUE_ID.fullmatch(self.queue_id) is None:
            raise ActiveLearningContractError("queue_id must be an opaque queue ID")
        _require_sha_ref(
            self.expected_queue_fingerprint,
            field_name="expected_queue_fingerprint",
        )
        if not isinstance(self.item_id, str) or _ITEM_ID.fullmatch(self.item_id) is None:
            raise ActiveLearningContractError("item_id must be an opaque item ID")
        _require_sha_ref(
            self.expected_item_fingerprint,
            field_name="expected_item_fingerprint",
        )
        if not isinstance(self.action, ShadowAction):
            raise ActiveLearningContractError("action must be controlled")
        split = self.split_member_refs
        if not isinstance(split, tuple):
            raise ActiveLearningContractError("split_member_refs must be a tuple")
        if self.action is not ShadowAction.SPLIT:
            if split:
                raise ActiveLearningContractError("only split actions may carry split membership")
            return
        if not 2 <= len(split) <= MAX_SPLIT_GROUPS:
            raise ActiveLearningContractError("split group count is out of bounds")
        groups = tuple(
            _canonical_refs(group, field_name="split group", minimum=1) for group in split
        )
        if groups != split or tuple(sorted(groups)) != groups:
            raise ActiveLearningContractError("split membership must be canonical and sorted")
        flattened = tuple(member for group in groups for member in group)
        if len(flattened) > MAX_MEMBER_REFS or len(flattened) != len(set(flattened)):
            raise ActiveLearningContractError("split membership must be bounded and unique")

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "active_learning_intent_revision",
                "queue_id": self.queue_id,
                "expected_queue_fingerprint": self.expected_queue_fingerprint,
                "item_id": self.item_id,
                "expected_item_fingerprint": self.expected_item_fingerprint,
                "action": self.action,
                "split_member_refs": self.split_member_refs,
            }
        )


@dataclass(frozen=True, slots=True)
class ActiveLearningShadowAutosave:
    queue_id: str
    queue_fingerprint: str
    intents: tuple[ActiveLearningIntent, ...] = ()
    version: str = AUTOSAVE_VERSION

    def __post_init__(self) -> None:
        if self.version != AUTOSAVE_VERSION:
            raise ActiveLearningContractError("autosave version mismatch")
        if not isinstance(self.queue_id, str) or _QUEUE_ID.fullmatch(self.queue_id) is None:
            raise ActiveLearningContractError("queue_id must be an opaque queue ID")
        _require_sha_ref(self.queue_fingerprint, field_name="queue_fingerprint")
        if not isinstance(self.intents, tuple) or len(self.intents) > MAX_QUEUE_ITEMS:
            raise ActiveLearningContractError("autosave intent count is out of bounds")
        if any(not isinstance(intent, ActiveLearningIntent) for intent in self.intents):
            raise ActiveLearningContractError("autosave intents must be controlled records")
        if any(intent.queue_id != self.queue_id for intent in self.intents):
            raise ActiveLearningContractError("autosave intents must bind the same queue")
        if any(
            intent.expected_queue_fingerprint != self.queue_fingerprint for intent in self.intents
        ):
            raise ActiveLearningContractError("autosave intents must bind the exact queue revision")
        if len({intent.item_id for intent in self.intents}) != len(self.intents):
            raise ActiveLearningContractError("autosave may contain one intent per item")
        object.__setattr__(
            self,
            "intents",
            tuple(sorted(self.intents, key=lambda intent: intent.item_id)),
        )

    @property
    def autosave_id(self) -> str:
        return _opaque_id("active-learning-autosave", {"queue_id": self.queue_id})

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(
            {
                "version": self.version,
                "kind": "active_learning_shadow_autosave_revision",
                "autosave_id": self.autosave_id,
                "queue_fingerprint": self.queue_fingerprint,
                "intent_fingerprints": tuple(intent.fingerprint for intent in self.intents),
            }
        )


def transition_shadow_intent(
    queue: ActiveLearningQueue,
    state: ActiveLearningShadowAutosave,
    intent: ActiveLearningIntent,
) -> ActiveLearningShadowAutosave:
    """Purely apply one exact-version intent to an immutable shadow autosave."""

    if not isinstance(queue, ActiveLearningQueue):
        raise ActiveLearningContractError("queue must be an active-learning queue")
    if not isinstance(state, ActiveLearningShadowAutosave):
        raise ActiveLearningContractError("state must be a shadow autosave")
    if not isinstance(intent, ActiveLearningIntent):
        raise ActiveLearningContractError("intent must be an active-learning intent")
    if (
        state.queue_id != queue.queue_id
        or state.queue_fingerprint != queue.fingerprint
        or intent.queue_id != queue.queue_id
        or intent.expected_queue_fingerprint != queue.fingerprint
    ):
        raise ActiveLearningConflictError("stale queue version")
    item = next(
        (candidate for candidate in queue.items if candidate.item_id == intent.item_id),
        None,
    )
    if item is None or intent.expected_item_fingerprint != item.fingerprint:
        raise ActiveLearningConflictError("stale item version")
    if item.row_override_count:
        raise ActiveLearningConflictError("row overrides block shadow actions")
    if intent.action not in item.allowed_actions:
        raise ActiveLearningConflictError("shadow action is not allowed for this item")
    if intent.action is ShadowAction.SPLIT:
        flattened = tuple(member for group in intent.split_member_refs for member in group)
        if tuple(sorted(flattened)) != item.member_refs:
            raise ActiveLearningConflictError("split must preserve complete exact membership")
    intents = tuple(existing for existing in state.intents if existing.item_id != item.item_id)
    return ActiveLearningShadowAutosave(
        queue_id=state.queue_id,
        queue_fingerprint=state.queue_fingerprint,
        intents=(*intents, intent),
    )


__all__ = [
    "AUTOSAVE_VERSION",
    "INTENT_VERSION",
    "QUEUE_VERSION",
    "ActiveLearningConflictError",
    "ActiveLearningContractError",
    "ActiveLearningIntent",
    "ActiveLearningMode",
    "ActiveLearningPresentation",
    "ActiveLearningQueue",
    "ActiveLearningQueueItem",
    "ActiveLearningShadowAutosave",
    "PresentationCode",
    "QueueItemKind",
    "ShadowAction",
    "canonical_json_bytes",
    "sha256_fingerprint",
    "transition_shadow_intent",
]

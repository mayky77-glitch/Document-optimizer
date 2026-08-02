"""Bounded local-only semantic hints for reconciliation presentation."""

from __future__ import annotations

from dataclasses import dataclass

from report_processor.reconciliation_grouping import (
    FeatureVector,
    GroupingResult,
    LocalSemanticAssist,
)
from report_processor.reconciliation_grouping.semantic_model import StageEncoder
from report_processor.stage_rag.encoder import RUBERT_TINY2_MODEL_REVISION, RuBERTTiny2Encoder

SEMANTIC_ASSIST_CONTRACT_VERSION = "ReconciliationSemanticAssist-1.0"
CONTROLLED_SEMANTIC_HINT = "Найдены похожие формулировки для сравнения."
MAX_AMBIGUOUS_GROUPS = 8
LOCAL_ASSIST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class SemanticAssistSnapshot:
    """Private, controlled state; raw embeddings, scores and errors are discarded."""

    group_ids: tuple[str, ...] = ()
    hint: str | None = None

    def __post_init__(self) -> None:
        if tuple(sorted(set(self.group_ids))) != self.group_ids:
            raise ValueError("semantic assist group IDs must be unique and sorted")
        if self.hint not in {None, CONTROLLED_SEMANTIC_HINT}:
            raise ValueError("semantic assist hint must use a controlled Russian string")
        if bool(self.group_ids) != bool(self.hint):
            raise ValueError("semantic assist IDs and hint must be present together")


def run_local_semantic_assist(
    grouping: GroupingResult,
    *,
    encoder: StageEncoder | None = None,
    timeout_seconds: float = LOCAL_ASSIST_TIMEOUT_SECONDS,
) -> SemanticAssistSnapshot:
    """Run one bounded local batch without changing any grouping or decision fact."""
    features = _ambiguous_features(grouping)
    if not features:
        return SemanticAssistSnapshot()
    assist = LocalSemanticAssist(
        encoder or RuBERTTiny2Encoder(),
        model_revision=RUBERT_TINY2_MODEL_REVISION,
        timeout_seconds=timeout_seconds,
        batch_size=len(features),
    )
    result = assist.rank(features)
    if result.unavailable_reason is not None or not result.similarities:
        return SemanticAssistSnapshot()
    return SemanticAssistSnapshot(
        tuple(feature.group_id for feature in features), CONTROLLED_SEMANTIC_HINT
    )


def _ambiguous_features(grouping: GroupingResult) -> tuple[FeatureVector, ...]:
    exception_ids = {
        group_id for exception in grouping.exceptions for group_id in exception.group_ids
    }
    return tuple(
        feature
        for feature in sorted(grouping.features, key=lambda feature: feature.group_id)
        if feature.group_id in exception_ids or not feature.action or not feature.object_kind
    )[:MAX_AMBIGUOUS_GROUPS]

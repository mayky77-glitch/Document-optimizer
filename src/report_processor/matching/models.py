"""Immutable public contract for deterministic source-to-target matching."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

MATCHING_CONTRACT_VERSION = "MatchingContract-12.0"
MATCHING_ENGINE_VERSION = "MatchingEngine-12.0"


class MatchStatus(StrEnum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"


class MatchStrategy(StrEnum):
    EXACT_BUSINESS_KEY = "exact_business_key"
    INDEX_POSITION = "index_position"
    OBJECT_SUBOBJECT_POSITION = "object_subobject_position"
    NORMALIZED_NAME_UNIT = "normalized_name_unit"
    NORMALIZED_NAME_CONTEXT = "normalized_name_context"
    CONFIGURATION_RULE = "configuration_rule"
    FUZZY_REVIEW = "fuzzy_review"
    AUTHORITATIVE_REVIEW = "authoritative_review"


_STRATEGY_ORDER = {strategy: ordinal for ordinal, strategy in enumerate(MatchStrategy)}


@dataclass(frozen=True, slots=True)
class MatchingPolicy:
    """Fixed, data-only matching thresholds. Fuzzy candidates stay manual."""

    fuzzy_threshold: Decimal = Decimal("0.750000")

    def __post_init__(self) -> None:
        if not isinstance(self.fuzzy_threshold, Decimal):
            raise TypeError("fuzzy_threshold должен быть Decimal")
        if not self.fuzzy_threshold.is_finite() or not (
            Decimal("0") <= self.fuzzy_threshold <= Decimal("1")
        ):
            raise ValueError("fuzzy_threshold должен быть конечным Decimal от 0 до 1")
        object.__setattr__(
            self, "fuzzy_threshold", self.fuzzy_threshold.quantize(Decimal("0.000001"))
        )


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    candidate_id: str
    target_row_id: str
    source_row_id: str
    source_row: object
    strategies: tuple[MatchStrategy, ...]
    confidence: Decimal
    rule_ids: tuple[str, ...]
    explanation: tuple[str, ...]
    source_provenance: Mapping[str, str | int]
    target_provenance: Mapping[str, str | int]
    blockers: tuple[str, ...] = ()
    auto_selectable: bool = True

    def __post_init__(self) -> None:
        if not self.strategies:
            raise ValueError("candidate должен содержать хотя бы одну strategy")
        ordered = tuple(sorted(set(self.strategies), key=_STRATEGY_ORDER.__getitem__))
        if not isinstance(self.confidence, Decimal) or not self.confidence.is_finite():
            raise TypeError("confidence должен быть конечным Decimal")
        object.__setattr__(self, "strategies", ordered)
        object.__setattr__(self, "confidence", self.confidence.quantize(Decimal("0.000001")))
        object.__setattr__(self, "source_provenance", _freeze_provenance(self.source_provenance))
        object.__setattr__(self, "target_provenance", _freeze_provenance(self.target_provenance))
        object.__setattr__(self, "explanation", tuple(self.explanation))
        object.__setattr__(self, "rule_ids", tuple(sorted(set(self.rule_ids))))
        object.__setattr__(self, "blockers", tuple(sorted(set(self.blockers))))

    @property
    def strategy(self) -> MatchStrategy:
        return self.strategies[0]

    @property
    def strategy_ordinal(self) -> int:
        return _STRATEGY_ORDER[self.strategy]


@dataclass(frozen=True, slots=True)
class MatchResult:
    result_id: str
    target_row_id: str
    target_row: object
    status: MatchStatus
    selected_candidate: MatchCandidate | None
    candidates: tuple[MatchCandidate, ...]
    warnings: tuple[str, ...]
    explanation: tuple[str, ...]
    selected_candidates: tuple[MatchCandidate, ...] = ()
    contract_version: str = field(default=MATCHING_CONTRACT_VERSION, init=False)

    def __post_init__(self) -> None:
        ordered = tuple(
            sorted(self.candidates, key=lambda item: (item.strategy_ordinal, item.source_row_id))
        )
        selected = tuple(
            sorted(
                self.selected_candidates,
                key=lambda item: (item.strategy_ordinal, item.source_row_id, item.candidate_id),
            )
        )
        if len({item.candidate_id for item in selected}) != len(selected):
            raise ValueError("selected_candidates содержит повторяющийся candidate")
        selected_ids = {item.candidate_id for item in selected}
        if self.selected_candidate is not None:
            selected_ids.add(self.selected_candidate.candidate_id)
        candidate_ids = {item.candidate_id for item in ordered}
        if not selected_ids <= candidate_ids:
            raise ValueError("selected candidate отсутствует среди candidates")
        if self.status is not MatchStatus.MATCHED and selected_ids:
            raise ValueError("только MATCHED может иметь selected candidate")
        if self.selected_candidate is not None and selected:
            raise ValueError("multi-selection оставляет legacy selected_candidate пустым")
        object.__setattr__(self, "candidates", ordered)
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
        object.__setattr__(self, "explanation", tuple(self.explanation))
        object.__setattr__(self, "selected_candidates", selected)

    @property
    def effective_selected_candidates(self) -> tuple[MatchCandidate, ...]:
        """Return global selections while retaining the legacy singleton contract."""
        if self.selected_candidates:
            return self.selected_candidates
        return (self.selected_candidate,) if self.selected_candidate is not None else ()


def strategy_ordinal(strategy: MatchStrategy) -> int:
    return _STRATEGY_ORDER[strategy]


def _freeze_provenance(values: Mapping[str, str | int]) -> Mapping[str, str | int]:
    copied = dict(values)
    if any(
        not isinstance(key, str) or not isinstance(value, (str, int))
        for key, value in copied.items()
    ):
        raise TypeError("provenance должен содержать строки и целые числа")
    return MappingProxyType(dict(sorted(copied.items())))

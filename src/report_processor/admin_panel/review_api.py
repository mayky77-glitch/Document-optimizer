"""Request validation contracts for reconciliation review decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .service import MAX_MANUAL_DISCREPANCY_DECISIONS


class ReviewRequestError(ValueError):
    """Raised when a review decision request does not match its API contract."""


@dataclass(frozen=True)
class SuggestionDecisionRequest:
    """Validated individual or target-group suggestion decision."""

    suggestion_id: str | None
    decision: str
    group_id: str | None

    @property
    def is_group_decision(self) -> bool:
        """Return whether the request resolves a target suggestion group."""
        return self.group_id is not None


@dataclass(frozen=True)
class ManualDiscrepancyDecisionRequest:
    """Validated manual discrepancy-group decision."""

    group_id: str
    discrepancy_ids: list[str] | None
    decision: str


def parse_suggestion_decision(payload: object) -> SuggestionDecisionRequest:
    """Validate a legacy suggestion or journal-only target-group decision."""
    if not isinstance(payload, Mapping):
        raise ReviewRequestError("Ожидается JSON с решением")
    suggestion_id = payload.get("suggestion_id")
    decision = payload.get("decision")
    group_id = payload.get("group_id")
    if group_id is not None:
        if (
            not isinstance(group_id, str)
            or decision not in {"apply", "reject"}
            or (suggestion_id is not None and not isinstance(suggestion_id, str))
        ):
            raise ReviewRequestError("Недопустимое решение для открытой группы подсказок")
        return SuggestionDecisionRequest(suggestion_id, decision, group_id)
    if not isinstance(suggestion_id, str) or decision not in {"fit", "not_fit"}:
        raise ReviewRequestError("Допустимы только решения fit и not_fit")
    return SuggestionDecisionRequest(suggestion_id, decision, None)


def parse_manual_discrepancy_decision(
    payload: object,
) -> ManualDiscrepancyDecisionRequest:
    """Validate the journal-only manual discrepancy-group decision contract."""
    if not isinstance(payload, Mapping):
        raise ReviewRequestError("Ожидается JSON с решением")
    group_id = payload.get("group_id")
    discrepancy_ids = payload.get("discrepancy_ids")
    decision = payload.get("decision")
    if (
        not isinstance(group_id, str)
        or (discrepancy_ids is not None and not isinstance(discrepancy_ids, list))
        or (
            isinstance(discrepancy_ids, list)
            and len(discrepancy_ids) > MAX_MANUAL_DISCREPANCY_DECISIONS
        )
        or (
            isinstance(discrepancy_ids, list)
            and not all(isinstance(item, str) for item in discrepancy_ids)
        )
        or decision not in {"approve", "reject"}
    ):
        raise ReviewRequestError("Допустимы только решения approve и reject для открытой группы")
    return ManualDiscrepancyDecisionRequest(group_id, discrepancy_ids, decision)

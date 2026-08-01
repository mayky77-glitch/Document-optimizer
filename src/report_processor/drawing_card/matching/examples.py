"""Confirmed example dictionary and deterministic lexical retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..models import TargetWorkCategory
from ..sources.normalization import normalize_text, normalize_unit


@dataclass(frozen=True, slots=True)
class ConfirmedExample:
    example_id: str
    source_text: str
    normalized_text: str
    category: TargetWorkCategory | None
    quantity_decision: str
    cost_decision: str
    unit: str | None
    source_type: str | None
    confirmed_by: str | None
    rule_version: str | None


@dataclass(frozen=True, slots=True)
class RetrievedExample:
    example: ConfirmedExample
    score: float


def load_confirmed_examples(path: Path | None) -> tuple[ConfirmedExample, ...]:
    if path is None or not path.exists():
        return ()
    examples: list[ConfirmedExample] = []
    latest_feedback: dict[tuple[str, str], ConfirmedExample] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not payload.get("confirmed", False):
            continue
        category = payload.get("category")
        decision = str(payload.get("decision", "review"))
        quantity = str(payload.get("quantity_decision", "exclude"))
        cost = str(payload.get("cost_decision", "exclude"))
        if "quantity_decision" not in payload and decision == "include_quantity":
            quantity = "include"
        if "cost_decision" not in payload and decision == "include_cost":
            cost = "include"
        if decision == "exclude":
            quantity = cost = "exclude"
        try:
            example = ConfirmedExample(
                example_id=str(payload["example_id"]),
                source_text=str(payload["source_text"]),
                normalized_text=str(
                    payload.get("normalized_text") or normalize_text(payload["source_text"])
                ),
                category=TargetWorkCategory(category) if category else None,
                quantity_decision=quantity,
                cost_decision=cost,
                unit=normalize_unit(payload.get("unit")),
                source_type=payload.get("source_type"),
                confirmed_by=payload.get("confirmed_by"),
                rule_version=payload.get("rule_version"),
            )
        except (KeyError, TypeError, ValueError):
            continue
        if _is_review_feedback(example):
            # Older feedback files used an action-specific id, leaving stale
            # contradictions behind.  Preserve only the latest JSONL decision.
            latest_feedback[(example.normalized_text, example.unit or "")] = example
        else:
            examples.append(example)
    return tuple((*examples, *latest_feedback.values()))


def _is_review_feedback(example: ConfirmedExample) -> bool:
    return example.confirmed_by == "inline-review" and (example.rule_version or "").startswith(
        "ReviewFeedbackStore-"
    )


def _prefer_review_feedback(candidates: list[ConfirmedExample]) -> list[ConfirmedExample]:
    """A local explicit decision overrides a bundled example with the same row identity."""
    feedback = [item for item in candidates if _is_review_feedback(item)]
    return feedback or candidates


class LexicalExampleRetriever:
    def __init__(self, examples: tuple[ConfirmedExample, ...]) -> None:
        self.examples = examples

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in normalize_text(text).replace("/", " ").split() if len(token) > 1}

    def search(
        self,
        text: str,
        *,
        source_type: str | None,
        unit: str | None,
        top_k: int,
    ) -> tuple[RetrievedExample, ...]:
        query = self._tokens(text)
        unit = normalize_unit(unit)
        ranked: list[RetrievedExample] = []
        for example in self.examples:
            tokens = self._tokens(example.normalized_text)
            union = query | tokens
            score = len(query & tokens) / len(union) if union else 0.0
            if unit and example.unit == unit:
                score += 0.08
            if source_type and example.source_type == source_type:
                score += 0.04
            if score > 0:
                ranked.append(RetrievedExample(example, min(score, 1.0)))
        ranked.sort(key=lambda item: (-item.score, item.example.example_id))
        return tuple(ranked[:top_k])


def exact_example_match(
    text: str,
    examples: tuple[ConfirmedExample, ...],
    *,
    unit: str | None,
    source_type: str | None,
) -> ConfirmedExample | None:
    normalized = normalize_text(text)
    normalized_unit = normalize_unit(unit)
    candidates = [item for item in examples if item.normalized_text == normalized]
    # Feedback is exact and unit-scoped.  Generic legacy examples may still be
    # used for positive categories, but a negative decision must never cross units.
    exact_unit = [item for item in candidates if item.unit == normalized_unit]
    candidates = exact_unit or [
        item for item in candidates if item.unit is None and item.category is not None
    ]
    candidates = _prefer_review_feedback(candidates)
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (
            item.unit != normalized_unit if item.unit else True,
            item.source_type != source_type if item.source_type else True,
            item.example_id,
        )
    )
    decisions = {(item.category, item.quantity_decision, item.cost_decision) for item in candidates}
    # Contradictory exact feedback is deliberately not a first/last-write rule.
    return candidates[0] if len(decisions) == 1 else None


def has_exact_example_conflict(
    text: str,
    examples: tuple[ConfirmedExample, ...],
    *,
    unit: str | None,
) -> bool:
    normalized = normalize_text(text)
    normalized_unit = normalize_unit(unit)
    candidates = [
        item
        for item in examples
        if item.normalized_text == normalized and item.unit == normalized_unit
    ]
    candidates = _prefer_review_feedback(candidates)
    return (
        len({(item.category, item.quantity_decision, item.cost_decision) for item in candidates})
        > 1
    )

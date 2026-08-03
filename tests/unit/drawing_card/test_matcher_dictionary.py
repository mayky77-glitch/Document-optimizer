"""Matcher boundary contracts that must stay deterministic and review-safe."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import ConfirmedExample, RetrievedExample
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher
from report_processor.drawing_card.matching.semantic import DenseRetrievalContext
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    TargetWorkCategory,
)
from report_processor.drawing_card.statuses import Status

RULES = load_rules(
    Path(__file__).parents[3]
    / "src"
    / "report_processor"
    / "drawing_card"
    / "resources"
    / "rules.json"
)


def _row(name: str, *, unit: str = "м") -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id="boundary-row",
        location=DrawingSourceLocation("source", "source.xlsx", "Лист1", 2, ("A2",)),
        object_index_raw="1001",
        drawing_code_raw="А-1",
        work_name_raw=name,
        unit_raw=unit,
        remaining_quantity=Decimal("1"),
        remaining_total_cost=Decimal("1"),
        formula_values=(),
        cached_values=(),
        source_document_type="visr",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )


def test_short_tokens_are_not_fuzzy_matched() -> None:
    decision = DrawingRowMatcher(RULES, (), rag_mode="off").match(_row("Монтаж ЗР Д 57 мм"))

    assert decision.category is None
    assert decision.requires_manual_review is False


def test_rubert_suggestion_is_never_auto_applied() -> None:
    example = ConfirmedExample(
        example_id="semantic-1",
        source_text="Редкий кабельный этап",
        normalized_text="редкий кабельный этап",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="include",
        cost_decision="include",
        unit="м",
        source_type="visr",
        confirmed_by="review",
        rule_version="1.0",
    )
    matcher = DrawingRowMatcher(RULES, (example,), rag_mode="semantic")
    matcher.semantic_retriever = _SemanticSuggestion(example)

    decision = matcher.match(_row("Редкий монолитный этап"))

    assert decision.category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert decision.quantity_decision == "review"
    assert decision.cost_decision == "review"
    assert decision.requires_manual_review is True
    assert "SEMANTIC_SUGGESTION_NOT_APPLIED" in decision.warnings


def test_dense_retriever_requires_explicit_context() -> None:
    with pytest.raises(ValueError, match="supplied together"):
        DrawingRowMatcher(RULES, (), rag_mode="semantic", dense_retriever=object())

    with pytest.raises(ValueError, match="tenant"):
        DenseRetrievalContext("", "project", "visr", "taxonomy-1")


class _SemanticSuggestion:
    def __init__(self, example: ConfirmedExample) -> None:
        self.example = example

    def search(self, text: str, *, top_k: int) -> tuple[RetrievedExample, ...]:
        assert text == "редкий монолитный этап"
        assert top_k == RULES.top_k_examples
        return (RetrievedExample(self.example, 0.91),)

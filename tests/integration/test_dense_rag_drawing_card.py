"""Dense RAG drawing-card boundary: tenant safe and review-only."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import ConfirmedExample
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher
from report_processor.drawing_card.matching.semantic import DenseRetrievalContext
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    TargetWorkCategory,
)
from report_processor.drawing_card.statuses import Status
from report_processor.stage_rag.models import (
    ConfirmedExampleVector,
    DenseRetrievalCandidate,
    DenseRetrievalQuery,
    DenseRetrievalResult,
)
from report_processor.stage_rag.qdrant_store import InMemoryVectorStore
from report_processor.stage_rag.retrieval import StoreBackedDenseRetriever

RULES = load_rules(
    Path(__file__).parents[2]
    / "src"
    / "report_processor"
    / "drawing_card"
    / "resources"
    / "rules.json"
)
CONTEXT = DenseRetrievalContext("tenant-a", "project-7", "visr", "taxonomy-1")


def _row(name: str) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id="dense-row",
        location=DrawingSourceLocation("source", "source.xlsx", "Лист1", 2, ("A2",)),
        object_index_raw="1001",
        drawing_code_raw="А-1",
        work_name_raw=name,
        unit_raw="м",
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


class _TenantFilteredRetriever:
    def __init__(
        self, candidates_by_tenant: dict[str, tuple[DenseRetrievalCandidate, ...]]
    ) -> None:
        self.candidates_by_tenant = candidates_by_tenant
        self.calls: list[tuple[str, str, int, str | None, str | None, str | None]] = []

    def retrieve(
        self,
        tenant_id: str,
        text: str,
        *,
        limit: int = 5,
        project_id: str | None = None,
        document_type: str | None = None,
        taxonomy_version: str | None = None,
    ) -> DenseRetrievalResult:
        self.calls.append((tenant_id, text, limit, project_id, document_type, taxonomy_version))
        query = DenseRetrievalQuery(
            tenant_id=tenant_id,
            vector=(1.0,),
            embedding_model_id="test-model",
            embedding_model_revision="test-revision",
            embedding_dimensions=1,
            limit=limit,
            project_id=project_id,
            document_type=document_type,
            taxonomy_version=taxonomy_version,
        )
        return DenseRetrievalResult(
            query=query,
            candidates=self.candidates_by_tenant.get(tenant_id, ())[:limit],
        )


def _matcher(retriever: _TenantFilteredRetriever, examples: tuple[ConfirmedExample, ...] = ()):
    return DrawingRowMatcher(
        RULES,
        examples,
        rag_mode="semantic",
        dense_retriever=retriever,
        dense_context=CONTEXT,
    )


def test_dense_rag_uses_all_explicit_filters_and_never_exposes_cross_tenant_evidence() -> None:
    class _Embedding:
        model_id = "test-model"
        revision = "test-revision"
        dimensions = 2

        def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
            return tuple((1.0, 0.0) for _ in texts)

    store = InMemoryVectorStore()
    store.upsert(
        (
            _dense_example("tenant-a-example", "tenant-a", "power_cable"),
            _dense_example("tenant-b-example", "tenant-b", "concrete_works"),
        )
    )
    retriever = StoreBackedDenseRetriever(_Embedding(), store)

    decision = _matcher(retriever).match(_row("Редкий монолитный этап"))

    assert decision.evidence_ids == ("tenant-a-example",)
    assert "tenant-b-example" not in decision.evidence_ids
    assert decision.quantity_confidence == 1.0


def _dense_example(example_id: str, tenant_id: str, category: str) -> ConfirmedExampleVector:
    return ConfirmedExampleVector(
        example_id=example_id,
        tenant_id=tenant_id,
        vector=(1.0, 0.0),
        normalized_text_hash="a" * 64,
        embedding_model_id="test-model",
        embedding_model_revision="test-revision",
        taxonomy_version="taxonomy-1",
        review_decision="confirmed",
        category=category,
        project_id="project-7",
        document_type="visr",
    )


def test_exact_feedback_precedes_dense_retrieval() -> None:
    example = ConfirmedExample(
        example_id="exact-feedback",
        source_text="Редкий монтаж кабеля",
        normalized_text="редкий монтаж кабеля",
        category=TargetWorkCategory.LOW_CURRENT_CABLE,
        quantity_decision="include",
        cost_decision="include",
        unit="м",
        source_type="visr",
        confirmed_by="inline-review",
        rule_version="ReviewFeedbackStore-1.0",
    )
    retriever = _TenantFilteredRetriever(
        {"tenant-a": (DenseRetrievalCandidate("dense", 0.99, "concrete_works"),)}
    )

    decision = _matcher(retriever, (example,)).match(_row("Редкий монтаж кабеля"))

    assert retriever.calls == []
    assert decision.matching_strategy == "confirmed_dictionary"
    assert decision.category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert decision.requires_manual_review is False


def test_dense_score_never_auto_applies_a_category() -> None:
    candidates = tuple(
        DenseRetrievalCandidate(f"high-score-{index}", 1.0 - index / 10, "concrete_works")
        for index in range(6)
    )
    retriever = _TenantFilteredRetriever({"tenant-a": candidates})

    decision = _matcher(retriever).match(_row("Редкий монолитный этап"))

    assert decision.category is TargetWorkCategory.CONCRETE_WORKS
    assert decision.quantity_decision == "review"
    assert decision.cost_decision == "review"
    assert decision.requires_manual_review is True
    assert decision.evidence_ids == tuple(f"high-score-{index}" for index in range(5))
    assert "candidate_scores=1.000,0.900,0.800,0.700,0.600" in decision.reason
    assert "DENSE_SUGGESTION_NOT_APPLIED" in decision.warnings


def test_dense_timeout_returns_generic_manual_review_without_backend_detail() -> None:
    class _TimeoutRetriever:
        def retrieve(self, *_args, **_kwargs):
            raise TimeoutError("qdrant.internal.example:6333")

    decision = DrawingRowMatcher(
        RULES,
        (),
        rag_mode="semantic",
        dense_retriever=_TimeoutRetriever(),
        dense_context=CONTEXT,
    ).match(_row("Редкий монолитный этап"))

    assert decision.requires_manual_review is True
    assert decision.evidence_ids == ()
    assert "DENSE_RETRIEVAL_UNAVAILABLE" in decision.warnings
    assert "qdrant.internal.example" not in decision.reason

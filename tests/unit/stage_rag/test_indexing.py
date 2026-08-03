"""Lifecycle tests for explicitly confirmed Dense RAG examples."""

from __future__ import annotations

import pytest

from fixtures.stage_rag.qdrant_fakes import RecordingVectorStore
from report_processor.stage_rag.errors import StageRAGInputError
from report_processor.stage_rag.indexing import (
    ConfirmedExampleIndexer,
    ConfirmedReviewOutcome,
    normalized_text_hash,
    plan_reindex,
    stable_example_id,
)


class Provider:
    model_id = "local-model"
    revision = "revision-a"
    dimensions = 2

    def encode(self, texts):
        return tuple((1.0, 0.0) for _ in texts)


def _outcome(**changes: object) -> ConfirmedReviewOutcome:
    fields: dict[str, object] = {
        "tenant_id": "tenant-a",
        "text": "  Pump   Station ",
        "category": "pump",
        "taxonomy_version": "taxonomy-1",
        "rule_version": "rule-1",
        "audit_reference": "review-123",
        "confirmed": True,
    }
    fields.update(changes)
    return ConfirmedReviewOutcome(**fields)  # type: ignore[arg-type]


def test_confirmed_outcome_is_idempotent_and_binds_required_metadata() -> None:
    store = RecordingVectorStore()
    indexer = ConfirmedExampleIndexer(store, Provider())

    first = indexer.index(_outcome())
    second = indexer.index(_outcome(text="pump station"))

    assert first.example_id == second.example_id == stable_example_id("tenant-a", "review-123")
    assert first.normalized_text_hash == normalized_text_hash("pump station")
    assert first.payload() == {
        "example_id": first.example_id,
        "tenant_id": "tenant-a",
        "normalized_text_hash": first.normalized_text_hash,
        "embedding_model_id": "local-model",
        "embedding_model_revision": "revision-a",
        "embedding_dimensions": 2,
        "taxonomy_version": "taxonomy-1",
        "review_decision": "confirmed",
        "active": True,
        "category": "pump",
        "rule_version": "rule-1",
        "audit_reference": "review-123",
    }
    assert len(store.upserts) == 2


def test_only_explicit_confirmations_are_indexed_and_replacements_are_deactivated() -> None:
    store = RecordingVectorStore()
    indexer = ConfirmedExampleIndexer(store, Provider())

    with pytest.raises(StageRAGInputError, match="UNCONFIRMED_OUTCOME"):
        indexer.index(_outcome(confirmed=False))
    indexer.index(_outcome(replaces_example_id="old", cancelled_example_ids=("cancelled", "old")))
    indexer.cancel("tenant-a", ("later-cancelled",))

    assert store.upserts == [store.upserts[0]]
    assert store.deactivations == [
        ("tenant-a", ("cancelled", "old")),
        ("tenant-a", ("later-cancelled",)),
    ]


def test_stable_ids_are_tenant_aware_and_reindex_plan_has_no_side_effect() -> None:
    assert stable_example_id("tenant-a", "review-123") != stable_example_id(
        "tenant-b", "review-123"
    )

    plan = plan_reindex(
        "confirmed_examples_v1",
        collection_version=2,
        embedding_model_id="local-model",
        embedding_model_revision="revision-b",
        taxonomy_version="taxonomy-2",
    )

    assert plan.target_collection == "confirmed_examples_v2"
    assert plan.rollback_collection == "confirmed_examples_v1"
    assert plan.alias_name == "confirmed_examples_current"


def test_same_normalized_text_with_distinct_review_evidence_has_distinct_public_ids() -> None:
    store = RecordingVectorStore()
    indexer = ConfirmedExampleIndexer(store, Provider())

    first = indexer.index(_outcome(audit_reference="review-123", project_id="project-a"))
    second = indexer.index(_outcome(audit_reference="review-456", project_id="project-b"))

    assert first.normalized_text_hash == second.normalized_text_hash
    assert first.example_id != second.example_id


@pytest.mark.parametrize("ids", ["example", b"example", ("",), (1,), None])
def test_cancel_rejects_invalid_lifecycle_ids(ids: object) -> None:
    with pytest.raises(StageRAGInputError, match="INVALID_EXAMPLE_IDS"):
        ConfirmedExampleIndexer(RecordingVectorStore(), Provider()).cancel("tenant-a", ids)  # type: ignore[arg-type]


@pytest.mark.parametrize("version", [True, 0, "2", None])
def test_plan_reindex_rejects_non_integer_versions(version: object) -> None:
    with pytest.raises(StageRAGInputError, match="INVALID_COLLECTION_VERSION"):
        plan_reindex(
            "confirmed_examples_v1",
            collection_version=version,  # type: ignore[arg-type]
            embedding_model_id="local-model",
            embedding_model_revision="revision-b",
            taxonomy_version="taxonomy-2",
        )


@pytest.mark.parametrize("vector", [((float("nan"), 0.0),), ((1.0,),), (("bad", 0.0),)])
def test_provider_vector_failures_are_controlled(vector: tuple[tuple[object, ...], ...]) -> None:
    class BadProvider(Provider):
        def encode(self, texts):
            return vector

    with pytest.raises(
        StageRAGInputError, match=r"(NONFINITE_VECTOR|INVALID_VECTOR|INVALID_VECTOR_DIMENSION)"
    ):
        ConfirmedExampleIndexer(RecordingVectorStore(), BadProvider()).index(_outcome())

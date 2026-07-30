"""Opt-in smoke test for the pinned, locally cached RuBERT model."""

from __future__ import annotations

import os

import pytest
from report_processor.stage_rag import (
    EMBEDDING_DIMENSIONS,
    RUBERT_TINY2_MODEL_ID,
    RUBERT_TINY2_MODEL_REVISION,
    RuBERTTiny2Encoder,
    StageRAGModelUnavailableError,
)

from report_processor.matching import MatchStatus
from report_processor.processing import DefaultProcessingAdapters, ProcessReportRequest


@pytest.mark.skipif(os.getenv("RUN_RAG_MODEL") != "1", reason="set RUN_RAG_MODEL=1")
def test_pinned_local_rubert_model_encodes_without_remote_access() -> None:
    assert RUBERT_TINY2_MODEL_ID == "cointegrated/rubert-tiny2"
    assert RUBERT_TINY2_MODEL_REVISION == "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae"
    try:
        vectors = RuBERTTiny2Encoder().encode(("Монтаж трубопровода",))
    except StageRAGModelUnavailableError as exc:
        pytest.skip(f"pinned local RuBERT model unavailable: {exc.code}")
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSIONS


def test_unavailable_injected_encoder_returns_controlled_manual_review_warning(tmp_path) -> None:
    class UnavailableEncoder:
        def encode(self, texts):
            raise StageRAGModelUnavailableError("offline model cache")

    request = ProcessReportRequest(
        tmp_path / "source.xlsx",
        tmp_path / "target.xlsx",
        options={"stage_rag": True},
    )
    source_rows = (type("Source", (), {"source_row_id": "source", "work_name": "source"})(),)
    matches = (
        type(
            "Match",
            (),
            {
                "result_id": "target",
                "status": MatchStatus.UNMATCHED,
                "target_row": type("Target", (), {"stage": "target", "work_name": "target"})(),
            },
        )(),
    )

    adapters = DefaultProcessingAdapters(UnavailableEncoder())
    artifacts, warnings = adapters._stage_relation_suggestions(request, source_rows, matches)

    assert artifacts == {
        "stage_rag_status": "RAG_MODEL_UNAVAILABLE",
        "stage_rag_requires_manual_review": True,
    }
    assert warnings == ("RAG_MODEL_UNAVAILABLE",)

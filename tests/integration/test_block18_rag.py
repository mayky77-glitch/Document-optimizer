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

pytestmark = pytest.mark.skipif(os.getenv("RUN_RAG_MODEL") != "1", reason="set RUN_RAG_MODEL=1")


def test_pinned_local_rubert_model_encodes_without_remote_access() -> None:
    assert RUBERT_TINY2_MODEL_ID == "cointegrated/rubert-tiny2"
    assert RUBERT_TINY2_MODEL_REVISION == "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae"
    try:
        vectors = RuBERTTiny2Encoder().encode(("Монтаж трубопровода",))
    except StageRAGModelUnavailableError as exc:
        pytest.skip(f"pinned local RuBERT model unavailable: {exc.code}")
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBEDDING_DIMENSIONS

"""Frozen public release contract for StageRelationRAG-18.0."""

from __future__ import annotations

import builtins
import subprocess
import sys

import pytest

from report_processor.stage_rag import (
    EMBEDDING_DIMENSIONS,
    RUBERT_TINY2_MODEL_ID,
    RUBERT_TINY2_MODEL_REVISION,
    STAGE_RELATION_RAG_CONTRACT_VERSION,
    RuBERTTiny2Encoder,
    StageRAGModelUnavailableError,
    StageRelationCandidate,
    StageRelationSuggestion,
)


def test_public_contract_constants_and_manual_review_values_are_frozen() -> None:
    assert STAGE_RELATION_RAG_CONTRACT_VERSION == "StageRelationRAG-18.0"
    assert RUBERT_TINY2_MODEL_ID == "cointegrated/rubert-tiny2"
    assert RUBERT_TINY2_MODEL_REVISION == "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae"
    assert EMBEDDING_DIMENSIONS == 312
    suggestion = StageRelationSuggestion("target", (StageRelationCandidate("source", 0.9),))
    assert suggestion.requires_manual_review is True
    assert suggestion.auto_accepted is False


def test_rubert_adapter_is_lazy_and_missing_dependencies_are_controlled(monkeypatch) -> None:
    encoder = RuBERTTiny2Encoder()
    assert encoder.encode(()) == ()

    original_import = builtins.__import__

    def missing_rag_dependency(name, *args, **kwargs):
        if name in {"torch", "transformers"}:
            raise ImportError("test missing optional dependency")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_rag_dependency)
    with pytest.raises(StageRAGModelUnavailableError) as caught:
        encoder.encode(("монтаж труб",))
    assert caught.value.code == "RAG_MODEL_UNAVAILABLE"


def test_base_package_import_needs_no_rag_extras() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import report_processor; print(report_processor.__version__)"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

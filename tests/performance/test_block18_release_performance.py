"""Slow-only deterministic retrieval release threshold."""

from __future__ import annotations

import os
import time

import pytest

from report_processor.stage_rag import StageRelationRAG, StageText

pytestmark = pytest.mark.skipif(os.getenv("RUN_SLOW") != "1", reason="set RUN_SLOW=1")


class IndexedEncoder:
    def encode(self, texts):
        return tuple((1.0, float(int(text.rsplit("-", 1)[1]) % 11 + 1)) for text in texts)


def test_deterministic_top_k_for_250_by_750_synthetic_stages() -> None:
    sources = tuple(StageText(f"source-{item:04d}", f"source-{item:04d}") for item in range(750))
    targets = tuple(StageText(f"target-{item:04d}", f"target-{item:04d}") for item in range(250))
    rag = StageRelationRAG(IndexedEncoder(), embedding_dimensions=2)

    started = time.perf_counter()
    first = rag.suggest(sources, targets, k=3)
    elapsed = time.perf_counter() - started
    second = rag.suggest(tuple(reversed(sources)), tuple(reversed(targets)), k=3)

    assert first == second
    assert len(first) == 250 and all(len(item.candidates) == 3 for item in first)
    assert elapsed <= 5.0

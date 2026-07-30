"""Versioned, sanitized golden data for deterministic StageRelationRAG output."""

from __future__ import annotations

import json
from pathlib import Path

from fixtures.stage_rag.builders import FakeEncoder
from report_processor.stage_rag import StageRelationRAG, StageText


def test_sanitized_versioned_golden_ranking_is_stable() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "stage_rag" / "golden_stage_relations.json"
    golden = json.loads(path.read_text(encoding="utf-8"))
    assert golden["version"] == "StageRelationRAGGolden-18.0"
    assert "xlsx" not in json.dumps(golden).casefold()

    encoder = FakeEncoder(golden["vectors"])
    sources = tuple(StageText(**item) for item in reversed(golden["sources"]))
    targets = tuple(StageText(**item) for item in reversed(golden["targets"]))
    rag = StageRelationRAG(encoder, embedding_dimensions=golden["embedding_dimensions"])
    suggestions = rag.suggest(sources, targets, k=3)

    assert {
        item.target_identity: [candidate.source_identity for candidate in item.candidates]
        for item in suggestions
    } == golden["expected"]

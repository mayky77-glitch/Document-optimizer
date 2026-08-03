"""Deterministic offline metrics for a sanitized Dense RAG evaluation fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DenseRAGEvaluation:
    """Metrics only; no threshold or embedding-model suitability claim is implied."""

    query_count: int
    recall_at_5: float
    mrr: float
    top1_error_rate: float
    review_rate: float
    mean_latency_ms: float


def evaluate_fixture(path: Path) -> DenseRAGEvaluation:
    """Load a sanitized, deterministic fixture and calculate retrieval metrics."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("evaluation fixture должен содержать cases")
    return evaluate_cases(payload["cases"])


def evaluate_cases(cases: list[object]) -> DenseRAGEvaluation:
    """Calculate Recall@5, MRR, top-1 error, review rate and mean latency."""
    if not cases:
        raise ValueError("evaluation cases не должны быть пустыми")
    recall = reciprocal_rank = top1_errors = reviews = 0
    total_latency = 0.0
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("evaluation case должен быть object")
        expected = case.get("expected_example_id")
        candidates = case.get("candidate_example_ids")
        latency = case.get("latency_ms")
        review = case.get("requires_manual_review")
        if (
            not isinstance(expected, str)
            or not isinstance(candidates, list)
            or any(not isinstance(item, str) for item in candidates)
            or not isinstance(latency, (int, float))
            or isinstance(latency, bool)
            or latency < 0
            or not isinstance(review, bool)
        ):
            raise ValueError("evaluation case имеет недопустимые поля")
        top_five = candidates[:5]
        if expected in top_five:
            recall += 1
            reciprocal_rank += 1 / (top_five.index(expected) + 1)
        if not candidates or candidates[0] != expected:
            top1_errors += 1
        reviews += review
        total_latency += float(latency)
    count = len(cases)
    return DenseRAGEvaluation(
        query_count=count,
        recall_at_5=recall / count,
        mrr=reciprocal_rank / count,
        top1_error_rate=top1_errors / count,
        review_rate=reviews / count,
        mean_latency_ms=total_latency / count,
    )

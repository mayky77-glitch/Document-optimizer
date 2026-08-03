"""Deterministic metric checks over a sanitized Dense RAG fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.stage_rag.evaluation import evaluate_cases, evaluate_fixture


def test_sanitized_fixture_reports_all_metrics_without_threshold_claims() -> None:
    result = evaluate_fixture(Path("tests/fixtures/stage_rag/dense_rag_evaluation.json"))

    assert result.query_count == 3
    assert result.recall_at_5 == pytest.approx(2 / 3)
    assert result.mrr == pytest.approx((1 + 1 / 2) / 3)
    assert result.top1_error_rate == pytest.approx(2 / 3)
    assert result.review_rate == 1.0
    assert result.mean_latency_ms == 5.0


def test_invalid_cases_are_rejected_deterministically() -> None:
    with pytest.raises(ValueError, match="не должны быть пустыми"):
        evaluate_cases([])
    with pytest.raises(ValueError, match="недопустимые поля"):
        evaluate_cases(
            [
                {
                    "expected_example_id": "id",
                    "candidate_example_ids": [],
                    "requires_manual_review": True,
                    "latency_ms": -1,
                }
            ]
        )

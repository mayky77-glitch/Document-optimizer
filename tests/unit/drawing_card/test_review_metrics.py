"""Contract tests for explicit review packet metrics."""

from __future__ import annotations

import pytest

from report_processor.drawing_card.audit.review_metrics import ReviewMetrics


def test_review_metrics_increment_explicit_counters_and_serialize_safe_rates() -> None:
    metrics = ReviewMetrics()
    metrics.record_review_candidate(4)
    metrics.record_queued_review_row(3)
    metrics.record_packet(singleton=True)
    metrics.record_packet()
    metrics.record_opened_card()
    metrics.record_feedback_hit()
    metrics.record_packet_exclusion()
    metrics.record_override()
    metrics.record_review_apply()
    metrics.record_post_review_error()

    assert metrics.to_dict() == {
        "review_candidates": 4,
        "queued_review_rows": 3,
        "packets": 2,
        "singleton_packets": 1,
        "opened_cards": 1,
        "feedback_hits": 1,
        "packet_exclusions": 1,
        "overrides": 1,
        "review_applies": 1,
        "post_review_errors": 1,
        "singleton_share": 0.5,
        "feedback_hit_rate": 0.25,
        "post_review_error_rate": 1.0,
    }


def test_review_metrics_zero_denominators_and_invalid_increments_are_safe() -> None:
    assert ReviewMetrics().to_dict()["singleton_share"] == 0.0
    assert ReviewMetrics().to_dict()["feedback_hit_rate"] == 0.0
    assert ReviewMetrics().to_dict()["post_review_error_rate"] == 0.0

    with pytest.raises(ValueError, match="Unknown review metric"):
        ReviewMetrics().increment("not_a_metric")
    with pytest.raises(ValueError, match="non-negative integers"):
        ReviewMetrics().increment("packets", -1)

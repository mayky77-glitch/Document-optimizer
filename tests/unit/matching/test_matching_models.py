"""Unit invariants that keep matching data-only and deterministic."""

from decimal import Decimal

from report_processor.matching import MatchCandidate, MatchStrategy


def test_candidate_orders_triggered_strategies_and_quantizes_confidence() -> None:
    candidate = MatchCandidate(
        candidate_id="c",
        target_row_id="t",
        source_row_id="s",
        strategies=(MatchStrategy.NORMALIZED_NAME_UNIT, MatchStrategy.EXACT_BUSINESS_KEY),
        strategy=MatchStrategy.EXACT_BUSINESS_KEY,
        confidence=Decimal("1"),
        source_provenance={"source_row": 1},
        target_provenance={"row_number": 2},
        explanation=("synthetic",),
    )
    assert candidate.strategies == (
        MatchStrategy.EXACT_BUSINESS_KEY,
        MatchStrategy.NORMALIZED_NAME_UNIT,
    )
    assert candidate.confidence == Decimal("1.000000")

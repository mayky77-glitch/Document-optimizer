"""Frozen public API contract for MatchingEngine-12.0."""

from decimal import Decimal

import pytest
from report_processor.matching import (
    MATCHING_CONTRACT_VERSION,
    MATCHING_ENGINE_VERSION,
    MatchCandidate,
    MatchingInputError,
    MatchingPolicy,
    MatchResult,
    MatchStatus,
    MatchStrategy,
    match_rows,
)


def test_public_versions_strategies_and_fixed_decimal_policy() -> None:
    assert MATCHING_CONTRACT_VERSION == "MatchingContract-12.0"
    assert MATCHING_ENGINE_VERSION == "MatchingEngine-12.0"
    assert tuple(MatchStrategy) == (
        MatchStrategy.EXACT_BUSINESS_KEY,
        MatchStrategy.INDEX_POSITION,
        MatchStrategy.OBJECT_SUBOBJECT_POSITION,
        MatchStrategy.NORMALIZED_NAME_UNIT,
        MatchStrategy.NORMALIZED_NAME_CONTEXT,
        MatchStrategy.CONFIGURATION_RULE,
        MatchStrategy.FUZZY_REVIEW,
    )
    assert MatchingPolicy().fuzzy_threshold == Decimal("0.750000")
    with pytest.raises(TypeError):
        MatchingPolicy(fuzzy_threshold=0.75)  # type: ignore[arg-type]
    assert callable(match_rows)
    assert issubclass(MatchingInputError, ValueError)


def test_result_rejects_nonselected_ambiguous_candidate() -> None:
    candidate = MatchCandidate(
        candidate_id="candidate",
        target_row_id="target",
        source_row_id="source",
        strategies=(MatchStrategy.EXACT_BUSINESS_KEY,),
        strategy=MatchStrategy.EXACT_BUSINESS_KEY,
        confidence=Decimal("1"),
        source_provenance={"source_row": 1},
        target_provenance={"row_number": 2},
        explanation=("exact",),
    )
    with pytest.raises(ValueError):
        MatchResult(
            result_id="result",
            target_row_id="target",
            target_source_id="target-file",
            target_fingerprint="sha256:abc",
            sheet_name="Table 2",
            row_number=2,
            status=MatchStatus.AMBIGUOUS,
            selected_candidate_id=candidate.candidate_id,
            candidates=(candidate,),
            explanation=("tie",),
            target_provenance={"row_number": 2},
        )

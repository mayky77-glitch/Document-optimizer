"""Integration evidence for deterministic Block 12 matching."""

import hashlib
import json
from decimal import Decimal

import pytest
from report_processor.matching import MatchingInputError, MatchStatus, MatchStrategy, match_rows

from fixtures.matching.builders import rule_set, source_row, target_row
from report_processor.business_rules.models import RuleAction


def _digest(results: tuple[object, ...]) -> str:
    payload = [
        {
            "result_id": item.result_id,
            "status": item.status.value,
            "selected": item.selected_candidate.candidate_id if item.selected_candidate else None,
            "candidates": [
                {
                    "id": candidate.candidate_id,
                    "strategies": [strategy.value for strategy in candidate.strategies],
                    "confidence": format(candidate.confidence, "f"),
                    "rules": candidate.rule_ids,
                    "blockers": candidate.blockers,
                    "source": dict(candidate.source_provenance),
                    "target": dict(candidate.target_provenance),
                }
                for candidate in item.candidates
            ],
        }
        for item in results
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _match(source_rows: tuple[object, ...], target, rules):
    return match_rows(
        source_rows,
        (target,),
        rules,
        target_source_id="target-a",
        target_fingerprint="sha256:abc",
    )


def test_unique_exact_match_retains_all_signals_provenance_and_is_deterministic() -> None:
    source = source_row()
    target = target_row()
    rules = rule_set()
    first = _match((source,), target, rules)
    second = _match((source,), target, rules)
    assert len(first) == 1 and first[0].status is MatchStatus.MATCHED
    candidate = first[0].candidates[0]
    assert candidate.strategy is MatchStrategy.EXACT_BUSINESS_KEY
    assert candidate.confidence == Decimal("1.000000")
    assert candidate.source_provenance["source_row_id"] == source.source_row_id
    assert candidate.target_provenance["row_number"] == target.row_number
    assert first[0].selected_candidate is candidate
    assert _digest(first) == _digest(second)


def test_tie_rule_review_exclude_fuzzy_and_duplicate_identities_are_controlled() -> None:
    target = target_row()
    tie = _match((source_row("a"), source_row("b")), target, rule_set())
    assert tie[0].status is MatchStatus.AMBIGUOUS and tie[0].selected_candidate is None
    review = _match((source_row(),), target, rule_set(action=RuleAction.REVIEW))
    assert review[0].selected_candidate is None
    excluded = _match((source_row(),), target, rule_set(action=RuleAction.EXCLUDE))
    assert excluded[0].selected_candidate is None
    fuzzy = _match((source_row(work_name="pipe install"),), target, rule_set(literal="unrelated"))
    manual = [
        candidate.manual_only
        for candidate in fuzzy[0].candidates
        if candidate.strategy is MatchStrategy.FUZZY_REVIEW
    ]
    assert all(manual)
    with pytest.raises(MatchingInputError):
        _match((source_row(), source_row()), target, rule_set())

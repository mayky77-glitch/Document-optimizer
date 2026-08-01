from decimal import Decimal

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.calculation import calculate_matches
from report_processor.quality_control import WriteDecision, evaluate_quality_control


def test_authoritative_calculation_is_quality_checked_once_before_any_write() -> None:
    source = calculation_source_row("source-a:1", quantity=Decimal("2"), cost=Decimal("10"))
    match = match_result(source, candidate_id="authoritative-candidate")
    rules = calculation_rule_set()
    calculations = calculate_matches((match,), rules)

    report = evaluate_quality_control((match,), calculations, rules)

    assert report.decision is WriteDecision.REQUIRE_MANUAL_REVIEW

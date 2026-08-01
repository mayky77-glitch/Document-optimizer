from decimal import Decimal

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.calculation import calculate_matches


def test_cost_only_authoritative_selection_keeps_target_quantity_out_of_calculation() -> None:
    source = calculation_source_row("source-a:1", quantity=Decimal("4"), cost=Decimal("12"))
    match = match_result(source, candidate_id="authoritative-candidate")

    (result,) = calculate_matches(
        (match,),
        calculation_rule_set(),
        {"authoritative-candidate": (False, True)},
    )

    assert result.quantity is None
    assert result.cost == Decimal("12.00")

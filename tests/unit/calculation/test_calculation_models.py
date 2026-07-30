"""Unit evidence for immutable Block 13 calculation value objects."""

from dataclasses import fields
from decimal import Decimal

import pytest
from report_processor.calculation import (
    CalculationCategory,
    CalculationCategoryTotal,
    CalculationContribution,
    CalculationResult,
    CalculationStatus,
    CalculationTrace,
)


def test_calculation_models_are_frozen_and_expose_the_frozen_fields() -> None:
    assert tuple(item.name for item in fields(CalculationContribution)) == (
        "contribution_id",
        "candidate_id",
        "source_row_id",
        "source_row",
        "category",
        "raw_quantity",
        "raw_cost",
        "included_quantity",
        "included_cost",
        "include_quantity",
        "include_cost",
        "rule_ids",
        "decisions",
        "warnings",
        "source_provenance",
        "target_provenance",
    )
    assert tuple(item.name for item in fields(CalculationCategoryTotal)) == (
        "category",
        "quantity",
        "cost_before_coefficient",
        "coefficient",
        "cost",
    )
    assert tuple(item.name for item in fields(CalculationTrace)) == (
        "trace_id",
        "match_result_id",
        "target_row_id",
        "rule_set_hash",
        "formula_tokens",
        "coefficient",
        "rounding_quantum",
        "rounding_mode",
        "contributions",
        "category_totals",
        "warnings",
    )
    assert tuple(item.name for item in fields(CalculationResult)) == (
        "calculation_id",
        "target_row_id",
        "match_result_id",
        "target_row",
        "status",
        "quantity",
        "cost_before_coefficient",
        "coefficient",
        "cost",
        "category_totals",
        "trace",
        "warnings",
        "explanation",
        "contract_version",
    )


def test_wire_enums_and_category_totals_retain_decimal_values() -> None:
    assert tuple(CalculationStatus) == (
        CalculationStatus.CALCULATED,
        CalculationStatus.CALCULATED_WITH_WARNINGS,
        CalculationStatus.NO_VALUES,
        CalculationStatus.MANUAL_REVIEW,
        CalculationStatus.NO_MATCH,
    )
    assert tuple(CalculationCategory) == (
        CalculationCategory.WORK,
        CalculationCategory.MATERIAL,
        CalculationCategory.SERVICE,
        CalculationCategory.UNCLASSIFIED,
    )
    total = CalculationCategoryTotal(
        category=CalculationCategory.WORK,
        quantity=Decimal("1.00"),
        cost_before_coefficient=Decimal("2.00"),
        coefficient=Decimal("1.1"),
        cost=Decimal("2.20"),
    )
    assert total.cost == Decimal("2.20")
    with pytest.raises((AttributeError, TypeError)):
        total.cost = Decimal("3")  # type: ignore[misc]

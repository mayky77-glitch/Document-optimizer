"""Frozen public API contract for CalculationEngine-13.0."""

from dataclasses import fields
from decimal import Decimal

import pytest

from report_processor.calculation import (
    CALCULATION_CONTRACT_VERSION,
    CALCULATION_ENGINE_VERSION,
    CalculationCategory,
    CalculationContribution,
    CalculationError,
    CalculationInputError,
    CalculationResult,
    CalculationStatus,
    calculate_matches,
)


def test_public_versions_exports_wire_values_and_result_shape() -> None:
    assert CALCULATION_CONTRACT_VERSION == "CalculationContract-13.0"
    assert CALCULATION_ENGINE_VERSION == "CalculationEngine-13.0"
    assert tuple(item.value for item in CalculationStatus) == (
        "calculated",
        "calculated_with_warnings",
        "no_values",
        "manual_review",
        "no_match",
    )
    assert tuple(item.value for item in CalculationCategory) == (
        "work",
        "material",
        "service",
        "unclassified",
    )
    assert callable(calculate_matches)
    assert issubclass(CalculationInputError, CalculationError)
    assert issubclass(CalculationError, ValueError)
    assert fields(CalculationResult)[-1].name == "contract_version"
    assert fields(CalculationResult)[-1].init is False


def test_contribution_rejects_float_and_nonfinite_decimal_values() -> None:
    common = {
        "contribution_id": "contribution",
        "candidate_id": "candidate",
        "source_row_id": "source",
        "source_row": object(),
        "category": CalculationCategory.UNCLASSIFIED,
        "raw_quantity": Decimal("1"),
        "raw_cost": Decimal("2"),
        "included_quantity": Decimal("1"),
        "included_cost": Decimal("2"),
        "include_quantity": True,
        "include_cost": True,
        "rule_ids": (),
        "decisions": (),
        "warnings": (),
        "source_provenance": {"source_row_id": "source"},
        "target_provenance": {"target_row_id": "target"},
    }
    with pytest.raises((TypeError, ValueError)):
        CalculationContribution(**(common | {"raw_cost": 2.0}))  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        CalculationContribution(**(common | {"raw_cost": Decimal("NaN")}))

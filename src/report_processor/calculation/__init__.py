"""Deterministic calculation engine (CalculationEngine-13.0)."""

from .engine import calculate_matches
from .exceptions import CalculationError, CalculationInputError
from .models import (
    CALCULATION_CONTRACT_VERSION,
    CALCULATION_ENGINE_VERSION,
    CalculationCategory,
    CalculationCategoryTotal,
    CalculationContribution,
    CalculationResult,
    CalculationStatus,
    CalculationTrace,
)

__all__ = (
    "CALCULATION_CONTRACT_VERSION",
    "CALCULATION_ENGINE_VERSION",
    "CalculationCategory",
    "CalculationCategoryTotal",
    "CalculationContribution",
    "CalculationError",
    "CalculationInputError",
    "CalculationResult",
    "CalculationStatus",
    "CalculationTrace",
    "calculate_matches",
)

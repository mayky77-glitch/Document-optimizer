"""Controlled input errors for CalculationEngine-13.0."""

from __future__ import annotations


class CalculationError(ValueError):
    code = "CALCULATION_ERROR"


class CalculationInputError(CalculationError):
    """Rejected immutable matching or rule-set input."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")

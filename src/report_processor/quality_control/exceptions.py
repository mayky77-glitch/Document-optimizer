"""Controlled errors for QualityControlEngine-14.0."""

from __future__ import annotations


class QualityControlError(ValueError):
    code = "QUALITY_CONTROL_ERROR"


class QualityControlInputError(QualityControlError):
    """Rejected public input that cannot be evaluated deterministically."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")

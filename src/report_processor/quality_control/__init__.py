"""Deterministic pre-write quality gate (QualityControlEngine-14.0)."""

from .engine import evaluate_quality_control
from .exceptions import QualityControlError, QualityControlInputError
from .models import (
    QUALITY_CONTROL_CONTRACT_VERSION,
    QUALITY_CONTROL_ENGINE_VERSION,
    QualityControlReport,
    QualityControlSummary,
    QualityDecision,
    QualityIssue,
    QualityLocation,
    QualitySeverity,
)

__all__ = (
    "QUALITY_CONTROL_CONTRACT_VERSION",
    "QUALITY_CONTROL_ENGINE_VERSION",
    "QualityControlError",
    "QualityControlInputError",
    "QualityControlReport",
    "QualityControlSummary",
    "QualityDecision",
    "QualityIssue",
    "QualityLocation",
    "QualitySeverity",
    "evaluate_quality_control",
)

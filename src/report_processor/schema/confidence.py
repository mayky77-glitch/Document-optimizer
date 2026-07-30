"""Explainable schema confidence, intentionally separate from status selection."""

from __future__ import annotations

from report_processor.schema.models import (
    ColumnResolution,
    HeaderCandidate,
    SheetClassification,
    SheetColumnRequirements,
)


def calculate_schema_confidence(
    classification: SheetClassification,
    header_candidate: HeaderCandidate | None,
    columns: tuple[ColumnResolution, ...],
    requirements: SheetColumnRequirements | None,
    warnings: tuple[str, ...],
) -> float:
    score = classification.confidence * 0.28
    score += (header_candidate.score if header_candidate else 0.0) * 0.27

    resolved = {item.logical_column for item in columns if item.status == "OK"}
    if requirements and requirements.required:
        required_ratio = len(resolved.intersection(requirements.required)) / len(
            requirements.required
        )
        score += required_ratio * 0.30
    else:
        successful = sum(item.status == "OK" for item in columns)
        score += min(successful / 5, 1.0) * 0.20

    unambiguous = sum(item.status == "OK" for item in columns)
    score += min(unambiguous / 6, 1.0) * 0.15

    penalties = {
        "SCAN_CELL_LIMIT_REACHED": 0.12,
        "AMBIGUOUS_HEADER": 0.18,
        "AMBIGUOUS_COLUMNS": 0.12,
        "MISSING_REQUIRED_COLUMNS": 0.18,
        "DATA_START_NOT_FOUND": 0.06,
    }
    for warning, penalty in penalties.items():
        if any(item == warning or item.startswith(f"{warning}:") for item in warnings):
            score -= penalty
    if classification.status == "AMBIGUOUS_SHEET_TYPE":
        score -= 0.18
    elif classification.status == "UNKNOWN_SHEET_TYPE":
        score -= 0.24
    return round(min(max(score, 0.0), 1.0), 4)

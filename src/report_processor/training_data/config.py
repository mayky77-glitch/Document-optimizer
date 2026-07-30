from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingDataConfig:
    include_non_detail_rows: bool = False
    include_outdated_rows: bool = False
    include_critical_formula_errors: bool = False
    deduplicate_exact_rows: bool = True

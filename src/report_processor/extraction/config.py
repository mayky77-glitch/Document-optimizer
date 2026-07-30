from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractionConfig:
    max_rows: int = 200_000
    max_consecutive_empty_rows: int = 20
    include_empty_rows: bool = False
    include_formula_without_cache: bool = True
    skip_repeated_headers: bool = True

    def __post_init__(self) -> None:
        if self.max_rows < 1:
            raise ValueError("max_rows должен быть положительным")
        if self.max_consecutive_empty_rows < 1:
            raise ValueError("max_consecutive_empty_rows должен быть положительным")

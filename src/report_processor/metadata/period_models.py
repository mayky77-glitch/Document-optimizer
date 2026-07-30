from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class DocumentPeriod:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 12:
            raise ValueError("month must be between 1 and 12")
        if not 1 <= self.year <= 9999:
            raise ValueError("year must be between 1 and 9999")

    @property
    def normalized(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def __str__(self) -> str:
        return self.normalized


@dataclass(frozen=True, slots=True)
class PeriodExtractionResult:
    value: DocumentPeriod | None
    candidates: tuple[DocumentPeriod, ...]
    status: str
    confidence: float | None
    source_fragment: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PeriodMatch:
    period: DocumentPeriod
    fragment: str
    start: int
    end: int
    confidence: float
    warnings: tuple[str, ...]

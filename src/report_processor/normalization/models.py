from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from report_processor.training_data.models import TrainingDataRow


def _frozen_dictionary(values: Mapping[str, str] | None) -> Mapping[str, str]:
    if values is None:
        return MappingProxyType({})
    copied: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("Словарь исправлений должен содержать только строки")
        copied[key] = value
    return MappingProxyType(dict(sorted(copied.items())))


@dataclass(frozen=True, slots=True)
class TypoDictionaries:
    """Exact replacement tables; values are data, never executable configuration."""

    codes: Mapping[str, str] | None = None
    names: Mapping[str, str] | None = None
    units: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "codes", _frozen_dictionary(self.codes))
        object.__setattr__(self, "names", _frozen_dictionary(self.names))
        object.__setattr__(self, "units", _frozen_dictionary(self.units))


@dataclass(frozen=True, slots=True)
class NormalizationConfig:
    """Data-only exact corrections used during schema 8 normalization."""

    code_typos: Mapping[str, str] | None = None
    name_typos: Mapping[str, str] | None = None
    unit_typos: Mapping[str, str] | None = None

    @property
    def typo_dictionaries(self) -> TypoDictionaries:
        return TypoDictionaries(
            codes=self.code_typos,
            names=self.name_typos,
            units=self.unit_typos,
        )


@dataclass(frozen=True, slots=True)
class NormalizedBusinessKey:
    """Business identity independent of a physical source file or row."""

    document_type: str
    document_period: str | None
    object_code: str | None
    subobject_code: str | None
    position_code: str | None
    cost_type_code: str | None
    drawing_code: str | None
    basis_code: str | None
    work_name: str | None
    unit: str | None

    def values(self) -> tuple[str | None, ...]:
        return (
            self.document_type,
            self.document_period,
            self.object_code,
            self.subobject_code,
            self.position_code,
            self.cost_type_code,
            self.drawing_code,
            self.basis_code,
            self.work_name,
            self.unit,
        )


@dataclass(frozen=True, slots=True)
class NormalizedSourceRow:
    """A block 7 row with immutable provenance and schema 8 business identity."""

    source_row: TrainingDataRow
    business_key: NormalizedBusinessKey
    line_id: str
    object_code: str | None
    subobject_code: str | None
    position_code: str | None
    cost_type_code: str | None
    drawing_code: str | None
    basis_code: str | None
    work_name: str | None
    unit: str | None
    work_name_tokens: tuple[str, ...]
    code_tokens: tuple[str, ...]
    unit_tokens: tuple[str, ...]

    @property
    def original_row(self) -> TrainingDataRow:
        return self.source_row

    @property
    def source_file_id(self) -> str:
        return self.source_row.source_file_id

    @property
    def source_filename(self) -> str:
        return self.source_row.source_filename

    @property
    def source_sheet(self) -> str:
        return self.source_row.source_sheet

    @property
    def source_row_number(self) -> int:
        return self.source_row.source_row

    @property
    def source_row_id(self) -> str:
        return self.source_row.source_row_id

    @property
    def provenance(self) -> Mapping[str, str | int]:
        return MappingProxyType(
            {
                "source_file_id": self.source_file_id,
                "source_filename": self.source_filename,
                "source_sheet": self.source_sheet,
                "source_row": self.source_row_number,
                "source_row_id": self.source_row_id,
            }
        )

    @property
    def normalized_name(self) -> str | None:
        return self.work_name

    @property
    def normalized_work_name(self) -> str | None:
        return self.work_name

    @property
    def normalized_unit(self) -> str | None:
        return self.unit

    @property
    def name_tokens(self) -> tuple[str, ...]:
        return self.work_name_tokens

    @property
    def warnings(self) -> tuple[str, ...]:
        return self.source_row.warnings

    @property
    def decimals(self) -> tuple[Decimal | None, ...]:
        return (
            self.source_row.contract_quantity,
            self.source_row.period_quantity,
            self.source_row.cumulative_quantity,
            self.source_row.remaining_quantity,
            self.source_row.unit_price,
            self.source_row.contract_cost,
            self.source_row.period_cost,
            self.source_row.cumulative_cost,
            self.source_row.total_cost,
        )


@dataclass(frozen=True, slots=True)
class NormalizationStatistics:
    input_rows: int
    output_rows: int


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    rows: tuple[NormalizedSourceRow, ...]
    statistics: NormalizationStatistics

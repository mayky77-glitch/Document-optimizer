from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from report_processor.extraction.models import ExtractedCellValue, SourceLocation


@dataclass(frozen=True, slots=True)
class KS2RawRow:
    source_location: SourceLocation
    source_values: tuple[ExtractedCellValue, ...]
    object_code: str | None
    object_name: str | None
    subobject_code: str | None
    subobject_name: str | None
    position_code: str | None
    work_name: str | None
    unit: str | None
    current_period_quantity: Decimal | None
    unit_price: Decimal | None
    current_period_cost: Decimal | None
    basis_code: str | None
    drawing_code: str | None
    cost_type_code: str | None
    warnings: tuple[str, ...]

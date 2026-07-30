from __future__ import annotations

from report_processor.extraction.models import CanonicalSourceRow
from report_processor.extraction.provenance import make_row_id
from report_processor.extraction.statuses import CanonicalRowStatus

from .models import SVVRRawRow


def map_svvr_to_canonical(
    raw: SVVRRawRow,
    *,
    document_index: str | None,
    document_period: str | None,
) -> CanonicalSourceRow:
    missing: list[str] = []
    if raw.work_name is None:
        missing.append("work_name")
    if raw.current_period_quantity is None:
        missing.append("current_period_quantity")
    if missing:
        status = CanonicalRowStatus.ERROR.value
        warnings = (*raw.warnings, *(f"REQUIRED_VALUE_MISSING:{item}" for item in missing))
    elif raw.warnings:
        status = CanonicalRowStatus.PARTIAL.value
        warnings = raw.warnings
    else:
        status = CanonicalRowStatus.OK.value
        warnings = ()
    location = raw.source_location
    return CanonicalSourceRow(
        row_id=make_row_id(location.source_file_id, location.sheet_name, location.row_number),
        source_type="svvr",
        source_location=location,
        document_index=document_index,
        document_period=document_period,
        object_code_raw=raw.object_code,
        object_name_raw=raw.object_name,
        subobject_code_raw=raw.subobject_code,
        subobject_name_raw=raw.subobject_name,
        position_code_raw=raw.position_code,
        work_name_raw=raw.work_name,
        unit_raw=raw.unit,
        contract_quantity=raw.contract_quantity,
        current_period_quantity=raw.current_period_quantity,
        cumulative_quantity=raw.cumulative_quantity,
        remaining_quantity=raw.remaining_quantity,
        unit_price=raw.unit_price,
        contract_cost=raw.contract_cost,
        current_period_cost=raw.current_period_cost,
        cumulative_cost=raw.cumulative_cost,
        total_cost=raw.total_cost,
        basis_code_raw=raw.basis_code,
        drawing_code_raw=raw.drawing_code,
        cost_type_code_raw=raw.cost_type_code,
        source_values=raw.source_values,
        status=status,
        warnings=tuple(dict.fromkeys(warnings)),
    )

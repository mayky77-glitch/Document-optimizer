from __future__ import annotations

from report_processor.extraction.models import CanonicalSourceRow
from report_processor.extraction.provenance import make_row_id
from report_processor.extraction.statuses import CanonicalRowStatus

from .models import KS2RawRow


def map_ks2_to_canonical(
    raw: KS2RawRow,
    *,
    document_index: str | None,
    document_period: str | None,
) -> CanonicalSourceRow:
    if raw.work_name is None:
        status = CanonicalRowStatus.ERROR.value
        warnings = (*raw.warnings, "REQUIRED_VALUE_MISSING:work_name")
    elif raw.warnings:
        status = CanonicalRowStatus.PARTIAL.value
        warnings = raw.warnings
    else:
        status = CanonicalRowStatus.OK.value
        warnings = ()
    location = raw.source_location
    return CanonicalSourceRow(
        row_id=make_row_id(location.source_file_id, location.sheet_name, location.row_number),
        source_type="ks2",
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
        contract_quantity=None,
        current_period_quantity=raw.current_period_quantity,
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=raw.unit_price,
        contract_cost=None,
        current_period_cost=raw.current_period_cost,
        cumulative_cost=None,
        total_cost=None,
        basis_code_raw=raw.basis_code,
        drawing_code_raw=raw.drawing_code,
        cost_type_code_raw=raw.cost_type_code,
        source_values=raw.source_values,
        status=status,
        warnings=tuple(dict.fromkeys(warnings)),
    )

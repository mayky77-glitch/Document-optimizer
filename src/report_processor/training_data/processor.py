from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from report_processor.extraction.models import CanonicalSourceRow

from .classification import is_detail_row, is_outdated_row, is_total_row
from .config import TrainingDataConfig
from .identity import disambiguate_line_id, make_line_id
from .models import (
    DataQualityStatus,
    FormulaErrorCode,
    TrainingDataResult,
    TrainingDataRow,
    TrainingDataStatistics,
)
from .normalization import normalize_code, normalize_text, normalize_unit
from .quality import assess_quality, detect_formula_error


def _row_signature(row: TrainingDataRow) -> tuple[object, ...]:
    excluded = {
        "source_file_id",
        "source_filename",
        "source_sheet",
        "source_row",
        "source_row_id",
        "line_id",
        "warnings",
    }
    return tuple(getattr(row, name) for name in row.__dataclass_fields__ if name not in excluded)


def _to_training_row(row: CanonicalSourceRow) -> TrainingDataRow:
    total = is_total_row(row)
    detail = is_detail_row(row, total=total)
    outdated = is_outdated_row(row)
    formula_error = detect_formula_error(row)
    quality, warnings = assess_quality(row, is_detail=detail, formula_error=formula_error)

    object_code = normalize_code(row.object_code_raw)
    subobject_code = normalize_code(row.subobject_code_raw)
    position_code = normalize_code(row.position_code_raw)
    cost_type_code = normalize_code(row.cost_type_code_raw)
    drawing_code = normalize_code(row.drawing_code_raw)
    basis_code = normalize_code(row.basis_code_raw)
    work_name_normalized = normalize_text(row.work_name_raw)
    unit_normalized = normalize_unit(row.unit_raw)
    location = row.source_location
    line_id = make_line_id(
        source_file_id=location.source_file_id,
        document_type=row.source_type,
        document_period=row.document_period,
        object_code=object_code,
        subobject_code=subobject_code,
        position_code=position_code,
        basis_code=basis_code,
        drawing_code=drawing_code,
        unit=unit_normalized,
        work_name=work_name_normalized,
    )
    return TrainingDataRow(
        document_type=row.source_type,
        document_period=row.document_period,
        source_file_id=location.source_file_id,
        source_filename=location.filename,
        source_sheet=location.sheet_name,
        source_row=location.row_number,
        source_row_id=row.row_id,
        object_code=object_code,
        subobject_code=subobject_code,
        position_code=position_code,
        cost_type_code=cost_type_code,
        drawing_code=drawing_code,
        basis_code=basis_code,
        work_name_raw=row.work_name_raw,
        work_name_normalized=work_name_normalized,
        unit_raw=row.unit_raw,
        unit_normalized=unit_normalized,
        contract_quantity=row.contract_quantity,
        period_quantity=row.current_period_quantity,
        cumulative_quantity=row.cumulative_quantity,
        remaining_quantity=row.remaining_quantity,
        unit_price=row.unit_price,
        contract_cost=row.contract_cost,
        period_cost=row.current_period_cost,
        cumulative_cost=row.cumulative_cost,
        total_cost=row.total_cost,
        is_detail=detail,
        is_total=total,
        is_outdated=outdated,
        formula_error=formula_error,
        data_quality_status=quality,
        line_id=line_id,
        warnings=warnings,
    )


def prepare_training_data(
    rows: tuple[CanonicalSourceRow, ...] | list[CanonicalSourceRow],
    *,
    config: TrainingDataConfig | None = None,
) -> TrainingDataResult:
    config = config or TrainingDataConfig()
    output: list[TrainingDataRow] = []
    skipped_non_detail = 0
    skipped_outdated = 0
    skipped_formula_errors = 0
    exact_duplicates = 0
    collisions = 0
    seen: dict[str, TrainingDataRow] = {}
    seen_signatures: dict[str, set[tuple[object, ...]]] = {}
    global_warnings: list[str] = []
    source_rows_by_id: dict[str, CanonicalSourceRow] = {}

    for source_row in rows:
        previous_source = source_rows_by_id.get(source_row.row_id)
        if previous_source is not None and previous_source != source_row:
            raise ValueError(
                f"Конфликтующие канонические строки имеют одинаковый row_id: {source_row.row_id}"
            )
        source_rows_by_id[source_row.row_id] = source_row

    for source_row in sorted(rows, key=lambda item: item.row_id):
        prepared = _to_training_row(source_row)
        if not prepared.is_detail and not config.include_non_detail_rows:
            skipped_non_detail += 1
            continue
        if prepared.is_outdated and not config.include_outdated_rows:
            skipped_outdated += 1
            continue
        if (
            prepared.formula_error
            in {FormulaErrorCode.EXCEL_ERROR, FormulaErrorCode.VALUE_READ_FAILED}
            and not config.include_critical_formula_errors
        ):
            skipped_formula_errors += 1
            continue

        base_line_id = prepared.line_id
        signature = _row_signature(prepared)
        previous = seen.get(base_line_id)
        if previous is None:
            seen[base_line_id] = prepared
            seen_signatures[base_line_id] = {signature}
            output.append(prepared)
            continue

        signatures = seen_signatures[base_line_id]
        if config.deduplicate_exact_rows and signature in signatures:
            exact_duplicates += 1
            continue

        collisions += 1
        signatures.add(signature)
        collision_warning = f"LINE_ID_COLLISION:{base_line_id}"
        global_warnings.append(collision_warning)
        prepared = replace(
            prepared,
            line_id=disambiguate_line_id(base_line_id, prepared.source_row_id),
            data_quality_status=DataQualityStatus.WARNING,
            warnings=tuple(dict.fromkeys((*prepared.warnings, collision_warning))),
        )
        while prepared.line_id in seen:
            prepared = replace(
                prepared,
                line_id=disambiguate_line_id(prepared.line_id, prepared.source_row_id),
            )
        seen[prepared.line_id] = prepared
        output.append(prepared)

    statistics = TrainingDataStatistics(
        input_rows=len(rows),
        output_rows=len(output),
        skipped_non_detail_rows=skipped_non_detail,
        skipped_outdated_rows=skipped_outdated,
        skipped_formula_error_rows=skipped_formula_errors,
        exact_duplicates_removed=exact_duplicates,
        line_id_collisions=collisions,
    )
    return TrainingDataResult(
        rows=tuple(output),
        statistics=statistics,
        warnings=tuple(dict.fromkeys(global_warnings)),
    )


def sum_decimal_field(rows: tuple[TrainingDataRow, ...], field_name: str) -> Decimal:
    total = Decimal("0")
    for row in rows:
        value = getattr(row, field_name)
        if isinstance(value, Decimal):
            total += value
    return total

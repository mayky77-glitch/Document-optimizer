from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from report_processor.training_data.models import TrainingDataRow

from .identity import make_line_id
from .models import (
    NormalizationConfig,
    NormalizationResult,
    NormalizationStatistics,
    NormalizedBusinessKey,
    NormalizedSourceRow,
    TypoDictionaries,
)
from .normalizers import normalize_code, normalize_name, normalize_unit, stable_tokens


def normalize_training_row(
    row: TrainingDataRow,
    *,
    typo_dictionaries: TypoDictionaries | None = None,
) -> NormalizedSourceRow:
    dictionaries = typo_dictionaries or TypoDictionaries()
    object_code = normalize_code(row.object_code, dictionaries)
    subobject_code = normalize_code(row.subobject_code, dictionaries)
    position_code = normalize_code(row.position_code, dictionaries)
    cost_type_code = normalize_code(row.cost_type_code, dictionaries)
    drawing_code = normalize_code(row.drawing_code, dictionaries)
    basis_code = normalize_code(row.basis_code, dictionaries)
    work_name = normalize_name(row.work_name_normalized or row.work_name_raw, dictionaries)
    unit = normalize_unit(row.unit_normalized or row.unit_raw, dictionaries)
    business_key = NormalizedBusinessKey(
        document_type=normalize_name(row.document_type, dictionaries) or "",
        document_period=normalize_code(row.document_period, dictionaries),
        object_code=object_code,
        subobject_code=subobject_code,
        position_code=position_code,
        cost_type_code=cost_type_code,
        drawing_code=drawing_code,
        basis_code=basis_code,
        work_name=work_name,
        unit=unit,
    )
    codes = (
        object_code,
        subobject_code,
        position_code,
        cost_type_code,
        drawing_code,
        basis_code,
    )
    return NormalizedSourceRow(
        source_row=row,
        business_key=business_key,
        line_id=make_line_id(business_key),
        object_code=object_code,
        subobject_code=subobject_code,
        position_code=position_code,
        cost_type_code=cost_type_code,
        drawing_code=drawing_code,
        basis_code=basis_code,
        work_name=work_name,
        unit=unit,
        work_name_tokens=stable_tokens(work_name),
        code_tokens=tuple(token for code in codes for token in stable_tokens(code)),
        unit_tokens=stable_tokens(unit),
    )


def normalize_training_data(
    rows: Iterable[TrainingDataRow],
    *,
    typo_dictionaries: TypoDictionaries | None = None,
) -> NormalizationResult:
    normalized_rows = tuple(
        normalize_training_row(row, typo_dictionaries=typo_dictionaries) for row in rows
    )
    line_id_counts = Counter(row.line_id for row in normalized_rows)
    collisions = sum(count - 1 for count in line_id_counts.values())
    warnings = tuple(
        f"LINE_ID_COLLISION:{line_id}"
        for line_id, count in sorted(line_id_counts.items())
        if count > 1
    )
    return NormalizationResult(
        rows=normalized_rows,
        statistics=NormalizationStatistics(
            input_rows=len(normalized_rows),
            output_rows=len(normalized_rows),
            line_id_collisions=collisions,
        ),
        warnings=warnings,
    )


def normalize_training_rows(
    rows: Iterable[TrainingDataRow],
    *,
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """Normalize every block 7 row without filtering or deduplication."""
    return normalize_training_data(
        rows,
        typo_dictionaries=config.typo_dictionaries if config is not None else None,
    )

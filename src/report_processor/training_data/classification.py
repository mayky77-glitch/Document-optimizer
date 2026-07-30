from __future__ import annotations

from report_processor.extraction.models import CanonicalSourceRow

from .normalization import normalize_text

_TOTAL_PREFIXES = (
    "итого",
    "всего",
    "накопительно",
    "за отчетный период",
    "за отчётный период",
    "к оплате",
    "общая стоимость",
    "сумма по",
    "сумма всего",
)
_OUTDATED_MARKERS = (
    "неактуал",
    "не актуал",
    "устарев",
    "архив",
    "historical",
)


def is_outdated_row(row: CanonicalSourceRow) -> bool:
    sheet = normalize_text(row.source_location.sheet_name) or ""
    filename = normalize_text(row.source_location.filename) or ""
    return any(marker in sheet or marker in filename for marker in _OUTDATED_MARKERS)


def is_total_row(row: CanonicalSourceRow) -> bool:
    work_name = normalize_text(row.work_name_raw) or ""
    for prefix in _TOTAL_PREFIXES:
        if work_name == prefix:
            return True
        if work_name.startswith(prefix) and work_name[len(prefix) : len(prefix) + 1] in {
            " ",
            ":",
            ";",
            ",",
            "-",
        }:
            return True
    return False


def is_detail_row(row: CanonicalSourceRow, *, total: bool | None = None) -> bool:
    if total is None:
        total = is_total_row(row)
    if total or normalize_text(row.work_name_raw) is None:
        return False
    detail_evidence = (
        row.position_code_raw,
        row.basis_code_raw,
        row.drawing_code_raw,
        row.unit_raw,
        row.contract_quantity,
        row.current_period_quantity,
        row.cumulative_quantity,
        row.remaining_quantity,
        row.unit_price,
        row.contract_cost,
        row.current_period_cost,
        row.cumulative_cost,
        row.total_cost,
    )
    return any(value not in (None, "") for value in detail_evidence)

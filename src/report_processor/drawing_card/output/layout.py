"""Deterministic placement of object and drawing-code blocks."""

from __future__ import annotations

from collections import defaultdict

from ..models import DrawingCardResultRow, DrawingCodeBlockLayout, ObjectBlockLayout
from .contract import MAIN_CARD_SHEET_NAME


def plan_layout(
    rows: list[DrawingCardResultRow],
    *,
    objects_per_sheet: int = 4,
    first_sheet_name: str = MAIN_CARD_SHEET_NAME,
    additional_sheet_prefix: str = "Карточка",
) -> list[ObjectBlockLayout]:
    drawings: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (row.object_index, row.drawing_code.group_key)
        if key in seen:
            continue
        seen.add(key)
        drawings[row.object_index].append(row.drawing_code.raw)
    layouts: list[ObjectBlockLayout] = []
    for object_number, object_index in enumerate(sorted(drawings)):
        sheet_number = object_number // objects_per_sheet
        slot = object_number % objects_per_sheet
        sheet_name = (
            first_sheet_name
            if sheet_number == 0
            else f"{additional_sheet_prefix} {sheet_number + 1}"
        )
        start_column = 2 + slot * 6
        blocks = tuple(
            DrawingCodeBlockLayout(
                drawing_code=drawing_code,
                start_row=4 + index * 8,
                end_row=11 + index * 8,
            )
            for index, drawing_code in enumerate(drawings[object_index])
        )
        layouts.append(
            ObjectBlockLayout(
                sheet_name=sheet_name,
                object_index=object_index,
                start_column=start_column,
                end_column=start_column + 4,
                header_row=2,
                column_header_row=3,
                data_start_row=4,
                drawing_code_blocks=blocks,
            )
        )
    return layouts

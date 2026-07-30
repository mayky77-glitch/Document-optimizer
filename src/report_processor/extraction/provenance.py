from __future__ import annotations

import hashlib

from report_processor.excel import DualWorkbookSession
from report_processor.schema import ColumnResolution, SheetType

from .models import SourceLocation


def make_row_id(source_file_id: str, sheet_name: str, row_number: int) -> str:
    payload_parts = (source_file_id, sheet_name, str(row_number))
    payload = b"".join(
        len(part.encode("utf-8")).to_bytes(8, byteorder="big") + part.encode("utf-8")
        for part in payload_parts
    )
    return hashlib.sha256(payload).hexdigest()


def make_row_location(
    session: DualWorkbookSession,
    *,
    sheet_name: str,
    sheet_type: SheetType,
    row_number: int,
) -> SourceLocation:
    return SourceLocation(
        source_file_id=session.source_file_id,
        filename=session.filename,
        sheet_name=sheet_name,
        sheet_type=sheet_type.value,
        row_number=row_number,
    )


def make_cell_location(
    session: DualWorkbookSession,
    *,
    sheet_name: str,
    sheet_type: SheetType,
    row_number: int,
    column: ColumnResolution,
) -> SourceLocation:
    coordinate = f"{column.column_letter}{row_number}"
    return SourceLocation(
        source_file_id=session.source_file_id,
        filename=session.filename,
        sheet_name=sheet_name,
        sheet_type=sheet_type.value,
        row_number=row_number,
        column_number=column.column_index,
        column_letter=column.column_letter,
        coordinate=coordinate,
    )

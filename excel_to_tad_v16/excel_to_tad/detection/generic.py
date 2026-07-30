"""Поиск и извлечение обычных многострочных Excel-таблиц."""

from __future__ import annotations

from typing import Any

from ..constants import (
    GENERIC_DIGITS_RE,
    GENERIC_FOOTER_PHRASES,
    GENERIC_FOOTER_STARTS,
    GENERIC_HEADER_TERMS,
    GENERIC_NO_NUMBER_RE,
    GENERIC_NUMBER_LABEL_RE,
    GENERIC_NUMBER_WITH_SUFFIX_RE,
    GENERIC_TITLE_MARKERS,
)
from ..dataframe import build_typed_dataframe
from ..normalization import (
    clean_text,
    is_small_integer,
    is_structural_empty,
    make_unique_headers,
    normalized,
    to_float,
)


def is_number_like(value: Any) -> bool:
    return to_float(value) is not None

def generic_header_text(value: Any) -> str | None:
    """
    Для названия колонки используем текст, а не служебные числовые значения
    из многострочной шапки. Числа вроде 1, 2, 3 и промежуточные итоги
    не превращаются в имена колонок.
    """
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    if is_number_like(cleaned):
        return None

    norm = normalized(cleaned)
    if not norm or norm in {"скрыть", "true", "false"}:
        return None

    return cleaned

def joined_header_for_column(
    worksheet: Any,
    column_number: int,
    start_row: int,
    end_row: int,
) -> str | None:
    parts: list[str] = []

    for row_number in range(start_row, end_row + 1):
        part = generic_header_text(
            worksheet.cell(row=row_number, column=column_number).value
        )
        if part and normalized(part) not in {
            normalized(existing) for existing in parts
        }:
            parts.append(part)

    if not parts:
        return None

    return " / ".join(parts)

def generic_known_header_hits(text: str) -> int:
    norm = normalized(text)
    tokens = set(norm.split())
    hits = 0

    for term in GENERIC_HEADER_TERMS:
        term_norm = normalized(term)
        if " " in term_norm:
            if term_norm in norm:
                hits += 1
        elif term_norm in tokens:
            hits += 1

    return hits

def row_nonempty_count(
    worksheet: Any,
    row_number: int,
    min_column: int,
    max_column: int,
) -> int:
    return sum(
        not is_structural_empty(
            worksheet.cell(row=row_number, column=column_number).value
        )
        for column_number in range(min_column, max_column + 1)
    )

def find_generic_header_band(
    worksheet: Any,
    scan_rows: int = 220,
) -> dict[str, Any] | None:
    """
    Ищет основную многострочную шапку на обычном листе.

    Матрица верхней части листа и префиксные суммы строятся один раз, чтобы
    не перечитывать и не нормализовать одни и те же ячейки для каждого окна.
    Формула оценки и критерии выбора сохранены.
    """
    max_row = min(int(worksheet.max_row or 0), scan_rows)
    max_column = min(int(worksheet.max_column or 0), 350)

    if max_row <= 0 or max_column <= 0:
        return None

    matrix = [
        list(row)
        for row in worksheet.iter_rows(
            min_row=1,
            max_row=max_row,
            min_col=1,
            max_col=max_column,
            values_only=True,
        )
    ]
    header_matrix: list[list[str | None]] = []
    nonempty_prefix: list[list[int]] = []
    row_long_cells: list[int] = []
    row_numeric_cells: list[int] = []
    row_numbering_like: list[bool] = []

    for row in matrix:
        header_row: list[str | None] = []
        prefix = [0]
        long_cells = 0
        numeric_cells = 0
        band_values: list[Any] = []

        for value in row:
            cleaned = clean_text(value)
            nonempty = cleaned is not None
            prefix.append(prefix[-1] + int(nonempty))
            header_row.append(generic_header_text(value))

            if not nonempty:
                continue
            band_values.append(value)
            if len(cleaned or "") > 160:
                long_cells += 1
            if is_number_like(value):
                numeric_cells += 1

        numbering_like = False
        if len(band_values) >= 2:
            accepted = sum(
                is_small_integer(value) or normalized(value) == "скрыть"
                for value in band_values
            )
            numbering_like = accepted / len(band_values) >= 0.65

        header_matrix.append(header_row)
        nonempty_prefix.append(prefix)
        row_long_cells.append(long_cells)
        row_numeric_cells.append(numeric_cells)
        row_numbering_like.append(numbering_like)

    known_hits_cache: dict[str, int] = {}
    best: dict[str, Any] | None = None

    for end_row_index in range(max_row):
        end_row = end_row_index + 1

        for height in (1, 2, 3, 4):
            start_row_index = end_row_index - height + 1
            if start_row_index < 0:
                continue
            start_row = start_row_index + 1

            headers: dict[int, str] = {}
            known_hits = 0

            for column_index in range(max_column):
                parts: list[str] = []
                seen_parts: set[str] = set()

                for row_index in range(start_row_index, end_row_index + 1):
                    part = header_matrix[row_index][column_index]
                    if not part:
                        continue
                    norm_part = normalized(part)
                    if norm_part in seen_parts:
                        continue
                    seen_parts.add(norm_part)
                    parts.append(part)

                if not parts:
                    continue

                header = " / ".join(parts)
                column_number = column_index + 1
                headers[column_number] = header
                hits = known_hits_cache.get(header)
                if hits is None:
                    hits = generic_known_header_hits(header)
                    known_hits_cache[header] = hits
                known_hits += hits

            if len(headers) < 2:
                continue

            long_cells = sum(
                row_long_cells[start_row_index : end_row_index + 1]
            )
            numeric_cells = sum(
                row_numeric_cells[start_row_index : end_row_index + 1]
            )
            numbering_like_rows = sum(
                row_numbering_like[start_row_index : end_row_index + 1]
            )

            min_column = min(headers)
            max_header_column = max(headers)
            width = max_header_column - min_column + 1

            future_rows = 0
            future_cells = 0
            future_end_index = min(end_row_index + 12, max_row - 1)
            for future_index in range(end_row_index + 1, future_end_index + 1):
                prefix = nonempty_prefix[future_index]
                count = (
                    prefix[max_header_column]
                    - prefix[min_column - 1]
                )
                future_cells += count
                if count >= 2:
                    future_rows += 1

            combined = normalized(" ".join(headers.values()))
            title_hits = sum(
                marker in combined for marker in GENERIC_TITLE_MARKERS
            )

            minimum_future_rows = 2 if len(headers) == 2 else 3
            if future_rows < minimum_future_rows:
                continue
            if known_hits == 0 and len(headers) < 4:
                continue

            text_columns = len(headers)
            score = (
                known_hits * 28.0
                + min(text_columns, 40) * 4.0
                + future_rows * 8.0
                + min(future_cells, 120) * 0.65
                - max(width - len(headers), 0) * 0.15
                - title_hits * 24.0
                - long_cells * 38.0
                - numeric_cells * 3.0
                - numbering_like_rows * 42.0
                - (height - 1) * 18.0
                - max(start_row - 180, 0) * 0.5
            )

            if title_hits >= 2 and known_hits < 2:
                score -= 60.0

            candidate = {
                "start_row": start_row,
                "end_row": end_row,
                "headers": headers,
                "min_column": min_column,
                "max_column": max_header_column,
                "known_header_hits": known_hits,
                "future_active_rows": future_rows,
                "score": round(score, 2),
            }

            if best is None or score > float(best["score"]):
                best = candidate

    if best is None or float(best["score"]) < 85.0:
        return None

    return best

def is_generic_numbering_row(values: list[Any]) -> bool:
    # Точки и тире рядом с номерами колонок не должны снижать долю
    # распознанных технических значений.
    nonempty = [value for value in values if not is_structural_empty(value)]
    if len(nonempty) < 2:
        return False

    accepted = 0
    for value in nonempty:
        norm = normalized(value)
        if (
            is_small_integer(value)
            or norm == "скрыть"
            or bool(GENERIC_NUMBER_LABEL_RE.fullmatch(norm))
            or bool(GENERIC_DIGITS_RE.fullmatch(norm))
            or bool(GENERIC_NUMBER_WITH_SUFFIX_RE.fullmatch(norm))
            or bool(GENERIC_NO_NUMBER_RE.fullmatch(norm))
        ):
            accepted += 1

    return accepted / len(nonempty) >= 0.65

def is_generic_footer_row(values: list[Any]) -> bool:
    cleaned = [
        clean_text(value)
        for value in values
        if clean_text(value) is not None
    ]
    if not cleaned:
        return False

    norms = [normalized(value) for value in cleaned]
    combined = " | ".join(norms)

    for norm in norms:
        if any(norm.startswith(prefix) for prefix in GENERIC_FOOTER_STARTS):
            # «Материалы поставки Заказчика» не начинается со слова
            # «Заказчик» и поэтому не считается подписью.
            return True

    if any(phrase in combined for phrase in GENERIC_FOOTER_PHRASES):
        return True

    # Отдельная строка «М.П.» или «должность / подпись».
    return bool(len(norms) <= 4 and any(norm in {"м п", "должность", "подпись"} for norm in norms))

def find_last_nonempty_row_in_columns(
    worksheet: Any,
    start_row: int,
    min_column: int,
    max_column: int,
) -> int | None:
    last: int | None = None

    for row_number in range(
        start_row,
        int(worksheet.max_row or start_row) + 1,
    ):
        if row_nonempty_count(
            worksheet,
            row_number,
            min_column,
            max_column,
        ) > 0:
            last = row_number

    return last

def build_generic_trimmed_dataframe(
    polars: Any,
    worksheet: Any,
) -> tuple[Any, dict[str, Any]]:
    """Выделяет основную таблицу обычного листа и формирует её в памяти."""
    sheet_title_norm = normalized(getattr(worksheet, "title", ""))
    if any(
        marker in sheet_title_norm
        for marker in ("титул", "титульный лист", "обложка")
    ):
        raise ValueError(
            "Лист определён как титульный и не содержит основной таблицы."
        )

    detected = find_generic_header_band(worksheet)
    if detected is None:
        raise ValueError(
            "Не удалось уверенно определить основную табличную область."
        )

    header_start = int(detected["start_row"])
    header_end = int(detected["end_row"])
    min_column = int(detected["min_column"])
    max_column = int(detected["max_column"])

    active_columns = {int(column) for column in detected["headers"]}
    for column_number in range(min_column, max_column + 1):
        for row_number in range(
            header_end + 1,
            min(
                header_end + 41,
                int(worksheet.max_row or header_end),
            ) + 1,
        ):
            if clean_text(
                worksheet.cell(
                    row=row_number,
                    column=column_number,
                ).value
            ) is not None:
                active_columns.add(column_number)
                break

    if not active_columns:
        raise ValueError("В найденной таблице отсутствуют активные колонки.")

    min_column = min(active_columns)
    max_column = max(active_columns)
    ordered_columns = list(range(min_column, max_column + 1))

    header_values = [
        joined_header_for_column(
            worksheet,
            column_number,
            header_start,
            header_end,
        )
        or f"column_{column_number}"
        for column_number in ordered_columns
    ]
    headers = make_unique_headers(header_values, len(header_values))

    data_start = header_end + 1
    skipped_numbering_rows = 0

    while data_start <= int(worksheet.max_row or data_start):
        values = [
            worksheet.cell(
                row=data_start,
                column=column_number,
            ).value
            for column_number in ordered_columns
        ]
        if not is_generic_numbering_row(values):
            break
        data_start += 1
        skipped_numbering_rows += 1

    last_nonempty = find_last_nonempty_row_in_columns(
        worksheet,
        data_start,
        min_column,
        max_column,
    )
    if last_nonempty is None:
        raise ValueError("После шапки таблицы не найдено строк данных.")

    footer_row: int | None = None
    for row_number in range(data_start, last_nonempty + 1):
        values = [
            worksheet.cell(
                row=row_number,
                column=column_number,
            ).value
            for column_number in ordered_columns
        ]
        if row_number >= data_start + 2 and is_generic_footer_row(values):
            footer_row = row_number
            break

    data_end = footer_row - 1 if footer_row is not None else last_nonempty
    skipped_empty_rows = 0
    first_written_row: int | None = None
    last_written_row: int | None = None
    rows: list[list[Any]] = []

    for row_number in range(data_start, data_end + 1):
        row_values = [
            worksheet.cell(
                row=row_number,
                column=column_number,
            ).value
            for column_number in ordered_columns
        ]

        if all(is_structural_empty(value) for value in row_values):
            skipped_empty_rows += 1
            continue

        rows.append(row_values)
        if first_written_row is None:
            first_written_row = row_number
        last_written_row = row_number

    if not rows:
        raise ValueError(
            "После удаления титульных и служебных строк таблица пуста."
        )

    dataframe, column_types = build_typed_dataframe(polars, headers, rows)
    metadata = {
        "mode": "generic_trimmed_table",
        "header_start_excel_row": header_start,
        "header_end_excel_row": header_end,
        "data_start_excel_row": data_start,
        "data_end_excel_row": data_end,
        "footer_start_excel_row": footer_row,
        "first_written_excel_row": first_written_row,
        "last_written_excel_row": last_written_row,
        "skipped_numbering_rows": skipped_numbering_rows,
        "skipped_empty_rows": skipped_empty_rows,
        "columns": dataframe.width,
        "written_rows": dataframe.height,
        "header_detection_score": detected["score"],
        "known_header_hits": detected["known_header_hits"],
        "output_columns": headers,
        "column_types": column_types,
        "numeric_rounding": None,
    }
    return dataframe, metadata

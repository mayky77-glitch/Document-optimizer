"""Распознавание и извлечение основной формы КС-2."""

from __future__ import annotations

import heapq
from difflib import SequenceMatcher
from typing import Any

from ..constants import (
    ALL_KS2_KEYS, FIELD_MIN_SCORE, HEADER_PROTOTYPES,
    KS2_EXCLUDED_TITLE_MARKERS, KS2_SHEET_RE, LOGICAL_KEYS, TARGET_HEADERS,
)
from ..normalization import (
    clean_text, compact_normalized, is_small_integer, normalized,
    positive_integer, to_float,
)

def sheet_name_has_ks2(sheet_name: str) -> bool:
    """Распознаёт кириллические и латинские варианты записи КС-2."""
    text = normalized(sheet_name)
    compact = compact_normalized(sheet_name)
    return bool(
        KS2_SHEET_RE.search(text)
        or "кс2" in compact
        or "кс02" in compact
    )

def is_excluded_ks2_title(sheet_name: str) -> bool:
    text = normalized(sheet_name)
    return any(marker in text.split() for marker in KS2_EXCLUDED_TITLE_MARKERS)

def worksheet_ks2_signature(worksheet: Any, scan_rows: int = 50) -> bool:
    """Ищет характерную надпись формы КС-2 в верхней части листа."""
    max_column = min(int(worksheet.max_column or 1), 80)
    markers = (
        "о приемке выполненных работ",
        "акт о приемке выполненных работ",
        "форма кс 2",
    )

    return any(
        any(marker in normalized(value) for marker in markers)
        for row in worksheet.iter_rows(
            min_row=1,
            max_row=min(scan_rows, int(worksheet.max_row or scan_rows)),
            max_col=max_column,
            values_only=True,
        )
        for value in row
        if value is not None
    )

def is_ks2_sheet(sheet_name: str, worksheet: Any | None = None) -> bool:
    """
    Определяет именно основную форму КС-2, а не реестры и справочники.

    Название может быть «КС-2», «КС2», «KC 02», «Акт КС-2»,
    «Форма КС-2», «КС-2 логистика» и т. п.
    """
    if is_excluded_ks2_title(sheet_name):
        return False

    if sheet_name_has_ks2(sheet_name):
        return True

    return worksheet is not None and worksheet_ks2_signature(worksheet)

def token_similarity(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())

    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0

def header_match_score(value: Any, field: str) -> int:
    """Оценка 0–100: насколько текст похож на заголовок нужного поля."""
    text = normalized(value)
    if not text:
        return 0

    # Защита от наиболее частых ложных совпадений.
    if field == "name":
        if "работ" not in text and "затрат" not in text:
            return 0
        if any(
            phrase in text
            for phrase in (
                "наименование объекта",
                "наименование стройки",
                "наименование подрядчика",
                "наименование заказчика",
                "наименование документа",
            )
        ):
            return 0

    if field == "unit" and "измер" not in text and text not in {"еи", "ед"}:
        return 0

    if field == "quantity" and not any(
        token in text for token in ("количество", "объем")
    ):
        return 0

    if field == "unit_price" and not any(
        phrase in text
        for phrase in (
            "цена",
            "расценка",
            "за единицу",
            "стоимость единицы",
            "единичная стоимость",
        )
    ):
        return 0

    if field == "cost":
        if "стоимость" not in text and "сумма" not in text and "всего" not in text:
            return 0
        if (
            "за единицу" in text
            or "стоимость единицы" in text
            or "единичная стоимость" in text
            or "сметная стоимость" in text
            or "договорная стоимость" in text
        ) and "общая стоимость" not in text:
            return 0

    if field == "order" and not any(
        token in text for token in ("поряд", "номер", "п п", "позици")
    ):
        return 0

    best = 0.0

    for prototype_raw in HEADER_PROTOTYPES[field]:
        prototype = normalized(prototype_raw)

        if text == prototype:
            score = 100.0
        elif prototype in text:
            extra = max(len(text.split()) - len(prototype.split()), 0)
            score = max(92.0 - extra * 2.0, 78.0)
        elif text in prototype and len(text.split()) >= 2:
            score = 86.0
        else:
            jaccard = token_similarity(text, prototype)
            sequence = SequenceMatcher(None, text, prototype).ratio()
            score = max(jaccard * 92.0, sequence * 82.0)

        best = max(best, score)

    # Предпочитаем конкретные формулировки над слишком общими.
    if field == "cost" and "общая стоимость" in text:
        best = max(best, 100.0)
    if field == "unit_price" and (
        "за единицу" in text or "расценка" in text
    ):
        best = max(best, 96.0)
    if field == "order" and "по порядку" in text:
        best = max(best, 100.0)
    if field == "name" and "наименование" in text and "работ" in text:
        best = max(best, 93.0)

    return int(round(min(best, 100.0)))

def header_kind(value: Any) -> str | None:
    """Совместимый вспомогательный интерфейс: лучший тип заголовка."""
    scored = [
        (header_match_score(value, field), field)
        for field in ALL_KS2_KEYS
    ]
    score, field = max(scored)
    return field if score >= FIELD_MIN_SCORE[field] else None

def build_header_candidates(
    worksheet: Any,
    scan_rows: int,
) -> dict[str, list[dict[str, Any]]]:
    """
    Формирует кандидатов по отдельным ячейкам и вертикальным фразам
    из 2–4 строк. Это позволяет распознавать многострочные заголовки.
    """
    max_row = min(scan_rows, int(worksheet.max_row or scan_rows))
    max_column = min(int(worksheet.max_column or 1), 300)

    matrix: list[list[Any]] = []
    for row in worksheet.iter_rows(
        min_row=1,
        max_row=max_row,
        max_col=max_column,
        values_only=True,
    ):
        matrix.append(list(row))

    candidates: dict[str, list[dict[str, Any]]] = {
        field: [] for field in ALL_KS2_KEYS
    }
    seen_hashes: set[int] = set()

    for column_index in range(max_column):
        for end_row_index in range(max_row):
            for window in (1, 2, 3, 4):
                start_row_index = max(0, end_row_index - window + 1)
                raw_parts: list[str] = []

                for row_index in range(start_row_index, end_row_index + 1):
                    value = matrix[row_index][column_index]
                    cleaned = clean_text(value)
                    if cleaned and cleaned not in raw_parts:
                        raw_parts.append(cleaned)

                if not raw_parts:
                    continue

                phrase = " ".join(raw_parts)
                norm_phrase = normalized(phrase)

                for field in ALL_KS2_KEYS:
                    score = header_match_score(phrase, field)
                    if score < FIELD_MIN_SCORE[field]:
                        continue

                    phrase_hash = hash(
                        (
                            field,
                            end_row_index + 1,
                            column_index + 1,
                            norm_phrase,
                        )
                    )
                    if phrase_hash in seen_hashes:
                        continue
                    seen_hashes.add(phrase_hash)

                    candidates[field].append({
                        "field": field,
                        "score": score,
                        "row": end_row_index + 1,
                        "start_row": start_row_index + 1,
                        "column": column_index + 1,
                        "source_header": phrase,
                    })

    for field in ALL_KS2_KEYS:
        candidates[field].sort(
            key=lambda item: (
                -item["score"],
                item["row"] - item["start_row"],
                item["row"],
                item["column"],
            )
        )
        candidates[field] = candidates[field][:60]

    return candidates

def find_ks2_columns(
    worksheet: Any,
    scan_rows: int = 180,
) -> tuple[dict[str, int], int, dict[str, Any]]:
    """
    Нечётко распознаёт шесть колонок КС-2 и проверяет их порядок:
    номер -> наименование -> единица -> количество -> цена -> стоимость.
    """
    candidates = build_header_candidates(worksheet, scan_rows)

    missing = [
        field for field in ALL_KS2_KEYS
        if not candidates[field]
    ]
    if missing:
        raise ValueError(
            "Не найдены обязательные заголовки КС-2: "
            + ", ".join(missing)
        )

    # Beam search по ожидаемому порядку колонок. Он устойчивее жёсткого
    # выбора одного ближайшего текста и не допускает одну колонку дважды.
    states: list[dict[str, Any]] = [{
        "selected": {},
        "score": 0.0,
        "last_column": 0,
        "min_row": None,
        "max_row": None,
    }]

    for field in ALL_KS2_KEYS:
        expanded: list[dict[str, Any]] = []

        for state in states:
            for candidate in candidates[field]:
                column = int(candidate["column"])
                if column <= int(state["last_column"]):
                    continue

                min_row = (
                    int(candidate["start_row"])
                    if state["min_row"] is None
                    else min(int(state["min_row"]), int(candidate["start_row"]))
                )
                max_row = (
                    int(candidate["row"])
                    if state["max_row"] is None
                    else max(int(state["max_row"]), int(candidate["row"]))
                )
                row_span = max_row - min_row

                if row_span > 8:
                    continue

                previous_column = int(state["last_column"])
                gap_penalty = max(column - previous_column - 8, 0) * 0.35
                row_penalty = row_span * 1.8

                selected = dict(state["selected"])
                selected[field] = candidate
                expanded.append({
                    "selected": selected,
                    "score": (
                        float(state["score"])
                        + float(candidate["score"])
                        - gap_penalty
                        - row_penalty
                    ),
                    "last_column": column,
                    "min_row": min_row,
                    "max_row": max_row,
                })

        if not expanded:
            raise ValueError(
                "Заголовки найдены, но не образуют ожидаемую "
                "структуру колонок КС-2."
            )

        states = heapq.nlargest(
            160,
            expanded,
            key=lambda state: float(state["score"]),
        )

    best = states[0]
    selected = best["selected"]
    mapping = {
        field: int(selected[field]["column"])
        for field in ALL_KS2_KEYS
    }
    header_last_row = max(
        int(selected[field]["row"])
        for field in ALL_KS2_KEYS
    )

    diagnostics = {
        field: {
            "excel_row": int(selected[field]["row"]),
            "excel_start_row": int(selected[field]["start_row"]),
            "excel_column": int(selected[field]["column"]),
            "source_header": str(selected[field]["source_header"]),
            "match_score": int(selected[field]["score"]),
        }
        for field in ALL_KS2_KEYS
    }
    diagnostics["layout_score"] = round(float(best["score"]), 2)

    return mapping, header_last_row, diagnostics

def is_technical_numbering_row(values: dict[str, Any]) -> bool:
    """
    Строка под заголовком вида:
        3 | 5 | 6 | 7 | 8
    """
    present = [
        values[key]
        for key in LOGICAL_KEYS
        if values[key] not in (None, "")
    ]

    return (
        len(present) >= 4
        and all(is_small_integer(value) for value in present)
    )

def boundary_reason(values: dict[str, Any]) -> str | None:
    combined = " | ".join(
        normalized(value)
        for value in values.values()
        if value is not None
    )

    if "итого по акту в разрезе объекта подобъектов" in combined:
        return "summary_block"

    if "расшифровка подписи" in combined:
        return "signature_block"

    name = normalized(values.get("name"))

    if name == "должность":
        return "signature_block"

    return None

def build_ks2_dataframe(
    polars: Any,
    worksheet: Any,
    only_detailed: bool,
) -> tuple[Any, dict[str, Any]]:
    """Извлекает КС-2 в память и возвращает типизированный Polars DataFrame."""
    mapping, header_last_row, diagnostics = find_ks2_columns(worksheet)

    max_selected_column = max(mapping.values())
    first_candidate_row = header_last_row + 1

    rows_scanned = 0
    skipped_before_start = 0
    skipped_without_name = 0
    skipped_technical = 0
    skipped_not_detailed = 0

    table_started = False
    start_excel_row: int | None = None
    stop_excel_row: int | None = None
    stop_order_value: Any = None
    last_numeric_order: int | None = None
    first_written_excel_row: int | None = None
    last_written_excel_row: int | None = None
    data: list[dict[str, Any]] = []

    for excel_row, row in enumerate(
        worksheet.iter_rows(
            min_row=first_candidate_row,
            max_col=max_selected_column,
            values_only=True,
        ),
        start=first_candidate_row,
    ):
        rows_scanned += 1

        values = {
            key: (
                row[column_number - 1]
                if column_number - 1 < len(row)
                else None
            )
            for key, column_number in mapping.items()
        }

        if is_technical_numbering_row(values):
            skipped_technical += 1
            continue

        order_number = positive_integer(values["order"])

        if not table_started:
            if order_number != 1:
                skipped_before_start += 1
                continue

            table_started = True
            start_excel_row = excel_row

        elif order_number is None:
            stop_excel_row = excel_row
            stop_order_value = values["order"]
            break

        last_numeric_order = order_number
        name = clean_text(values["name"])

        if not name:
            skipped_without_name += 1
            continue

        unit = clean_text(values["unit"])
        quantity = to_float(values["quantity"])
        unit_price = to_float(values["unit_price"])
        cost = to_float(values["cost"])

        if only_detailed and not any(
            value is not None
            for value in (unit, quantity, unit_price, cost)
        ):
            skipped_not_detailed += 1
            continue

        data.append(
            {
                TARGET_HEADERS[0]: name,
                TARGET_HEADERS[1]: unit,
                TARGET_HEADERS[2]: quantity,
                TARGET_HEADERS[3]: unit_price,
                TARGET_HEADERS[4]: cost,
            }
        )

        if first_written_excel_row is None:
            first_written_excel_row = excel_row
        last_written_excel_row = excel_row

    if not table_started:
        raise ValueError(
            "Не найдена первая строка данных КС-2: "
            "в колонке «по порядку» отсутствует начальное значение 1."
        )

    if not data:
        raise ValueError("После очистки на листе КС-2 не осталось строк.")

    schema = {
        TARGET_HEADERS[0]: polars.String,
        TARGET_HEADERS[1]: polars.String,
        TARGET_HEADERS[2]: polars.Float64,
        TARGET_HEADERS[3]: polars.Float64,
        TARGET_HEADERS[4]: polars.Float64,
    }
    dataframe = polars.DataFrame(data, schema=schema, strict=False)

    metadata = {
        "mode": "ks2_ordinal_bounded_view",
        "header_detection": diagnostics,
        "ordinal_excel_column": mapping["order"],
        "header_last_excel_row": header_last_row,
        "first_candidate_excel_row": first_candidate_row,
        "table_start_excel_row": start_excel_row,
        "first_written_excel_row": first_written_excel_row,
        "last_written_excel_row": last_written_excel_row,
        "last_numeric_order": last_numeric_order,
        "stop_excel_row": stop_excel_row,
        "stop_order_value": stop_order_value,
        "stop_reason": "first_non_numeric_ordinal",
        "rows_scanned": rows_scanned,
        "written_rows": dataframe.height,
        "skipped_before_start": skipped_before_start,
        "skipped_technical_rows": skipped_technical,
        "skipped_rows_without_name": skipped_without_name,
        "skipped_not_detailed_rows": skipped_not_detailed,
        "output_columns": TARGET_HEADERS,
        "column_types": {
            TARGET_HEADERS[0]: "text",
            TARGET_HEADERS[1]: "text",
            TARGET_HEADERS[2]: "float64",
            TARGET_HEADERS[3]: "float64",
            TARGET_HEADERS[4]: "float64",
        },
        "numeric_rounding": None,
    }
    return dataframe, metadata

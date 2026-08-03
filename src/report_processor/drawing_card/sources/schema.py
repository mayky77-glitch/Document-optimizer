"""Logical schema detection for construction worksheets.

The detector never trusts a header label alone.  Quantity and total-cost columns
are checked against sampled formulas and cached values so a cost-like helper
column cannot silently be used as a physical quantity column.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from decimal import Decimal, InvalidOperation

from report_processor.hierarchy import is_ancestor_position, parse_position_code

from ..models import SourceSchema
from ..statuses import Status
from .normalization import normalize_text
from .readers import WorkbookReader, value_at

_DRAWING_ALIASES = (
    "шифр чертежа",
    "шифр рд",
    "шифр рабочей документации",
    "код чертежа",
    "номер чертежа",
    "обозначение чертежа",
    "чертеж",
)
_DOCUMENT_INDEX_ALIASES = ("индекс документа", "шифр документа", "номер документа")
_POSITION_ALIASES = (
    "номер позиции",
    "позиция",
    "номер п п",
    "номер по порядку",
    "порядковый номер",
)
_WORK_ALIASES = (
    "наименование этапа выполнения работ",
    "наименование этапа работ",
    "наименование работ и затрат",
    "наименование работ",
    "вид работ",
    "этап работ",
)
_UNIT_ALIASES = ("ед. изм", "ед изм", "единица измерения", "единица")
_QUANTITY_TOKENS = ("колич", "объем", "объём", "кол-во")
_UNIT_PRICE_TOKENS = ("цена за единицу", "стоимость за единицу")
_TOTAL_COST_TOKENS = ("общая стоимость", "стоимость работ всего")
_CONTRACT_COST_BLOCK = "стоимость по договору"
_PERFORMED_BLOCK_ALIASES = (
    "выполнено за весь период строительства",
    "выполнено за весь период",
)


def _normalize_header(value: object) -> str:
    return normalize_text(None if value is None else str(value))


def _forward_fill(values: list[str]) -> list[str]:
    result: list[str] = []
    current = ""
    for value in values:
        if value:
            current = value
        result.append(current)
    return result


def _compose_headers(rows: list[tuple[object, ...]], start: int, end: int) -> dict[int, str]:
    """Compose logical headers from up to five physical rows.

    Parent layers are forward-filled because merged headers store text only in
    the top-left cell.  The last (leaf) row is deliberately *not* forward-filled:
    a blank leaf is a real blank, and filling it caused a neighbouring
    ``Общая стоимость`` label to leak into a ``Количество`` column in the 0907
    KС-6 workbook.
    """

    width = max((len(row) for row in rows), default=0)
    layers: list[list[str]] = []
    for row_index in range(start, end + 1):
        raw = [
            _normalize_header(rows[row_index][column]) if column < len(rows[row_index]) else ""
            for column in range(width)
        ]
        layers.append(raw if row_index == end else _forward_fill(raw))
    headers: dict[int, str] = {}
    for column in range(width):
        parts: list[str] = []
        for layer in layers:
            value = layer[column]
            if value and (not parts or parts[-1] != value):
                parts.append(value)
        headers[column + 1] = " ".join(parts)
    return headers


def _contains_alias(header: str, aliases: Iterable[str]) -> bool:
    return any(alias in header for alias in aliases)


def _remaining_quantity_score(header: str) -> int:
    if "остат" not in header and "осталось выполнить" not in header:
        return 0
    if any(token in header for token in _QUANTITY_TOKENS):
        return 8
    return 0


def _remaining_cost_score(header: str) -> int:
    if "остат" not in header and "осталось выполнить" not in header:
        return 0
    if any(token in header for token in _UNIT_PRICE_TOKENS):
        return 0
    if any(token in header for token in _TOTAL_COST_TOKENS) or "остаток стоимости" in header:
        return 9
    if "стоимость по договору" in header:
        return 7
    return 0


def _block_metric_score(header: str, block_aliases: tuple[str, ...], *, quantity: bool) -> int:
    """Score an explicit leaf metric under one multi-row header block."""
    block = next((alias for alias in block_aliases if alias in header), None)
    if block is None:
        return 0
    leaf = header.replace(block, " ").strip()
    if quantity:
        return 20 if any(token in leaf for token in _QUANTITY_TOKENS) else 0
    if "единиц" in leaf or "цен" in leaf:
        return 0
    return 20 if "стоим" in leaf or "сумм" in leaf else 0


def _is_unit_price_header(header: str) -> bool:
    return any(token in header for token in _UNIT_PRICE_TOKENS) or "цен" in header


def _is_exact_contract_cost_header(header: str) -> bool:
    compact = header.replace(",", "").replace(".", "").strip()
    return compact in {
        _CONTRACT_COST_BLOCK,
        f"{_CONTRACT_COST_BLOCK} руб",
        f"{_CONTRACT_COST_BLOCK} рублей",
    }


def _resolve_contract_metrics(headers: dict[int, str]) -> tuple[dict[str, int], list[str]]:
    """Resolve contract triplets where volume sits left of the cost block."""
    cost_columns = sorted(
        column
        for column, header in headers.items()
        if _block_metric_score(header, (_CONTRACT_COST_BLOCK,), quantity=False)
        or (
            _is_exact_contract_cost_header(header)
            and _is_unit_price_header(headers.get(column - 1, ""))
        )
    )
    candidates: list[tuple[int, int]] = []
    for cost_column in cost_columns:
        quantities = [
            column
            for column in range(max(1, cost_column - 6), cost_column)
            if any(token in headers.get(column, "") for token in _QUANTITY_TOKENS)
            and any(
                _is_unit_price_header(headers.get(price_column, ""))
                for price_column in range(column + 1, cost_column)
            )
        ]
        if quantities:
            candidates.append((max(quantities), cost_column))
    if not candidates:
        return {}, []
    quantity_column, cost_column = candidates[0]
    warnings: list[str] = []
    if len(candidates) > 1:
        warnings.append(f"AMBIGUOUS_COLUMN:contract_total_cost:{cost_column},{candidates[1][1]}")
        warnings.append(f"AMBIGUOUS_COLUMN:contract_quantity:{quantity_column},{candidates[1][0]}")
    return {
        "contract_quantity": quantity_column,
        "contract_total_cost": cost_column,
    }, warnings


def _resolve_block_metrics(
    headers: dict[int, str],
    *,
    prefix: str,
    block_aliases: tuple[str, ...],
) -> tuple[dict[str, int], list[str]]:
    """Resolve quantity/cost leaves, keeping duplicate physical blocks deterministic."""
    resolved: dict[str, int] = {}
    warnings: list[str] = []
    for field, quantity in (("quantity", True), ("total_cost", False)):
        ranked = sorted(
            (
                (score, column)
                for column, header in headers.items()
                if (score := _block_metric_score(header, block_aliases, quantity=quantity))
            ),
            key=lambda item: (-item[0], item[1]),
        )
        if not ranked:
            continue
        resolved[f"{prefix}_{field}"] = ranked[0][1]
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            warnings.append(f"AMBIGUOUS_COLUMN:{prefix}_{field}:{ranked[0][1]},{ranked[1][1]}")
    return resolved, warnings


def _resolve_columns(headers: dict[int, str]) -> tuple[dict[str, int], list[str]]:
    resolved: dict[str, int] = {}
    warnings: list[str] = []
    candidates: dict[str, list[tuple[int, int]]] = {
        "drawing_code": [],
        "document_index": [],
        "position_code": [],
        "work_name": [],
        "unit": [],
        "remaining_quantity": [],
        "remaining_total_cost": [],
    }
    for column, header in headers.items():
        if _contains_alias(header, _DRAWING_ALIASES):
            candidates["drawing_code"].append((10, column))
        if _contains_alias(header, _DOCUMENT_INDEX_ALIASES):
            candidates["document_index"].append((9, column))
        if _contains_alias(header, _POSITION_ALIASES):
            candidates["position_code"].append((10, column))
        if _contains_alias(header, _WORK_ALIASES):
            candidates["work_name"].append((10, column))
        if _contains_alias(header, _UNIT_ALIASES):
            candidates["unit"].append((8, column))
        quantity_score = _remaining_quantity_score(header)
        if quantity_score:
            candidates["remaining_quantity"].append((quantity_score, column))
        cost_score = _remaining_cost_score(header)
        if cost_score:
            candidates["remaining_total_cost"].append((cost_score, column))
    for field, field_candidates in candidates.items():
        if not field_candidates:
            continue
        ranked = sorted(field_candidates, key=lambda item: (-item[0], item[1]))
        resolved[field] = ranked[0][1]
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            warnings.append(f"AMBIGUOUS_COLUMN:{field}:{ranked[0][1]},{ranked[1][1]}")
    if resolved.get("remaining_quantity") == resolved.get("remaining_total_cost"):
        column = resolved.pop("remaining_quantity", None)
        warnings.append(f"SAME_COLUMN_FOR_QUANTITY_AND_COST:{column}")
    contract_columns, contract_warnings = _resolve_contract_metrics(headers)
    performed_columns, performed_warnings = _resolve_block_metrics(
        headers,
        prefix="performed",
        block_aliases=_PERFORMED_BLOCK_ALIASES,
    )
    resolved.update(contract_columns)
    resolved.update(performed_columns)
    warnings.extend(contract_warnings)
    warnings.extend(performed_warnings)
    return resolved, warnings


def _content_position_column(
    columns: dict[str, int],
    headers: dict[int, str],
    rows: Sequence[tuple[object, ...]],
    *,
    start: int,
) -> tuple[int | None, str | None]:
    """Recover a non-standard position column only on strong, unique hierarchy evidence."""
    if "position_code" in columns:
        return columns["position_code"], None
    excluded = ("единиц", "колич", "объем", "стоим", "цен", "работ", "чертеж")
    ranked: list[tuple[int, int]] = []
    for column, header in headers.items():
        if any(token in header for token in excluded):
            continue
        parsed = [parse_position_code(value_at(row, column)) for row in rows[start : start + 32]]
        values = [value for value in parsed if value is not None]
        parent_pairs = sum(
            1 for parent in values for child in values if is_ancestor_position(parent, child)
        )
        if len(values) >= 4 and parent_pairs >= 2 and len(values) / 32 >= 0.12:
            ranked.append((len(values) + parent_pairs * 3, column))
    ranked.sort(reverse=True)
    if not ranked:
        return None, None
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None, "AMBIGUOUS_POSITION_COLUMN_CONTENT"
    return ranked[0][1], "POSITION_COLUMN_FROM_CONTENT"


def _schema_score(columns: dict[str, int]) -> int:
    score = sum(2 for key in ("drawing_code", "work_name", "unit") if key in columns)
    score += sum(4 for key in ("remaining_quantity", "remaining_total_cost") if key in columns)
    score += sum(
        1
        for key in (
            "contract_quantity",
            "contract_total_cost",
            "performed_quantity",
            "performed_total_cost",
        )
        if key in columns
    )
    return score


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).replace("\u00a0", " ").replace(" ", "").replace(",", ".").strip()
    if not text or text.startswith("="):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _formula(value: object) -> str:
    return value if isinstance(value, str) and value.startswith("=") else ""


def _metric_pair_stats(
    formula_rows: Sequence[tuple[object, ...]],
    cached_rows: Sequence[tuple[object, ...]],
    quantity_column: int,
    cost_column: int,
    *,
    start_index: int,
) -> dict[str, float | int]:
    comparable = 0
    equal_nonzero = 0
    quantity_nonzero = 0
    subtraction_formulas = 0
    formula_count = 0
    for formula_row, cached_row in zip(
        formula_rows[start_index:], cached_rows[start_index:], strict=False
    ):
        quantity = _decimal(value_at(cached_row, quantity_column))
        cost = _decimal(value_at(cached_row, cost_column))
        formula = _formula(value_at(formula_row, quantity_column))
        if formula:
            formula_count += 1
            if "-" in formula:
                subtraction_formulas += 1
        if quantity not in (None, Decimal(0)):
            quantity_nonzero += 1
        if quantity in (None, Decimal(0)) or cost in (None, Decimal(0)):
            continue
        comparable += 1
        tolerance = max(Decimal("0.000001"), abs(cost) * Decimal("0.000000001"))
        if abs(quantity - cost) <= tolerance:
            equal_nonzero += 1
    return {
        "comparable": comparable,
        "equal_nonzero": equal_nonzero,
        "equal_ratio": equal_nonzero / comparable if comparable else 0.0,
        "quantity_nonzero": quantity_nonzero,
        "formula_count": formula_count,
        "subtraction_formulas": subtraction_formulas,
        "subtraction_ratio": subtraction_formulas / formula_count if formula_count else 0.0,
    }


def _candidate_triplets(headers: dict[int, str]) -> tuple[tuple[int, int, int], ...]:
    candidates: list[tuple[int, int, int]] = []
    max_column = max(headers, default=0)
    for quantity_column in range(1, max_column - 1):
        quantity_header = headers.get(quantity_column, "")
        unit_price_header = headers.get(quantity_column + 1, "")
        cost_header = headers.get(quantity_column + 2, "")
        has_quantity = any(token in quantity_header for token in _QUANTITY_TOKENS)
        has_unit_price = any(token in unit_price_header for token in _UNIT_PRICE_TOKENS)
        has_total_cost = any(token in cost_header for token in _TOTAL_COST_TOKENS)
        if has_quantity and has_unit_price and has_total_cost:
            candidates.append((quantity_column, quantity_column + 1, quantity_column + 2))
    return tuple(candidates)


def _triplet_score(
    formula_rows: Sequence[tuple[object, ...]],
    cached_rows: Sequence[tuple[object, ...]],
    quantity_column: int,
    unit_price_column: int,
    cost_column: int,
    *,
    start_index: int,
) -> tuple[float, dict[str, float | int]]:
    relation_samples = 0
    relation_matches = 0
    formula_count = 0
    subtraction_formulas = 0
    equal_nonzero = 0
    comparable = 0
    for formula_row, cached_row in zip(
        formula_rows[start_index:], cached_rows[start_index:], strict=False
    ):
        quantity = _decimal(value_at(cached_row, quantity_column))
        unit_price = _decimal(value_at(cached_row, unit_price_column))
        cost = _decimal(value_at(cached_row, cost_column))
        q_formula = _formula(value_at(formula_row, quantity_column))
        if q_formula:
            formula_count += 1
            if "-" in q_formula:
                subtraction_formulas += 1
        if quantity not in (None, Decimal(0)) and cost not in (None, Decimal(0)):
            comparable += 1
            if abs(quantity - cost) <= max(Decimal("0.000001"), abs(cost) * Decimal("1e-9")):
                equal_nonzero += 1
        if quantity in (None, Decimal(0)) or unit_price in (None, Decimal(0)) or cost is None:
            continue
        relation_samples += 1
        expected = quantity * unit_price
        tolerance = max(Decimal("1.01"), abs(cost) * Decimal("0.002"))
        if abs(expected - cost) <= tolerance:
            relation_matches += 1
    relation_ratio = relation_matches / relation_samples if relation_samples else 0.0
    subtraction_ratio = subtraction_formulas / formula_count if formula_count else 0.0
    equal_ratio = equal_nonzero / comparable if comparable else 0.0
    score = relation_ratio * 6.0 + subtraction_ratio * 4.0 + min(relation_samples, 10) * 0.1
    score -= equal_ratio * 5.0
    if formula_count == 0:
        score -= 3.0
    stats: dict[str, float | int] = {
        "relation_samples": relation_samples,
        "relation_matches": relation_matches,
        "relation_ratio": relation_ratio,
        "formula_count": formula_count,
        "subtraction_formulas": subtraction_formulas,
        "subtraction_ratio": subtraction_ratio,
        "equal_ratio": equal_ratio,
    }
    return score, stats


def _validate_metric_columns(
    columns: dict[str, int],
    headers: dict[int, str],
    formula_rows: Sequence[tuple[object, ...]],
    cached_rows: Sequence[tuple[object, ...]],
    *,
    data_start_index: int,
) -> tuple[dict[str, int], list[str]]:
    resolved = dict(columns)
    warnings: list[str] = []
    quantity_column = resolved.get("remaining_quantity")
    cost_column = resolved.get("remaining_total_cost")
    if quantity_column is None or cost_column is None:
        return resolved, warnings

    current = _metric_pair_stats(
        formula_rows,
        cached_rows,
        quantity_column,
        cost_column,
        start_index=data_start_index,
    )
    suspicious = quantity_column == cost_column or (
        int(current["comparable"]) >= 3
        and float(current["equal_ratio"]) >= 0.45
        and int(current["equal_nonzero"]) >= 3
    )
    if not suspicious:
        return resolved, warnings

    warnings.append(
        "SUSPICIOUS_QUANTITY_COST_PAIR:"
        f"{quantity_column},{cost_column}:"
        f"equal_nonzero={current['equal_nonzero']}/{current['comparable']}"
    )
    ranked: list[tuple[float, tuple[int, int, int], dict[str, float | int]]] = []
    for triplet in _candidate_triplets(headers):
        q_col, price_col, c_col = triplet
        if (q_col, c_col) == (quantity_column, cost_column):
            continue
        score, stats = _triplet_score(
            formula_rows,
            cached_rows,
            q_col,
            price_col,
            c_col,
            start_index=data_start_index,
        )
        ranked.append((score, triplet, stats))
    ranked.sort(key=lambda item: (-item[0], item[1][0]))
    if ranked:
        score, (q_col, _price_col, c_col), stats = ranked[0]
        strong = (
            score >= 5.0
            and int(stats["relation_samples"]) >= 3
            and float(stats["relation_ratio"]) >= 0.70
            and int(stats["subtraction_formulas"]) >= 2
        )
        if strong:
            resolved["remaining_quantity"] = q_col
            resolved["remaining_total_cost"] = c_col
            warnings.append(
                "METRIC_COLUMNS_REPLACED:"
                f"remaining_quantity:{quantity_column}->{q_col};"
                f"remaining_total_cost:{cost_column}->{c_col};"
                f"score={score:.3f}"
            )
            return resolved, warnings

    # Failing closed is safer than writing monetary values as tonnes/metres.
    resolved.pop("remaining_quantity", None)
    warnings.append(f"UNTRUSTED_QUANTITY_COLUMN_REMOVED:{quantity_column}")
    return resolved, warnings


def detect_sheet_schema(
    reader: WorkbookReader,
    sheet_name: str,
    *,
    max_scan_rows: int = 80,
    max_scan_columns: int = 256,
) -> SourceSchema:
    scanned_pairs = list(
        reader.iter_rows(sheet_name, min_row=1, max_row=max_scan_rows, max_col=max_scan_columns)
    )
    formula_rows = [formula for formula, _cached in scanned_pairs]
    cached_rows = [cached for _formula, cached in scanned_pairs]
    if not formula_rows:
        return SourceSchema(sheet_name, 1, 1, 2, {}, {}, 0.0, Status.MISSING_REQUIRED_COLUMNS)
    anchors: list[int] = []
    for index, row in enumerate(formula_rows):
        text = " | ".join(_normalize_header(value) for value in row if value is not None)
        if _contains_alias(text, _DRAWING_ALIASES) and _contains_alias(text, _WORK_ALIASES):
            anchors.append(index)
    if not anchors:
        return SourceSchema(sheet_name, 1, 1, 2, {}, {}, 0.0, Status.MISSING_REQUIRED_COLUMNS)
    best: tuple[int, int, int, dict[str, int], dict[int, str], list[str]] | None = None
    for anchor in anchors:
        for end in range(anchor, min(anchor + 4, len(formula_rows) - 1) + 1):
            headers = _compose_headers(formula_rows, anchor, end)
            columns, warnings = _resolve_columns(headers)
            score = _schema_score(columns)
            candidate = (score, -(end - anchor), -anchor, columns, headers, warnings)
            if best is None or candidate[:3] > best[:3]:
                best = candidate
    assert best is not None
    score, neg_span, neg_anchor, columns, headers, warnings = best
    anchor = -neg_anchor
    end = anchor - neg_span
    columns, metric_warnings = _validate_metric_columns(
        columns,
        headers,
        formula_rows,
        cached_rows,
        data_start_index=end + 1,
    )
    warnings.extend(metric_warnings)
    position_column, position_warning = _content_position_column(
        columns, headers, cached_rows, start=end + 1
    )
    if position_column is not None:
        columns["position_code"] = position_column
    if position_warning:
        warnings.append(position_warning)
    required = {"drawing_code", "work_name", "unit", "remaining_quantity", "remaining_total_cost"}
    missing = sorted(required - columns.keys())
    status = Status.OK.value if not missing else Status.MISSING_REQUIRED_COLUMNS.value
    if missing:
        warnings.append("MISSING:" + ",".join(missing))
    confidence = min(1.0, _schema_score(columns) / 14)
    return SourceSchema(
        sheet_name=sheet_name,
        header_start_row=anchor + 1,
        header_end_row=end + 1,
        data_start_row=end + 2,
        columns=columns,
        logical_headers=headers,
        confidence=confidence,
        status=status,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def detect_workbook_schemas(reader: WorkbookReader) -> list[SourceSchema]:
    schemas = [detect_sheet_schema(reader, name) for name in reader.list_sheets()]
    preferred = {"виср": 4, "кс-6а": 3, "кс-6": 3, "свод": 2, "кс-2": 1}
    ranked: list[SourceSchema] = []
    for schema in schemas:
        name_score = max(
            (weight for token, weight in preferred.items() if token in schema.sheet_name.lower()),
            default=0,
        )
        ranked.append(replace(schema, confidence=min(1.0, schema.confidence + name_score * 0.01)))
    return sorted(ranked, key=lambda item: (-item.confidence, item.sheet_name.lower()))


def select_usable_schemas(schemas: list[SourceSchema]) -> tuple[SourceSchema, ...]:
    usable = [
        schema
        for schema in schemas
        if {"drawing_code", "work_name", "unit"}.issubset(schema.columns)
        and ("remaining_quantity" in schema.columns or "remaining_total_cost" in schema.columns)
    ]
    if not usable:
        return ()
    top = usable[0].confidence
    selected = [schema for schema in usable if schema.confidence >= max(0.7, top - 0.05)]
    return tuple(selected)

"""Bounded, path-free facts and groups for reconciliation review cards."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from decimal import Decimal



def manual_review_groups(
    discrepancies: Sequence[Mapping[str, object]],
    decisions: Sequence[Mapping[str, object]],
    *,
    include_ids: bool = False,
) -> list[dict[str, object]]:
    decided = {
        _text(item.get("discrepancy_id"))
        for item in decisions
        if _text(item.get("decision")) in {"approve", "reject"}
    }
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = {}
    for item in discrepancies:
        if _text(item.get("severity")) != "manual_review":
            continue
        discrepancy_id = _text(item.get("discrepancy_id"), 200)
        if not discrepancy_id or discrepancy_id in decided:
            continue
        code = _text(item.get("code"), 120) or "MANUAL_REVIEW"
        message = _text(item.get("message")) or "Требуется ручная проверка."
        context = public_context(item.get("context"))
        title = _text(context.get("work_name")) or "Нужна ручная проверка"
        grouped.setdefault((code, message, title), []).append(item)
    result = []
    for (code, message, title), items in sorted(grouped.items()):
        record: dict[str, object] = {
            "group_id": controlled_id("manual-review-group", code, message, title),
            "code": code,
            "title": title,
            "message": message,
            "count": len(items),
            "members": bounded_members(items),
            "context": group_context(items),
        }
        if include_ids:
            record["discrepancy_ids"] = sorted(_text(item.get("discrepancy_id"), 200) for item in items)
        result.append(record)
    return result


def suggestion_review_groups(
    suggestions: Sequence[Mapping[str, object]], decisions: Sequence[Mapping[str, object]]
) -> list[dict[str, object]]:
    decided = {
        _text(item.get("suggestion_id"))
        for item in decisions
        if _text(item.get("decision")) in {"fit", "not_fit"}
    }
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for item in suggestions:
        suggestion_id, target_ref = _text(item.get("suggestion_id"), 200), _text(item.get("target_ref"), 200)
        if item.get("requires_manual_review") is True and suggestion_id and target_ref and suggestion_id not in decided:
            grouped.setdefault(target_ref, []).append(item)
    return [
        {
            "group_id": controlled_id("suggestion-review-group", target_ref),
            "title": _text(items[0].get("target_label")) or "Целевой этап",
            "count": len(items),
            "candidates": [
                {
                    "suggestion_id": _text(item.get("suggestion_id"), 200),
                    "label": _text(item.get("candidate_label")) or "Предложенный этап",
                    "source_unit": _text(public_context(item.get("context")).get("source_unit")),
                    "confidence": finite_float(item.get("score", 0.0)),
                }
                for item in items
            ],
            "context": public_context(items[0].get("context")),
        }
        for target_ref, items in sorted(grouped.items())
    ]


def issue_contexts(artifacts: Mapping[str, object]) -> dict[str, dict[str, object]]:
    sources = {_text(getattr(row, "source_row_id", ""), 200): row for row in tuple(getattr(artifacts.get("normalized"), "rows", ()) or ())}
    matches = tuple(artifacts.get("matches", ()) or ())
    match_ids = {_text(getattr(item, "result_id", ""), 200): item for item in matches}
    target_ids = {_text(getattr(item, "target_row_id", ""), 200): item for item in matches}
    calculations = {_text(getattr(item, "calculation_id", ""), 200): item for item in tuple(artifacts.get("calculations", ()) or ())}
    report = artifacts.get("quality_report")
    issues = (*tuple(getattr(report, "issues", ()) or ()), *tuple(artifacts.get("hierarchy_issues", ()) or ()))
    result = {}
    for issue in issues:
        match = match_ids.get(_text(getattr(issue, "match_result_id", ""), 200)) or target_ids.get(_text(getattr(issue, "target_row_id", ""), 200))
        calculation = calculations.get(_text(getattr(issue, "calculation_id", ""), 200))
        rows = [sources[row_id] for row_id in tuple(getattr(issue, "source_row_ids", ()) or ()) if row_id in sources]
        result[_text(getattr(issue, "issue_id", ""), 200)] = context_record(rows, match, calculation)
    return result


def suggestion_contexts(artifacts: Mapping[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    sources = {_text(getattr(row, "source_row_id", ""), 200): row for row in tuple(getattr(artifacts.get("normalized"), "rows", ()) or ())}
    matches = {_text(getattr(item, "result_id", ""), 200): item for item in tuple(artifacts.get("matches", ()) or ())}
    calculations = {_text(getattr(item, "match_result_id", ""), 200): item for item in tuple(artifacts.get("calculations", ()) or ())}
    result = {}
    for suggestion in tuple(artifacts.get("stage_relation_suggestions", ()) or ()):
        target_id = _text(getattr(suggestion, "target_identity", ""), 200)
        for candidate in tuple(getattr(suggestion, "candidates", ()) or ()):
            source_id = _text(getattr(candidate, "source_identity", ""), 200)
            result[target_id, source_id] = context_record([sources[source_id]] if source_id in sources else [], matches.get(target_id), calculations.get(target_id))
    return result


def context_record(source_rows: Sequence[object], match: object, calculation: object) -> dict[str, object]:
    source, target = (source_rows[0] if source_rows else None), (getattr(match, "target_row", None) or getattr(calculation, "target_row", None))
    values = {
        "work_name": _text(
            getattr(source, "work_name", None)
            or getattr(target, "stage", None)
            or getattr(target, "work_name", None)
        ),
        "source_unit": _text(getattr(source, "unit", None)),
        "target_unit": _text(getattr(target, "unit", None)),
        "proposed_match": _text(getattr(target, "stage", None) or getattr(target, "work_name", None)),
    }
    explanation = tuple(getattr(match, "explanation", ()) or ())
    if explanation:
        values["reason"] = _text(explanation[0])
    cost = safe_number(getattr(calculation, "cost", None))
    if cost is not None:
        values["aggregate_cost"] = cost
    candidates = tuple(getattr(match, "candidates", ()) or ())
    candidate = getattr(match, "selected_candidate", None) or (candidates[0] if candidates else None)
    confidence = safe_number(getattr(candidate, "confidence", None))
    if confidence is not None:
        values["confidence"] = confidence
    source_value = getattr(source, "source_row", None)
    quantity = safe_number(
        getattr(source_value, "remaining_quantity", None)
        or getattr(source_value, "period_quantity", None)
    )
    if quantity is not None:
        values["quantity"] = quantity
    source_cost = safe_number(
        getattr(source_value, "total_cost", None) or getattr(source_value, "period_cost", None)
    )
    if source_cost is not None:
        values["cost"] = source_cost
    return public_context(values)


def public_context(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    allowed = (
        "work_name",
        "source_unit",
        "target_unit",
        "proposed_match",
        "confidence",
        "reason",
        "aggregate_cost",
        "quantity",
        "cost",
    )
    result = {}
    for key in allowed:
        item = safe_number(value.get(key)) if key in {"aggregate_cost", "confidence", "quantity", "cost"} else _text(value.get(key))
        if item is not None and item != "":
            result[key] = item
    return result


def bounded_members(items: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "title": _text(public_context(item.get("context")).get("work_name")) or "Позиция без наименования",
            "context": public_context(item.get("context")),
        }
        for item in items
    ]


def group_context(items: Sequence[Mapping[str, object]]) -> dict[str, object]:
    contexts = [public_context(item.get("context")) for item in items]
    result = dict(next((item for item in contexts if item), {}))
    costs = [item["aggregate_cost"] for item in contexts if "aggregate_cost" in item]
    if costs:
        result["aggregate_cost"] = round(sum(float(value) for value in costs), 2)
    return result


def safe_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value == value and abs(value) != float("inf") else None


def finite_float(value: object) -> float:
    return safe_number(value) or 0.0


def controlled_id(*parts: object) -> str:
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8", "replace")).hexdigest()[:24]


def _text(value: object, limit: int = 500) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]

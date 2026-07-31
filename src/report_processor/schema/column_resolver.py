"""Resolve physical headers to logical columns with explicit ambiguity handling."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace

from report_processor.hierarchy import is_ancestor_position, parse_position_code
from report_processor.schema.models import (
    ColumnAliasRule,
    ColumnCandidate,
    ColumnResolution,
    ComposedHeader,
    LogicalColumn,
    SheetType,
)
from report_processor.schema.text_normalization import normalize_header_text

_CONTEXT_REQUIRED = {
    LogicalColumn.CONTRACT_QUANTITY,
    LogicalColumn.CURRENT_PERIOD_QUANTITY,
    LogicalColumn.CUMULATIVE_QUANTITY,
    LogicalColumn.REMAINING_QUANTITY,
    LogicalColumn.CURRENT_PERIOD_COST,
    LogicalColumn.CUMULATIVE_COST,
    LogicalColumn.TOTAL_COST,
}
_MONTH_OR_YEAR_RE = re.compile(
    r"\b(?:январ|феврал|март|апрел|ма[йя]|июн|июл|август|"
    r"сентябр|октябр|ноябр|декабр)\w*\b|\b20\d{2}\b"
)


def _contains_token(text: str, token: str) -> bool:
    normalized = normalize_header_text(token)
    if " " in normalized:
        return normalized in text
    words = text.split()
    if len(normalized) >= 4:
        return any(word == normalized or word.startswith(normalized) for word in words)
    return normalized in words


def _score_rule(header: ComposedHeader, rule: ColumnAliasRule) -> ColumnCandidate | None:
    text = header.normalized_text
    if not text:
        return None
    aliases = tuple(normalize_header_text(alias) for alias in rule.exact_aliases)
    required = tuple(token for token in rule.required_tokens if _contains_token(text, token))
    optional = tuple(token for token in rule.optional_tokens if _contains_token(text, token))
    forbidden = tuple(token for token in rule.forbidden_tokens if _contains_token(text, token))

    exact = text in aliases
    if not exact and len(required) != len(rule.required_tokens):
        return None
    if exact:
        score = 1.0
    else:
        contextual_optional = optional
        if (
            rule.logical_column
            in {LogicalColumn.CURRENT_PERIOD_QUANTITY, LogicalColumn.CURRENT_PERIOD_COST}
            and _MONTH_OR_YEAR_RE.search(text)
            and "за" in text.split()
        ):
            contextual_optional = (*optional, "reporting_period")
        optional_ratio = len(contextual_optional) / max(len(rule.optional_tokens), 1)
        score = 0.58 + optional_ratio * 0.25 + min(rule.priority / 1000, 0.1)
        if rule.logical_column in _CONTEXT_REQUIRED and not contextual_optional:
            score -= 0.24
    if forbidden:
        score -= min(0.20 + len(forbidden) * 0.16, 0.62)
    score = min(max(score, 0.0), 1.0)
    return ColumnCandidate(
        column_index=header.column_index,
        column_letter=header.column_letter,
        header_text=header.raw_text,
        score=round(score, 4),
        matched_tokens=tuple(dict.fromkeys((*required, *optional))),
        rejected_tokens=forbidden,
    )


def _resolution_for_logical(
    logical: LogicalColumn,
    headers: tuple[ComposedHeader, ...],
    rules: tuple[ColumnAliasRule, ...],
) -> ColumnResolution:
    candidates: list[tuple[ColumnCandidate, ColumnAliasRule]] = []
    for rule in rules:
        for header in headers:
            candidate = _score_rule(header, rule)
            if candidate is not None and candidate.score >= 0.45:
                candidates.append((candidate, rule))
    candidates.sort(key=lambda item: (-item[0].score, item[0].column_index, -item[1].priority))
    alternatives = tuple(item[0] for item in candidates[:5])
    if not candidates or candidates[0][0].score < 0.64:
        return ColumnResolution(
            logical,
            None,
            None,
            None,
            candidates[0][0].score if candidates else 0.0,
            None,
            alternatives,
            "COLUMN_NOT_FOUND",
        )
    top_candidate, top_rule = candidates[0]
    competing = [
        item[0]
        for item in candidates[1:]
        if item[0].column_index != top_candidate.column_index
        and top_candidate.score - item[0].score <= 0.045
        and item[0].score >= 0.72
    ]
    if competing:
        return ColumnResolution(
            logical,
            None,
            None,
            None,
            top_candidate.score,
            f"priority={top_rule.priority}",
            alternatives,
            "AMBIGUOUS_COLUMN",
            ("EQUAL_COLUMN_CANDIDATES",),
        )
    return ColumnResolution(
        logical_column=logical,
        column_index=top_candidate.column_index,
        column_letter=top_candidate.column_letter,
        header_text=top_candidate.header_text,
        confidence=top_candidate.score,
        matched_rule=f"priority={top_rule.priority}",
        alternatives=alternatives,
        status="OK",
    )


def _resolve_physical_conflicts(
    resolutions: tuple[ColumnResolution, ...],
) -> tuple[ColumnResolution, ...]:
    by_column: dict[int, list[ColumnResolution]] = defaultdict(list)
    for resolution in resolutions:
        if resolution.status == "OK" and resolution.column_index is not None:
            by_column[resolution.column_index].append(resolution)
    replacements: dict[LogicalColumn, ColumnResolution] = {}
    for items in by_column.values():
        if len(items) < 2:
            continue
        ranked = sorted(items, key=lambda item: -item.confidence)
        winner = ranked[0]
        for item in ranked[1:]:
            if winner.confidence - item.confidence >= 0.08:
                replacements[item.logical_column] = replace(
                    item,
                    column_index=None,
                    column_letter=None,
                    header_text=None,
                    status="AMBIGUOUS_COLUMN",
                    warnings=(*item.warnings, "PHYSICAL_COLUMN_CONFLICT"),
                )
            else:
                replacements[winner.logical_column] = replace(
                    winner,
                    column_index=None,
                    column_letter=None,
                    header_text=None,
                    status="AMBIGUOUS_COLUMN",
                    warnings=(*winner.warnings, "PHYSICAL_COLUMN_CONFLICT"),
                )
                replacements[item.logical_column] = replace(
                    item,
                    column_index=None,
                    column_letter=None,
                    header_text=None,
                    status="AMBIGUOUS_COLUMN",
                    warnings=(*item.warnings, "PHYSICAL_COLUMN_CONFLICT"),
                )
    return tuple(replacements.get(item.logical_column, item) for item in resolutions)


def resolve_logical_columns(
    headers: tuple[ComposedHeader, ...],
    sheet_type: SheetType,
    aliases: tuple[ColumnAliasRule, ...],
) -> tuple[ColumnResolution, ...]:
    applicable = tuple(rule for rule in aliases if sheet_type in rule.applicable_sheet_types)
    logical_columns = sorted(
        {rule.logical_column for rule in applicable},
        key=lambda item: item.value,
    )
    resolutions = tuple(
        _resolution_for_logical(
            logical,
            headers,
            tuple(rule for rule in applicable if rule.logical_column == logical),
        )
        for logical in logical_columns
    )
    return _resolve_physical_conflicts(resolutions)


def resolve_position_column_from_content(
    headers: tuple[ComposedHeader, ...],
    sampled_values: dict[int, tuple[object, ...]],
    current: ColumnResolution,
) -> ColumnResolution:
    """Recover a variant numbering header only from strong, unique hierarchy evidence."""
    if current.status == "OK" or current.logical_column is not LogicalColumn.POSITION_CODE:
        return current
    excluded = ("единиц", "колич", "объем", "стоим", "цен", "работ", "чертеж")
    candidates: list[tuple[int, ComposedHeader]] = []
    for header in headers:
        if any(token in header.normalized_text for token in excluded):
            continue
        codes = [
            code
            for value in sampled_values.get(header.column_index, ())
            if (code := parse_position_code(value))
        ]
        pairs = sum(1 for parent in codes for child in codes if is_ancestor_position(parent, child))
        if len(codes) >= 4 and pairs >= 2:
            candidates.append((len(codes) + pairs * 3, header))
    candidates.sort(key=lambda item: (-item[0], item[1].column_index))
    if not candidates or (len(candidates) > 1 and candidates[0][0] == candidates[1][0]):
        return current
    _score, header = candidates[0]
    return ColumnResolution(
        logical_column=LogicalColumn.POSITION_CODE,
        column_index=header.column_index,
        column_letter=header.column_letter,
        header_text=header.raw_text,
        confidence=0.80,
        matched_rule="content_hierarchy",
        alternatives=(),
        status="OK",
        warnings=("POSITION_COLUMN_FROM_CONTENT",),
    )

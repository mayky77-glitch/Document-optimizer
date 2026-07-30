"""Source inspection, schema scoring and safe candidate selection."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..models import ManifestEntry, ObjectIdentityResult, SourceSchema
from ..statuses import Status
from .identity import resolve_object_identity
from .readers import materialize_entry, open_schema_reader
from .schema import detect_workbook_schemas, select_usable_schemas


@dataclass(frozen=True, slots=True)
class SourceInspection:
    entry: ManifestEntry
    object_identity: ObjectIdentityResult
    sheets: tuple[str, ...]
    schemas: tuple[SourceSchema, ...]
    usable_schemas: tuple[SourceSchema, ...]
    score: float
    status: str
    warnings: tuple[str, ...]


def inspect_source(
    entry: ManifestEntry,
    *,
    object_mapping: dict[str, str] | None = None,
    explicit_object_index: str | None = None,
) -> SourceInspection:
    materialized = materialize_entry(entry)
    reader = None
    try:
        reader = open_schema_reader(materialized.path)
        schemas = tuple(detect_workbook_schemas(reader))
        usable = select_usable_schemas(list(schemas))
        inferred_type = entry.document_type
        if inferred_type is None and usable:
            sheet_name = usable[0].sheet_name.lower()
            if "виср" in sheet_name:
                inferred_type = "visr"
            elif "кс-6" in sheet_name or "кс6" in sheet_name:
                inferred_type = "ks6a"
            elif "кс-2" in sheet_name or "кс2" in sheet_name:
                inferred_type = "ks2"
            elif "сввр" in sheet_name:
                inferred_type = "svvr"
        effective_entry = replace(entry, document_type=inferred_type)
        identity = resolve_object_identity(
            effective_entry,
            mapping=object_mapping,
            explicit_value=explicit_object_index,
        )
        warnings = list(effective_entry.warnings) + list(identity.warnings)
        if not usable:
            warnings.append(Status.MISSING_REQUIRED_COLUMNS)
        score = 0.0
        if usable:
            score += max(schema.confidence for schema in usable) * 100
            completeness = max(len(schema.columns) for schema in usable)
            score += completeness * 3
        priority = {"visr": 12, "ks6a": 10, "ks2": 6, "svvr": 5}
        score += priority.get(effective_entry.document_type or "", 0)
        if effective_entry.revision and effective_entry.revision.isdigit():
            score += min(int(effective_entry.revision), 20) * 0.01
        if effective_entry.is_copy:
            score -= 5
        if effective_entry.is_outdated:
            score -= 50
        if effective_entry.is_temporary:
            score -= 100
        status = Status.OK.value
        if identity.status != Status.OK:
            status = str(identity.status)
        elif not usable:
            status = Status.MISSING_REQUIRED_COLUMNS.value
        elif warnings:
            status = Status.WARNING.value
        return SourceInspection(
            entry=effective_entry,
            object_identity=identity,
            sheets=reader.list_sheets(),
            schemas=schemas,
            usable_schemas=usable,
            score=score,
            status=status,
            warnings=tuple(str(item) for item in warnings),
        )
    finally:
        if reader is not None:
            reader.close()
        materialized.close()


def _period_filtered_candidates(
    candidates: list[SourceInspection],
    requested_period: str | None,
) -> tuple[list[SourceInspection], dict[str, str]]:
    """Filter by an explicit period or, when omitted, the latest known period."""
    reasons: dict[str, str] = {}
    if requested_period:
        exact = [item for item in candidates if item.entry.period == requested_period]
        if exact:
            for item in candidates:
                if item not in exact:
                    reasons[item.entry.file_id] = "not_selected_other_period"
            return exact, reasons
        unknown = [item for item in candidates if item.entry.period is None]
        for item in candidates:
            if item not in unknown:
                reasons[item.entry.file_id] = "not_selected_period_mismatch"
        return unknown, reasons
    known_periods = sorted({item.entry.period for item in candidates if item.entry.period})
    if not known_periods:
        return candidates, reasons
    latest = known_periods[-1]
    selected = [item for item in candidates if item.entry.period in {latest, None}]
    for item in candidates:
        if item not in selected:
            reasons[item.entry.file_id] = "not_selected_older_period"
    return selected, reasons


def _selection_record(
    item: SourceInspection,
    decision: str,
    *,
    extra_warnings: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "file_id": item.entry.file_id,
        "logical_path": item.entry.logical_path,
        "object_index": item.object_identity.value,
        "document_type": item.entry.document_type,
        "period": item.entry.period,
        "score": item.score,
        "decision": decision,
        "warnings": list(item.warnings + extra_warnings),
    }


def select_inspections(
    inspections: list[SourceInspection],
    *,
    explicit_inputs: bool,
    requested_period: str | None,
) -> tuple[list[SourceInspection], list[dict[str, object]], list[str]]:
    selected: list[SourceInspection] = []
    records: list[dict[str, object]] = []
    warnings: list[str] = []
    eligible: list[SourceInspection] = []
    for item in inspections:
        reason = None
        if not item.usable_schemas:
            reason = "skipped_missing_required_columns"
        elif not item.object_identity.value:
            reason = "skipped_object_identity_unresolved"
        elif item.entry.is_temporary:
            reason = "skipped_temporary_file"
        elif item.entry.is_outdated:
            reason = "skipped_outdated_file"
        if reason:
            records.append(_selection_record(item, reason))
            warnings.extend(item.warnings or (reason.upper(),))
        else:
            eligible.append(item)

    if explicit_inputs:
        period_pool, period_reasons = _period_filtered_candidates(eligible, requested_period)
        for item in eligible:
            decision = period_reasons.get(item.entry.file_id, "selected_explicit_input")
            records.append(_selection_record(item, decision))
            if decision == "selected_explicit_input":
                selected.append(item)
        if not selected:
            warnings.append("NO_ELIGIBLE_SOURCES")
        return selected, records, list(dict.fromkeys(warnings))

    groups: dict[str, list[SourceInspection]] = {}
    for item in eligible:
        groups.setdefault(item.object_identity.value or "", []).append(item)

    for object_index, candidates in sorted(groups.items()):
        period_pool, period_reasons = _period_filtered_candidates(candidates, requested_period)
        for item in candidates:
            if item.entry.file_id in period_reasons:
                records.append(_selection_record(item, period_reasons[item.entry.file_id]))
        if not period_pool:
            warnings.append(f"NO_SOURCE_FOR_PERIOD:{object_index}:{requested_period}")
            continue
        noncopies = [item for item in period_pool if not item.entry.is_copy]
        pool = noncopies or period_pool
        if not noncopies and period_pool:
            warnings.append(f"{Status.ONLY_COPY_CANDIDATES}:{object_index}")
        ranked = sorted(pool, key=lambda item: (-item.score, item.entry.logical_path))
        top_score = ranked[0].score
        top = [item for item in ranked if abs(item.score - top_score) < 1e-9]
        if len(top) > 1:
            warning = f"{Status.MULTIPLE_TOP_CANDIDATES}:{object_index}"
            warnings.append(warning)
            for item in top:
                records.append(
                    _selection_record(item, "blocked_ambiguous_top", extra_warnings=(warning,))
                )
            for item in ranked[len(top) :]:
                records.append(_selection_record(item, "not_selected_lower_score"))
            continue
        winner = ranked[0]
        selected.append(winner)
        for item in ranked:
            records.append(
                _selection_record(
                    item,
                    "selected" if item is winner else "not_selected_lower_score",
                )
            )

    if not selected:
        warnings.append("NO_ELIGIBLE_SOURCES")
    return selected, records, list(dict.fromkeys(warnings))

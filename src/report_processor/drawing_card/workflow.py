"""End-to-end orchestration for drawing-card creation and update."""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from dataclasses import replace
from importlib import resources
from pathlib import Path

from report_processor.hierarchy import HierarchyEntry, filter_aggregate_rows

from .aggregation.aggregator import aggregate_rows, build_complete_card_rows
from .audit import (
    DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
    DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
    AtomicJsonlWriter,
    atomic_write_json,
    atomic_write_jsonl,
    disposition_for_decision,
    disposition_for_row,
    funnel_summary,
    source_hashes,
)
from .autopilot import load_machine_consensus
from .config import load_model_config, load_rules
from .matching.examples import load_confirmed_examples
from .matching.matcher import DrawingRowMatcher
from .models import (
    AggregatedDrawingResult,
    DrawingSourceRow,
    MatchDecision,
    SourceSchema,
    WorkflowRequest,
    WorkflowResult,
)
from .output import (
    load_existing_values,
    merge_update_rows,
    plan_layout,
    plan_write_operations,
    validate_card,
    write_card,
)
from .review import export_manual_review, import_review_approvals
from .sources import (
    build_manifest,
    extract_rows,
    inspect_source,
    materialize_entry,
    open_reader,
    select_inspections,
)
from .sources.identity import load_object_map
from .statuses import Status

LOGGER = logging.getLogger(__name__)

_GLOBAL_STRICT_BLOCKER_STATUSES = frozenset(
    {
        "MANUAL_REVIEW_REQUIRED",
        "SOURCE_INSPECTION_FAILED",
        "SOURCE_EXTRACTION_FAILED",
        Status.AMBIGUOUS_SCHEMA,
        Status.MISSING_REQUIRED_COLUMNS,
        Status.OBJECT_NOT_FOUND,
        Status.OBJECT_CONFLICT,
        Status.UNSAFE_ARCHIVE_PATH,
        Status.SUSPICIOUS_COMPRESSION_RATIO,
        Status.VERY_LARGE_ARCHIVE_ENTRY,
        "FUNNEL_CONSERVATION_FAILED",
        "FUNNEL_UNKNOWN_DISPOSITION",
        "FUNNEL_UNKNOWN_ROLE_POLICY",
        "FUNNEL_ANOMALOUS_EXCLUSION_SHARE",
    }
)

_CONTRIBUTING_ROW_BLOCKER_STATUSES = frozenset(
    {
        Status.DRAWING_CODE_AMBIGUOUS,
        Status.INVALID_NUMBER,
        Status.EXCEL_ERROR,
        Status.FORMULA_WITHOUT_CACHED_VALUE,
        Status.CONFLICT_REQUIRES_REVIEW,
        Status.MODEL_DECISION_INVALID,
    }
)

_CONTRIBUTING_HIERARCHY_BLOCKER_STATUSES: frozenset[str] = frozenset()


def default_rules_path() -> Path:
    return _bundled_resource("rules.json")


def default_examples_path() -> Path:
    return _bundled_resource("confirmed_examples.jsonl")


def default_template_path() -> Path:
    return _bundled_resource("default_drawing_card_template.xlsx")


def _bundled_resource(name: str) -> Path:
    """Resolve a package resource rather than relying on a source checkout."""
    return Path(resources.files("report_processor.drawing_card.resources").joinpath(name))


def _validate_request(request: WorkflowRequest) -> None:
    if not request.inputs or request.input_dir is not None or request.archive is not None:
        raise ValueError("Specify one or more explicit source workbooks")
    if request.mode not in {"create", "update"}:
        raise ValueError("mode must be create or update")
    if request.mode == "create" and request.existing_card is not None:
        raise ValueError("--existing-card is only valid in update mode")
    if request.mode == "update" and request.existing_card is None:
        raise ValueError("update mode requires --existing-card")
    if request.existing_card is not None and not request.existing_card.is_file():
        raise FileNotFoundError(request.existing_card)
    if request.review_decisions is not None and not request.review_decisions.is_file():
        raise FileNotFoundError(request.review_decisions)
    if request.machine_consensus is not None and not request.machine_consensus.is_file():
        raise FileNotFoundError(request.machine_consensus)
    if request.remaining_strategy != "direct_remaining_columns":
        raise ValueError(
            "Only direct_remaining_columns is enabled by default; "
            "calculated fallback is intentionally disabled"
        )
    if request.output is None and not request.dry_run:
        raise ValueError("--output is required unless --dry-run is used")
    if request.output is not None and not request.dry_run:
        output_path = request.output.expanduser().resolve()
        if any(output_path == path.expanduser().resolve() for path in request.inputs):
            raise ValueError("--output must not overwrite an input file")
        if request.output.exists() and request.output.is_dir():
            raise IsADirectoryError(
                f"--output must point to an .xlsx file, not a directory: {request.output}"
            )
        if request.output.suffix.lower() != ".xlsx":
            raise ValueError(f"--output must end with .xlsx: {request.output}")
        base_path = (
            request.existing_card
            if request.mode == "update"
            else request.template or default_template_path()
        )
        if base_path is not None and output_path == base_path.expanduser().resolve():
            raise ValueError("--output must not overwrite the template or existing card")
    if request.objects_per_sheet < 1 or request.objects_per_sheet > 4:
        raise ValueError("objects-per-sheet must be between 1 and 4 for this template contract")
    for path in request.inputs:
        if not path.exists():
            raise FileNotFoundError(path)


def _container_paths(request: WorkflowRequest) -> list[Path]:
    return list(request.inputs)


def _entry_metadata_rank(entry) -> tuple[int, int, int, str]:
    priority = {"visr": 0, "ks6a": 1, "ks2": 2, "svvr": 3, "puo": 4, "vuo": 5}
    revision = int(entry.revision) if entry.revision and entry.revision.isdigit() else 0
    return (
        priority.get(entry.document_type or "", 9),
        int(entry.is_copy),
        -revision,
        entry.logical_path,
    )


def _preferred_metadata_pool(entries: list) -> list:
    """Choose a small primary tier and one fallback without using mtime."""
    if len(entries) <= 3:
        return sorted(entries, key=_entry_metadata_rank)
    by_type: dict[str, list] = {}
    for entry in entries:
        by_type.setdefault(entry.document_type or "unknown", []).append(entry)
    ordered_types = sorted(
        by_type,
        key=lambda document_type: min(
            _entry_metadata_rank(item) for item in by_type[document_type]
        ),
    )
    primary_type = ordered_types[0]
    primary = sorted(by_type[primary_type], key=_entry_metadata_rank)[:2]
    fallback: list = []
    for document_type in ordered_types[1:]:
        candidates = sorted(by_type[document_type], key=_entry_metadata_rank)
        if candidates:
            fallback = [candidates[0]]
            break
    return primary + fallback


def _manifest_candidates(manifest, request: WorkflowRequest):
    """Limit archive inspection without selecting a source by mtime."""
    if request.inputs:
        return manifest
    groups: dict[str, list] = {}
    unhinted = []
    for entry in manifest:
        if entry.is_temporary or entry.is_outdated:
            continue
        if entry.object_index_hint:
            groups.setdefault(entry.object_index_hint, []).append(entry)
        else:
            unhinted.append(entry)
    selected = _preferred_metadata_pool(unhinted) if unhinted else []
    for _object_index, entries in sorted(groups.items()):
        pool = entries
        if request.period:
            exact = [entry for entry in pool if entry.period == request.period]
            pool = exact or [entry for entry in pool if entry.period is None]
        else:
            known = sorted({entry.period for entry in pool if entry.period})
            if known:
                latest = known[-1]
                pool = [entry for entry in pool if entry.period in {latest, None}]
        selected.extend(_preferred_metadata_pool(pool))
    return sorted(
        selected, key=lambda item: (item.object_index_hint or "", _entry_metadata_rank(item))
    )


def _top_schema(inspection, warnings: list[str]) -> SourceSchema | None:
    """Return the best usable schema and preserve ambiguity in the audit."""
    if not inspection.usable_schemas:
        return None
    top_confidence = inspection.usable_schemas[0].confidence
    top_schemas = [
        schema
        for schema in inspection.usable_schemas
        if abs(schema.confidence - top_confidence) < 1e-9
    ]
    if len(top_schemas) > 1:
        warnings.append(
            f"{Status.AMBIGUOUS_SCHEMA}:{inspection.entry.logical_path}:"
            + ",".join(schema.sheet_name for schema in top_schemas)
        )
    return top_schemas[0]


def _processing_summary(
    result: WorkflowResult, matcher_calls: int, validation: dict | None
) -> dict:
    return {
        "run_id": result.run_id,
        "status": result.status,
        "manifest_entries": len(result.manifest),
        "schemas": len(result.schemas),
        "extracted_rows": result.extracted_row_count,
        "classification_decisions": result.classification_decision_count,
        "aggregated_results": len(result.aggregated),
        "card_rows": len(result.card_rows),
        "objects": len({row.object_index for row in result.card_rows}),
        "drawing_groups": len(
            {(row.object_index, row.drawing_code.group_key) for row in result.card_rows}
        ),
        "nonempty_quantities": sum(row.remaining_quantity is not None for row in result.card_rows),
        "nonempty_total_costs": sum(
            row.remaining_total_cost is not None for row in result.card_rows
        ),
        "manual_review_decisions": result.manual_review_count,
        "model_calls": matcher_calls,
        "matching_strategies": sorted(
            {
                decision.matching_strategy
                for decision in result.decisions
                if decision.matching_strategy
            }
        ),
        "write_operations": len(result.write_operations),
        "warnings": result.warnings,
        "output": str(result.output_path) if result.output_path else None,
        "output_validation": validation,
    }


def _publication_blockers(result: WorkflowResult) -> list[str]:
    """Return issues that must prevent strict publication of a card."""
    return list(_publication_blocker_counts(result))


def _publication_blocker_counts(result: WorkflowResult) -> dict[str, int]:
    """Count only unsafe issues that can affect the values being published."""
    counts: Counter[str] = Counter()
    for warning in result.warnings:
        code = str(warning).partition(":")[0]
        if code in _GLOBAL_STRICT_BLOCKER_STATUSES:
            if code == "MANUAL_REVIEW_REQUIRED" and result.manual_review_count:
                counts[code] = result.manual_review_count
            else:
                counts[code] += 1

    contributing_ids = {
        row_id
        for row in result.card_rows
        for row_id in (*row.quantity_source_rows, *row.cost_source_rows)
    }
    for row in result.source_rows:
        if row.row_id not in contributing_ids:
            continue
        for warning in row.warnings:
            code = str(warning).partition(":")[0]
            if code in _CONTRIBUTING_ROW_BLOCKER_STATUSES:
                counts[code] += 1

    for issue in result.hierarchy_issues:
        code = str(getattr(issue, "code", ""))
        if code not in _CONTRIBUTING_HIERARCHY_BLOCKER_STATUSES:
            continue
        issue_row_ids = set(getattr(issue, "related_row_ids", ()))
        row_id = getattr(issue, "row_id", None)
        if row_id:
            issue_row_ids.add(row_id)
        if issue_row_ids.intersection(contributing_ids):
            counts[code] += 1
    return dict(counts)


def _aggregate_unit_mismatch_reviews(
    rows: list[DrawingSourceRow],
    decisions: list[MatchDecision],
    aggregated: list[AggregatedDrawingResult],
) -> tuple[list[DrawingSourceRow], list[MatchDecision]]:
    """Turn late aggregate unit conflicts into actionable source-row review."""
    row_by_id = {row.row_id: row for row in rows}
    decision_by_id = {decision.row_id: decision for decision in decisions}
    review_row_ids = {
        row_id
        for item in aggregated
        if item.status == Status.UNIT_MISMATCH
        for row_id in item.quantity_rows
    }
    review_rows: list[DrawingSourceRow] = []
    review_decisions: list[MatchDecision] = []
    for row_id in sorted(review_row_ids):
        row = row_by_id.get(row_id)
        decision = decision_by_id.get(row_id)
        if row is None or decision is None:
            continue
        review_rows.append(row)
        review_decisions.append(
            replace(
                decision,
                quantity_decision="review",
                reason=(
                    "В одну договорную позицию попали строки с несовместимыми "
                    "единицами. Проверьте единицу или оставьте только стоимость."
                ),
                requires_manual_review=True,
                status=Status.UNIT_MISMATCH,
                warnings=tuple(dict.fromkeys((*decision.warnings, Status.UNIT_MISMATCH))),
            )
        )
    return review_rows, review_decisions


def _save_summary(
    result: WorkflowResult,
    *,
    matcher_calls: int = 0,
    validation: dict | None = None,
) -> None:
    atomic_write_json(
        result.work_dir / "processing_summary.json",
        _processing_summary(result, matcher_calls, validation),
    )


def run_workflow(request: WorkflowRequest) -> WorkflowResult:
    run_id = uuid.uuid4().hex
    run_dir = request.work_dir.expanduser().resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    result = WorkflowResult(run_id=run_id, status=Status.BLOCKED, work_dir=run_dir)
    try:
        _validate_request(request)
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, ValueError) as error:
        result.warnings.append(f"REQUEST_VALIDATION_FAILED:{error}")
        atomic_write_json(
            run_dir / "error.json", {"error": str(error), "stage": "request_validation"}
        )
        _save_summary(result)
        return result
    rules_path = (request.rules or default_rules_path()).expanduser().resolve()
    examples_path = (request.examples or default_examples_path()).expanduser().resolve()
    rules = load_rules(rules_path)
    result.category_units = {rule.category.value: rule.expected_units for rule in rules.categories}
    mapping = load_object_map(request.object_map)
    before_hashes = source_hashes(_container_paths(request))
    atomic_write_json(run_dir / "source_hashes_before.json", before_hashes)

    manifest = build_manifest(request.inputs, None, None)
    result.manifest = manifest
    atomic_write_json(run_dir / "input_manifest.json", manifest)
    LOGGER.info("Discovered %s Excel entries", len(manifest))

    inspections = []
    # Schema quality is only known after inspection. Inspect every manifest entry so
    # metadata pruning cannot hide the best actual source.
    inspection_candidates = manifest
    LOGGER.info("Inspecting %s candidate workbooks", len(inspection_candidates))
    for entry in inspection_candidates:
        try:
            inspections.append(inspect_source(entry, object_mapping=mapping))
        except (OSError, ValueError, KeyError) as error:
            result.warnings.append(f"SOURCE_INSPECTION_FAILED:{entry.logical_path}:{error}")
    atomic_write_json(run_dir / "source_inspections.json", inspections)
    selected, selections, selection_warnings = select_inspections(
        inspections,
        explicit_inputs=bool(request.inputs),
        requested_period=request.period,
    )
    result.warnings.extend(selection_warnings)
    atomic_write_json(run_dir / "source_selections.json", selections)

    try:
        approvals = import_review_approvals(request.review_decisions)
    except ValueError as error:
        result.warnings.append(f"REVIEW_DECISIONS_INVALID:{error}")
        atomic_write_json(
            run_dir / "error.json", {"error": str(error), "stage": "review_decisions"}
        )
        atomic_write_json(
            run_dir / "source_hashes_after.json", source_hashes(_container_paths(request))
        )
        _save_summary(result)
        return result
    examples = load_confirmed_examples(examples_path)
    if request.feedback_examples is not None:
        feedback = load_confirmed_examples(request.feedback_examples)
        examples = tuple({item.example_id: item for item in (*examples, *feedback)}.values())
    tiny_model = None
    if request.rag_mode != "off" and request.model_config is not None:
        from .matching.tiny_model import OpenAICompatibleTinyModel

        tiny_model = OpenAICompatibleTinyModel(load_model_config(request.model_config))
    matcher = DrawingRowMatcher(
        rules,
        examples,
        rag_mode=request.rag_mode,
        tiny_model=tiny_model,
        approvals=approvals,
        machine_consensus=load_machine_consensus(request.machine_consensus),
    )

    matched_rows = []
    matched_decisions = []
    review_rows = []
    review_decisions = []
    dispositions = []
    drawing_rows: dict[tuple[str, str], DrawingSourceRow] = {}
    with (
        AtomicJsonlWriter(run_dir / "extracted_rows.jsonl") as extracted_writer,
        AtomicJsonlWriter(run_dir / "classification_decisions.jsonl") as classification_writer,
        AtomicJsonlWriter(run_dir / "matches.jsonl") as matches_writer,
        AtomicJsonlWriter(run_dir / "rejected_rows.jsonl") as rejected_writer,
        AtomicJsonlWriter(run_dir / "row_dispositions.jsonl") as disposition_writer,
    ):
        for inspection in selected:
            schema = _top_schema(inspection, result.warnings)
            if schema is None:
                continue
            result.schemas.append(schema)
            result.warnings.extend(schema.warnings)
            if inspection.entry.extension.lower() == ".xlsb":
                # The XLSB reader exposes cached Excel values, but not formula text.
                # This is a source capability notice, not a per-row data failure.
                result.warnings.append(Status.FORMULA_NOT_AVAILABLE_FOR_BACKEND)
            materialized = materialize_entry(inspection.entry)
            reader = None
            try:
                LOGGER.info(
                    "Extracting %s [%s]",
                    inspection.entry.logical_path,
                    schema.sheet_name,
                )
                reader = open_reader(materialized.path)
                extracted_rows = list(
                    extract_rows(
                        reader,
                        inspection.entry,
                        schema,
                        inspection.object_identity.value,
                    )
                )
                hierarchy = filter_aggregate_rows(
                    [
                        HierarchyEntry(
                            row_id=row.row_id,
                            position_code=row.position_code_raw,
                            amount=row.remaining_total_cost,
                            context=(row.location.file_id, row.location.sheet_name),
                            is_transactional=_is_transactional_hierarchy_row(row),
                        )
                        for row in extracted_rows
                    ]
                )
                parent_ids = set(hierarchy.parent_row_ids)
                resource_detail_ids = set(hierarchy.resource_detail_row_ids)
                result.hierarchy_issues.extend(hierarchy.issues)
                result.warnings.extend(hierarchy.warnings)
                for row in extracted_rows:
                    result.extracted_row_count += 1
                    extracted_writer.write(row)
                    result.warnings.extend(row.warnings)
                    if row.row_id in parent_ids:
                        disposition = disposition_for_row(
                            row,
                            disposition=DISPOSITION_HIERARCHY_AGGREGATE_EXCLUDED,
                            reason_code="HIERARCHY_AGGREGATE_POLICY",
                            row_role="aggregate",
                        )
                        dispositions.append(disposition)
                        disposition_writer.write(disposition)
                        rejected_writer.write(
                            {"row_id": row.row_id, "status": Status.HIERARCHY_AGGREGATE_EXCLUDED}
                        )
                        continue
                    if row.row_id in resource_detail_ids:
                        disposition = disposition_for_row(
                            row,
                            disposition=DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
                            reason_code="HIERARCHY_RESOURCE_DETAIL_POLICY",
                            row_role="resource_detail",
                        )
                        dispositions.append(disposition)
                        disposition_writer.write(disposition)
                        rejected_writer.write(
                            {
                                "row_id": row.row_id,
                                "status": Status.HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
                            }
                        )
                        continue
                    if _is_source_resource_detail(row):
                        disposition = disposition_for_row(
                            row,
                            disposition=DISPOSITION_HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
                            reason_code="SOURCE_RESOURCE_DETAIL_POLICY",
                            row_role="resource_detail",
                        )
                        dispositions.append(disposition)
                        disposition_writer.write(disposition)
                        rejected_writer.write(
                            {
                                "row_id": row.row_id,
                                "status": Status.HIERARCHY_RESOURCE_DETAIL_EXCLUDED,
                            }
                        )
                        continue
                    if row.object_index_raw and row.drawing_code_raw:
                        drawing_rows.setdefault((row.object_index_raw, row.drawing_code_raw), row)
                    decision = matcher.match(row)
                    disposition = disposition_for_decision(row, decision)
                    dispositions.append(disposition)
                    disposition_writer.write(disposition)
                    result.classification_decision_count += 1
                    classification_writer.write(decision)
                    if decision.category is not None:
                        matched_rows.append(row)
                        matched_decisions.append(decision)
                        matches_writer.write(decision)
                    if decision.requires_manual_review:
                        review_rows.append(row)
                        review_decisions.append(decision)
                        rejected_writer.write(decision)
                    if result.extracted_row_count % 10_000 == 0:
                        LOGGER.info(
                            "Processed %s source rows; matched %s; review %s",
                            result.extracted_row_count,
                            len(matched_decisions),
                            len(review_decisions),
                        )
            except (OSError, ValueError, KeyError, TypeError) as error:
                result.warnings.append(
                    f"SOURCE_EXTRACTION_FAILED:{inspection.entry.logical_path}:{error}"
                )
            finally:
                if reader is not None:
                    reader.close()
                materialized.close()

    atomic_write_jsonl(run_dir / "hierarchy_issues.jsonl", result.hierarchy_issues)
    funnel = funnel_summary(dispositions, extracted_row_count=result.extracted_row_count)
    atomic_write_json(run_dir / "funnel_summary.json", funnel)
    for blocker in funnel["strict_blockers"]:
        result.warnings.append(str(blocker))
    aggregated = aggregate_rows(
        matched_rows,
        matched_decisions,
        drawing_code_mode=request.drawing_code_mode,
        strict=request.strict,
    )
    result.aggregated = aggregated
    result.warnings.extend(warning for item in aggregated for warning in item.warnings)
    atomic_write_jsonl(run_dir / "aggregated_results.jsonl", aggregated)

    aggregate_review_rows, aggregate_review_decisions = _aggregate_unit_mismatch_reviews(
        matched_rows, matched_decisions, aggregated
    )
    review_rows_by_id = {row.row_id: row for row in review_rows}
    review_rows_by_id.update({row.row_id: row for row in aggregate_review_rows})
    review_decisions_by_id = {decision.row_id: decision for decision in review_decisions}
    review_decisions_by_id.update(
        {decision.row_id: decision for decision in aggregate_review_decisions}
    )
    result.manual_review_count = len(review_decisions_by_id)
    if result.manual_review_count:
        result.warnings.append(f"MANUAL_REVIEW_REQUIRED:{result.manual_review_count}")

    retained_rows = {row.row_id: row for row in drawing_rows.values()}
    retained_rows.update({row.row_id: row for row in matched_rows})
    retained_rows.update(review_rows_by_id)
    retained_decisions = {decision.row_id: decision for decision in matched_decisions}
    retained_decisions.update(review_decisions_by_id)
    result.source_rows = list(retained_rows.values())
    result.decisions = list(retained_decisions.values())
    atomic_write_jsonl(run_dir / "aggregate_review_decisions.jsonl", aggregate_review_decisions)
    export_manual_review(
        run_dir / "manual_review.xlsx",
        list(review_rows_by_id.values()),
        list(review_decisions_by_id.values()),
    )

    card_rows = build_complete_card_rows(
        list(drawing_rows.values()),
        aggregated,
        rules,
        drawing_code_mode=request.drawing_code_mode,
    )
    if request.mode == "update" and request.existing_card is not None:
        existing = load_existing_values(request.existing_card)
        card_rows, update_warnings = merge_update_rows(card_rows, existing, request.update_policy)
        result.warnings.extend(update_warnings)
    result.card_rows = card_rows
    layouts = plan_layout(card_rows, objects_per_sheet=request.objects_per_sheet)
    result.layouts = layouts
    atomic_write_json(run_dir / "layout_plan.json", layouts)

    planned_ops = plan_write_operations(
        rows=card_rows,
        layouts=layouts,
        run_id=run_id,
        cost_scale=rules.cost_scale,
    )
    result.write_operations = planned_ops
    atomic_write_json(run_dir / "planned_write_operations.json", planned_ops)

    result.blocker_counts = _publication_blocker_counts(result)
    result.blockers = list(result.blocker_counts)
    blockers = result.blockers
    validation = None
    if request.strict and blockers:
        result.status = Status.BLOCKED
    elif not card_rows:
        if "NO_CARD_ROWS" not in result.warnings:
            result.warnings.append("NO_CARD_ROWS")
        result.status = Status.BLOCKED
    elif request.dry_run:
        result.status = (
            Status.PARTIALLY_READY
            if blockers
            else Status.COMPLETED_WITH_WARNINGS
            if result.warnings
            else Status.OK
        )
    else:
        base_path = (
            request.existing_card
            if request.mode == "update"
            else request.template or default_template_path()
        )
        if base_path is None or not base_path.exists():
            result.warnings.append(
                "OUTPUT_BASE_MISSING:Drawing-card template is required. "
                "Use --template or keep the bundled template."
            )
            result.status = Status.BLOCKED
        else:
            assert request.output is not None
            operations = write_card(
                base_path=base_path,
                output_path=request.output,
                rows=card_rows,
                layouts=layouts,
                run_id=run_id,
                cost_scale=rules.cost_scale,
            )
            result.write_operations = operations
            result.output_path = request.output
            atomic_write_jsonl(run_dir / "write_operations.jsonl", operations)
            validation = validate_card(request.output, layouts)
            atomic_write_json(run_dir / "output_validation.json", validation)
            if validation["status"] != Status.OK:
                result.status = Status.OUTPUT_VALIDATION_FAILED
            else:
                result.status = (
                    Status.PARTIALLY_READY
                    if blockers
                    else Status.COMPLETED_WITH_WARNINGS
                    if result.warnings
                    else Status.OK
                )

    after_hashes = source_hashes(_container_paths(request))
    atomic_write_json(run_dir / "source_hashes_after.json", after_hashes)
    unchanged = before_hashes == after_hashes
    if not unchanged:
        result.warnings.append("SOURCE_HASH_CHANGED")
        result.status = Status.BLOCKED
    summary = _processing_summary(result, matcher.model_calls, validation)
    summary["source_hashes_unchanged"] = unchanged
    atomic_write_json(run_dir / "processing_summary.json", summary)
    return result


def _is_transactional_hierarchy_row(row: DrawingSourceRow) -> bool:
    """Return whether a row is a measured work/resource line, not a section label."""
    name = row.work_name_raw or ""
    has_business_name = any(character.isalpha() for character in name)
    return has_business_name and bool(row.cost_type_code_raw)


def _is_source_resource_detail(row: DrawingSourceRow) -> bool:
    """Identify source-native resource/equipment rows before category matching."""
    name = row.work_name_raw or ""
    has_business_name = any(character.isalpha() for character in name)
    has_line_values = bool(row.unit_raw) or row.remaining_quantity is not None
    return has_business_name and has_line_values and not row.cost_type_code_raw

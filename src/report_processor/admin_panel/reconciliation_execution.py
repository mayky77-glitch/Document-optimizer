"""Authoritative reconciliation adapter for the documented report layout."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from report_processor.calculation import calculate_matches
from report_processor.matching import (
    MatchCandidate,
    MatchResult,
    MatchStatus,
    MatchStrategy,
    match_rows,
)
from report_processor.reconciliation_grouping import (
    PackageVersionContext,
    build_reconciliation_packages,
    partition_rows,
)
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewDecision,
    ReviewRow,
    apply_overrides,
    build_review_groups,
    feedback_for_group,
    latest_feedback,
    normalize_name,
    normalize_unit,
)
from report_processor.schema import LogicalColumn

from .reconciliation_batch_store import ReconciliationBatchStore
from .reconciliation_semantic_assist import RUBERT_TINY2_MODEL_REVISION, run_local_semantic_assist
from .reconciliation_sources import AllReconciliationSourcesUnusableError, ReconciliationSourceBatch
from .reconciliation_state import ReconciliationReviewState
from .reconciliation_target import (
    category_id,
    publish_unchanged_target,
    read_reconciliation_target,
    terminal_index,
    writer_calculations,
)
from .reconciliation_target_measure import ReconciliationTargetMeasureError


@dataclass(frozen=True, slots=True)
class ReconciliationReviewResult:
    state: ReconciliationReviewState | None
    source_batch: ReconciliationSourceBatch | None
    source_issues: tuple[object, ...] = ()
    target_error: bool = False
    target_error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationApplyResult:
    output: object
    feedback: tuple[FeedbackRecord, ...]
    apply_key: str
    payload_hash: str
    catalog_digest: str = ""
    target_identity_digest: str = ""
    calculation_digest: str = ""
    rules_hash: str = ""
    actionable: bool = False

    def __iter__(self):
        # Preserve the narrow pre-integrity adapter contract for direct callers.
        yield self.output
        yield self.feedback


def prepare_review(job, feedback: tuple[FeedbackRecord, ...]) -> ReconciliationReviewResult:
    """Build only the strict physical current-period review.

    Historical target projection is deliberately a separate entry point.  The
    verification flow calls this function and must never load the preview or
    period-transform modules.
    """
    if getattr(job, "reporting_period", None) is not None:
        raise ValueError("REPORTING_PERIOD_REQUIRES_PERIOD_PREVIEW")
    try:
        _schema, targets = read_reconciliation_target(job.target, job.target_digest, job.stage)
    except ReconciliationTargetMeasureError as error:
        return ReconciliationReviewResult(None, None, (), True, str(error))
    except Exception:
        return ReconciliationReviewResult(None, None, (), True)
    return _prepare_review_from_targets(job, feedback, targets, job.target_digest)


def prepare_period_review(job, feedback: tuple[FeedbackRecord, ...]) -> ReconciliationReviewResult:
    """Build a review against one immutable read-only target projection."""
    period = getattr(job, "reporting_period", None)
    if period is None:
        return prepare_review(job, feedback)
    try:
        # Keep this import local: document verification imports only
        # ``prepare_review`` and must not even import the preview/planner path.
        from .reconciliation_period_preview import preview_reconciliation_target

        preview = preview_reconciliation_target(job.target, job.target_digest, job.stage, period)
    except ReconciliationTargetMeasureError as error:
        return ReconciliationReviewResult(None, None, (), True, str(error))
    except Exception:
        return ReconciliationReviewResult(None, None, (), True)
    identity = preview.target_identity_digest
    job.target_identity_digest = identity
    return _prepare_review_from_targets(job, feedback, preview.rows, identity)


def _prepare_review_from_targets(
    job,
    feedback: tuple[FeedbackRecord, ...],
    targets,
    target_identity_digest: str,
) -> ReconciliationReviewResult:
    try:
        catalog = _catalog(targets)
    except Exception:
        return ReconciliationReviewResult(None, None, (), True)
    try:
        target_identities = {
            terminal_index(target.document_index_normalized) for target in targets
        } - {None}
        batch = _sources(job, target_identities) if target_identities else _sources(job)
    except AllReconciliationSourcesUnusableError as error:
        return ReconciliationReviewResult(None, None, error.issues)
    identities = getattr(batch, "terminal_identities", ())
    source_rows = _review_rows(batch.rows, targets, catalog, job, identities)
    partition = partition_rows(source_rows)
    # Zero-activity rows remain internal source facts.  They must never reach
    # grouping, feedback or an operator decision surface.
    rows = partition.visible_rows
    groups = build_review_groups(rows)
    grouping = build_reconciliation_packages(
        source_rows,
        groups,
        category_availability=_group_category_availability(
            groups, batch.rows, catalog, job, identities
        ),
        version_context=PackageVersionContext(
            _normalized_source_digests(job.source_digests),
            target_identity_digest,
            _catalog_version(catalog),
            model_revision=RUBERT_TINY2_MODEL_REVISION,
        ),
    )
    state = ReconciliationReviewState(
        rows={row.row_id: row for row in rows},
        groups={group.group_id: group for group in groups},
        categories={key: value for key, value in catalog.labels.items()},
        source_digests=job.source_digests,
        target_digest=job.target_digest,
        target_identity_digest=target_identity_digest,
        available_categories=_available_categories(batch.rows, catalog, job, identities),
        grouping=grouping,
    )
    semantic_assist = run_local_semantic_assist(grouping)
    state.set_semantic_assist(semantic_assist.group_ids, semantic_assist.hint)
    _restore_feedback(state, feedback)
    store = ReconciliationBatchStore(job.directory)
    store.restore(state)
    state.set_autosave(store.save)
    return ReconciliationReviewResult(state, batch, batch.issues)


def apply_review(
    job, state: ReconciliationReviewState, decisions: tuple[ReviewDecision, ...] | None = None
) -> ReconciliationApplyResult:
    from report_processor.business_rules import load_default_rule_set, load_rule_configuration
    from report_processor.excel_writer import write_target_report
    from report_processor.quality_control import WriteDecision

    rule_set = (
        load_rule_configuration(job.rules_path)
        if getattr(job, "rules_path", None)
        else load_default_rule_set()
    )
    if not rule_set.valid or rule_set.rule_set is None:
        raise ValueError("RULE_CONFIGURATION_INVALID")
    snapshot = decisions if decisions is not None else tuple(state.core_decisions())
    feedback = _feedback_records(state, snapshot)
    plan = _apply_plan(job, state, rule_set.rule_set.content_hash, feedback, snapshot)
    schema, targets, identity, preview = _apply_target_projection(job)
    catalog, matches, selected = _calculate_selected(
        job, state, snapshot, rule_set.rule_set, targets
    )
    catalog_digest = _catalog_digest(catalog, identity)
    calculation_digest = calculation_semantic_digest(selected)
    actionable = any(item.quantity is not None or item.cost is not None for item in selected)
    if not actionable:
        publish_unchanged_target(job.target, job.directory / "result.xlsx", job.target_digest)
        return ReconciliationApplyResult(
            job.directory / "result.xlsx",
            feedback,
            *plan,
            catalog_digest,
            identity,
            calculation_digest,
            rule_set.rule_set.content_hash,
            False,
        )
    write_job = job
    if preview is not None:
        from report_processor.excel_writer import prepare_period_insertion

        prepared = prepare_period_insertion(
            job.target, job.directory / "apply-period-target.xlsx", preview.plan
        )
        prepared_digest = getattr(prepared, "output_sha256", None)
        if not isinstance(prepared_digest, str):
            raise RuntimeError("RECONCILIATION_PERIOD_PREPARE_INVALID")
        write_job = _prepared_apply_job(job, prepared_digest)
        strict_schema, strict_targets = read_reconciliation_target(
            write_job.target, write_job.target_digest, write_job.stage
        )
        strict_catalog, strict_matches, strict_selected = _calculate_selected(
            write_job, state, snapshot, rule_set.rule_set, strict_targets
        )
        strict_catalog_digest = _catalog_digest(strict_catalog, identity)
        strict_calculation_digest = calculation_semantic_digest(strict_selected)
        if (
            strict_catalog_digest != catalog_digest
            or _match_target_ids(strict_matches) != _match_target_ids(matches)
            or strict_calculation_digest != calculation_digest
        ):
            raise RuntimeError("RECONCILIATION_PERIOD_APPLY_DRIFT")
        schema, selected = strict_schema, strict_selected
    result = write_target_report(
        write_job.target, job.directory / "result.xlsx", WriteDecision.ALLOW_WRITE, selected, schema
    )
    if getattr(result, "output_sha256", None) is None:
        raise RuntimeError("authoritative workbook write was not verified")
    return ReconciliationApplyResult(
        job.directory / "result.xlsx",
        feedback,
        *plan,
        catalog_digest,
        identity,
        calculation_digest,
        rule_set.rule_set.content_hash,
        True,
    )


def rebuild_apply_evidence(
    job, state: ReconciliationReviewState, decisions: tuple[ReviewDecision, ...]
):
    """Recreate bounded apply facts without a transformer or writer call."""
    from report_processor.business_rules import load_default_rule_set, load_rule_configuration

    rule_set = (
        load_rule_configuration(job.rules_path)
        if getattr(job, "rules_path", None)
        else load_default_rule_set()
    )
    if not rule_set.valid or rule_set.rule_set is None:
        raise RuntimeError("RULE_CONFIGURATION_INVALID")
    feedback = _feedback_records(state, decisions)
    apply_key, plan_hash = _apply_plan(
        job, state, rule_set.rule_set.content_hash, feedback, decisions
    )
    _schema, targets, identity, _preview = _apply_target_projection(job)
    catalog, _matches, selected = _calculate_selected(
        job, state, decisions, rule_set.rule_set, targets
    )
    return {
        "apply_key": apply_key,
        "plan_hash": plan_hash,
        "catalog_digest": _catalog_digest(catalog, identity),
        "target_identity_digest": identity,
        "calculation_digest": calculation_semantic_digest(selected),
        "rules_hash": rule_set.rule_set.content_hash,
        "actionable": any(item.quantity is not None or item.cost is not None for item in selected),
        "feedback": feedback,
    }


def _apply_target_projection(job):
    period = getattr(job, "reporting_period", None)
    if period is None:
        schema, targets = read_reconciliation_target(job.target, job.target_digest, job.stage)
        identity = getattr(job, "target_identity_digest", None) or job.target_digest
        return schema, targets, identity, None
    from .reconciliation_period_preview import preview_reconciliation_target

    preview = preview_reconciliation_target(job.target, job.target_digest, job.stage, period)
    identity = preview.target_identity_digest
    expected = getattr(job, "target_identity_digest", None)
    if expected is not None and expected != identity:
        raise RuntimeError("RECONCILIATION_TARGET_IDENTITY_CHANGED")
    return preview.schema, preview.rows, identity, preview


def _calculate_selected(job, state, decisions, rule_set, targets):
    catalog = _catalog(targets)
    overrides = apply_overrides(state.rows.values(), state.groups.values(), decisions)
    target_identities = {terminal_index(target.document_index_normalized) for target in targets} - {
        None
    }
    source_batch = _sources(job, target_identities) if target_identities else _sources(job)
    source_rows = {_review_row_id(job, row.source_row_id): row for row in source_batch.rows}
    matches = _selected_matches(
        state,
        overrides,
        catalog,
        job,
        source_rows,
        getattr(source_batch, "terminal_identities", ()),
    )
    calculations = calculate_matches(
        matches,
        rule_set,
        {
            candidate.candidate_id: override.candidate_inclusion
            for match in matches
            for candidate in match.effective_selected_candidates
            if (override := overrides[candidate.source_row_id]) is not None
        },
    )
    return (
        catalog,
        matches,
        writer_calculations(
            item for item in calculations if item.status.value.startswith("calculated")
        ),
    )


def _prepared_apply_job(job, prepared_digest: str):
    from dataclasses import replace

    target = job.directory / "apply-period-target.xlsx"
    return replace(job, target=target, target_digest=prepared_digest)


def _catalog_digest(catalog: _Catalog, target_identity_digest: str) -> str:
    return _hash(
        "ReconciliationCatalogIdentity-1.0",
        target_identity_digest,
        _catalog_version(catalog),
    )


def _match_target_ids(matches) -> tuple[str, ...]:
    return tuple(sorted(match.target_row_id for match in matches))


def calculation_semantic_digest(calculations) -> str:
    """Canonical writer-adapted calculation facts, sorted independently of input order."""
    payload = [
        {
            "cost": _decimal_text(item.cost),
            "quantity": _decimal_text(item.quantity),
            "status": item.status.value,
            "target_row_id": item.target_row_id,
        }
        for item in calculations
    ]
    return _hash(
        "ReconciliationCalculationSemantics-1.0",
        sorted(payload, key=lambda item: item["target_row_id"]),
    )


def _decimal_text(value) -> str | None:
    return str(value) if value is not None else None


@dataclass(frozen=True, slots=True)
class _Catalog:
    labels: dict[str, str]
    targets: dict[tuple[str, str], object]


def _catalog(targets) -> _Catalog:
    labels: dict[str, str] = {}
    by_index: dict[tuple[str, str], object] = {}
    for target in targets:
        label = (target.work_name or "").strip()
        index = terminal_index(target.document_index_normalized)
        if not label or not index:
            continue
        key = category_id(label)
        labels.setdefault(key, label)
        pair = (index, key)
        if pair in by_index:
            raise ValueError("DUPLICATE_TARGET_CATEGORY")
        by_index[pair] = target
    return _Catalog(labels, by_index)


def _sources(job, target_identities: set[str] | None = None) -> ReconciliationSourceBatch:
    from .reconciliation_sources import (
        ReconciliationSourceDescriptor,
        descriptor_from_upload_basename,
        extract_reconciliation_sources,
        resolve_descriptor_identity,
    )

    paths = job.sources or (job.source,)
    names = tuple(getattr(job, "source_names", ()) or ())
    descriptors = (
        tuple(descriptor_from_upload_basename(name) for name in names)
        if len(names) == len(paths)
        else tuple(ReconciliationSourceDescriptor(path.name) for path in paths)
    )
    if target_identities is not None:
        descriptors = tuple(
            resolve_descriptor_identity(descriptor, target_identities) for descriptor in descriptors
        )
    workbooks = tuple(
        (path, f"source:{job.source_digests[index]}", descriptor)
        for index, (path, descriptor) in enumerate(zip(paths, descriptors, strict=True))
    )
    return extract_reconciliation_sources(workbooks, require_document_index=True)


def _review_rows(rows, targets, catalog: _Catalog, job, identities=()) -> tuple[ReviewRow, ...]:
    from report_processor.business_rules import load_default_rule_set, load_rule_configuration

    validation = (
        load_rule_configuration(job.rules_path)
        if getattr(job, "rules_path", None)
        else load_default_rule_set()
    )
    if not validation.valid or validation.rule_set is None:
        raise ValueError("RULE_CONFIGURATION_INVALID")
    matches = match_rows(
        rows,
        targets,
        validation.rule_set,
        target_source_id=f"target:{job.target_digest}",
        target_fingerprint=f"sha256:{job.target_digest}",
    )
    proposals: dict[str, set[str]] = {}
    for match in matches:
        target_index = terminal_index(match.target_row.document_index_normalized)
        category = category_id(match.target_row.work_name or "")
        for candidate in match.candidates:
            if (
                not candidate.blockers
                and dict(identities).get(candidate.source_row.source_file_id) == target_index
            ):
                proposals.setdefault(candidate.source_row_id, set()).add(category)
    return tuple(
        ReviewRow(
            _review_row_id(job, row.source_row_id),
            row.work_name,
            row.unit,
            row.source_row.period_quantity,
            row.source_row.period_cost,
            _unique(proposals.get(row.source_row_id, set()), catalog),
        )
        for row in sorted(rows, key=lambda item: item.source_row_id)
    )


def _unique(values: set[str], catalog: _Catalog) -> str | None:
    eligible = values.intersection(catalog.labels)
    return next(iter(eligible)) if len(eligible) == 1 else None


def _available_categories(rows, catalog: _Catalog, job, identities=()) -> dict[str, frozenset[str]]:
    by_index: dict[str, set[str]] = {}
    for index, category in catalog.targets:
        by_index.setdefault(index, set()).add(category)
    return {
        _review_row_id(job, row.source_row_id): frozenset(
            by_index.get(dict(identities).get(row.source_file_id, ""), set())
        )
        for row in rows
    }


def _group_category_availability(
    groups, rows, catalog: _Catalog, job, identities=()
) -> dict[str, frozenset[str]]:
    available = _available_categories(rows, catalog, job, identities)
    return {
        group.group_id: frozenset.intersection(
            *(available.get(row_id, frozenset()) for row_id in group.member_ids)
        )
        for group in groups
    }


def _catalog_version(catalog: _Catalog) -> str:
    return sha256(
        json.dumps(
            {
                "contract": "ReconciliationTargetMeasure-2.0",
                "labels": sorted(catalog.labels.items()),
                "targets": sorted(
                    (
                        index,
                        category,
                        target.sheet_name,
                        target.row_number,
                        _target_cell_coordinate(target, LogicalColumn.CURRENT_PERIOD_QUANTITY),
                        _target_cell_coordinate(target, LogicalColumn.CURRENT_PERIOD_COST),
                    )
                    for (index, category), target in catalog.targets.items()
                ),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _normalized_source_digests(values) -> tuple[str, ...]:
    raw = tuple(values)
    if any(not isinstance(value, str) for value in raw):
        raise ValueError("source digests are required")
    normalized = tuple(sorted({value.strip().casefold() for value in raw}))
    if not normalized or any(not value for value in normalized):
        raise ValueError("source digests are required")
    return normalized


def _selected_matches(state, overrides, catalog: _Catalog, job, source_rows, identities=()):
    buckets: dict[str, tuple[object, list[MatchCandidate]]] = {}
    reserved_identities: set[tuple[str, str, int]] = set()
    for row_id, override in sorted(overrides.items()):
        if override.action is None or override.target_category is None:
            continue
        source = source_rows[row_id]
        identity = _physical_source_identity(source)
        if identity in reserved_identities:
            raise ValueError("DUPLICATE_SOURCE_IDENTITY")
        reserved_identities.add(identity)
        index = dict(identities).get(source.source_file_id)
        target = catalog.targets.get((index or "", override.target_category))
        if target is None:
            raise ValueError("SELECTED_CATEGORY_UNAVAILABLE")
        target_id = _target_id(job, target)
        candidate = MatchCandidate(
            _hash("review", target_id, row_id),
            target_id,
            row_id,
            source,
            (MatchStrategy.AUTHORITATIVE_REVIEW,),
            Decimal("1"),
            (),
            ("operator_category",),
            {},
            {"target_row_id": target_id},
            auto_selectable=False,
        )
        buckets.setdefault(target_id, (target, []))[1].append(candidate)
    return tuple(
        MatchResult(
            _hash("match", target_id),
            target_id,
            target,
            MatchStatus.MATCHED,
            None,
            tuple(candidates),
            (),
            ("operator_selected",),
            tuple(candidates),
        )
        for target_id, (target, candidates) in sorted(buckets.items())
    )


def _physical_source_identity(source) -> tuple[str, str, int]:
    location = source.source_location
    digest = str(location.source_file_id).rsplit(":", 1)[-1]
    row = location.row_number
    if (
        not digest
        or not isinstance(location.sheet_name, str)
        or not location.sheet_name
        or row <= 0
    ):
        raise ValueError("INVALID_SOURCE_IDENTITY")
    return digest, location.sheet_name, row


def _apply_plan(
    job,
    state: ReconciliationReviewState,
    rules_hash: str,
    feedback: tuple[FeedbackRecord, ...],
    decisions: tuple[ReviewDecision, ...],
) -> tuple[str, str]:
    decisions = [
        {
            "action": item.action.value,
            "mode": item.mode.value if item.mode else None,
            "target_category": item.target_category,
            "group_id": item.group_id,
            "row_id": item.row_id,
            "version": item.version,
        }
        for item in decisions
    ]
    payload = {
        "contract": "ReconciliationApplyIntegrity-3.0",
        "job_id": getattr(job, "job_id", "direct-apply"),
        "source_digests": tuple(getattr(job, "source_digests", ())),
        "target_digest": job.target_digest,
        "target_identity_digest": getattr(job, "target_identity_digest", None) or job.target_digest,
        "stage": job.stage,
        "state_fingerprint": getattr(state, "version_fingerprint", "direct-apply"),
        "rules_hash": rules_hash,
        "decisions": sorted(
            decisions, key=lambda item: (item["group_id"] or "", item["row_id"] or "")
        ),
        "feedback": [
            (
                item.name_key,
                item.unit_key,
                item.action.value,
                item.target_category,
                item.mode.value if item.mode else None,
            )
            for item in feedback
        ],
    }
    payload_hash = _hash("apply-payload", payload)
    return _hash("apply-key", payload), payload_hash


def _target_id(job, target) -> str:
    target_identity = getattr(job, "target_identity_digest", None) or job.target_digest
    return _hash(
        "target",
        "MatchingContract-12.0",
        f"target:{target_identity}",
        f"sha256:{target_identity}",
        target.sheet_name,
        target.row_number,
        _target_cell_coordinate(target, LogicalColumn.CURRENT_PERIOD_QUANTITY),
        _target_cell_coordinate(target, LogicalColumn.CURRENT_PERIOD_COST),
    )


def _target_cell_coordinate(target, logical_column: LogicalColumn) -> str | None:
    cell_for = getattr(target, "cell_for", None)
    cell = cell_for(logical_column) if callable(cell_for) else None
    coordinate = getattr(cell, "coordinate", None)
    return coordinate if isinstance(coordinate, str) else None


def _source_index(filename: str) -> str | None:
    from .reconciliation_sources import document_index_from_basename

    return document_index_from_basename(filename)


def _review_row_id(job, source_row_id: str) -> str:
    return (
        "review-row-"
        + _hash(
            "ReconciliationReviewRow-1.0",
            getattr(job, "target_identity_digest", None) or job.target_digest,
            *_normalized_source_digests(job.source_digests),
            source_row_id,
        )[:32]
    )


def _hash(*parts) -> str:
    return sha256(
        json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _restore_feedback(state, feedback) -> None:
    rows = state.rows
    for group in state.groups.values():
        if record := feedback_for_group(group, feedback):
            decision = ReviewDecision(
                record.action,
                record.mode,
                record.target_category,
                group_id=group.group_id,
                version=group.version,
            )
            try:
                state.validate_decision(decision, group_id=group.group_id)
            except ValueError:
                continue
            state.group_decisions[group.group_id] = decision
            state.familiar_group_ids.add(group.group_id)
    records = latest_feedback(feedback)
    for row in rows.values():
        if record := records.get((normalize_name(row.display_name), normalize_unit(row.unit))):
            decision = ReviewDecision(
                record.action, record.mode, record.target_category, row_id=row.row_id
            )
            try:
                state.validate_decision(decision, row_id=row.row_id)
            except ValueError:
                continue
            state.row_decisions[row.row_id] = decision
            group = next(item for item in state.groups.values() if row.row_id in item.member_ids)
            state.familiar_group_ids.add(group.group_id)


def _feedback_records(
    state, decisions: tuple[ReviewDecision, ...] | None = None
) -> tuple[FeedbackRecord, ...]:
    from report_processor.reconciliation_review import (
        feedback_from_decision,
        feedback_from_row_decision,
    )

    effective = decisions
    if effective is None:
        effective_decisions = getattr(state, "effective_decisions", None)
        effective = (
            tuple(effective_decisions())
            if callable(effective_decisions)
            else (*state.group_decisions.values(), *state.row_decisions.values())
        )
    group_decisions = sorted(
        (decision for decision in effective if decision.group_id is not None),
        key=lambda decision: decision.group_id or "",
    )
    row_decisions = sorted(
        (decision for decision in effective if decision.row_id is not None),
        key=lambda decision: decision.row_id or "",
    )
    groups = state.groups
    values = [
        feedback_from_decision(groups[decision.group_id], decision, sequence=index)
        for index, decision in enumerate(group_decisions, 1)
        if decision.group_id is not None
    ]
    values.extend(
        feedback_from_row_decision(state.rows[decision.row_id], decision, sequence=index)
        for index, decision in enumerate(
            row_decisions,
            len(values) + 1,
        )
        if decision.row_id is not None
    )
    return tuple(values)

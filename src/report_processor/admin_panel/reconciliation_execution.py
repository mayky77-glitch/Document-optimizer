"""Authoritative reconciliation adapter for the documented report layout."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from report_processor.calculation import calculate_matches
from report_processor.identifiers import extract_document_index
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


@dataclass(frozen=True, slots=True)
class ReconciliationReviewResult:
    state: ReconciliationReviewState | None
    source_batch: ReconciliationSourceBatch | None
    source_issues: tuple[object, ...] = ()
    target_error: bool = False


def prepare_review(job, feedback: tuple[FeedbackRecord, ...]) -> ReconciliationReviewResult:
    try:
        batch = _sources(job)
    except AllReconciliationSourcesUnusableError as error:
        return ReconciliationReviewResult(None, None, error.issues)
    try:
        _schema, targets = read_reconciliation_target(job.target, job.target_digest, job.stage)
    except Exception:
        return ReconciliationReviewResult(None, batch, batch.issues, True)
    catalog = _catalog(targets)
    source_rows = _review_rows(batch.rows, targets, catalog, job)
    partition = partition_rows(source_rows)
    # Zero-activity rows remain internal source facts.  They must never reach
    # grouping, feedback or an operator decision surface.
    rows = partition.visible_rows
    groups = build_review_groups(rows)
    grouping = build_reconciliation_packages(
        source_rows,
        groups,
        category_availability=_group_category_availability(groups, batch.rows, catalog, job),
        version_context=PackageVersionContext(
            _normalized_source_digests(job.source_digests),
            job.target_digest,
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
        available_categories=_available_categories(batch.rows, catalog, job),
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
    job, state: ReconciliationReviewState
) -> tuple[object, tuple[FeedbackRecord, ...]]:
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
    schema, targets = read_reconciliation_target(job.target, job.target_digest, job.stage)
    catalog = _catalog(targets)
    overrides = apply_overrides(state.rows.values(), state.groups.values(), state.core_decisions())
    source_rows = {_review_row_id(job, row.source_row_id): row for row in _sources(job).rows}
    matches = _selected_matches(state, overrides, catalog, job, source_rows)
    calculations = calculate_matches(
        matches,
        rule_set.rule_set,
        {
            candidate.candidate_id: override.candidate_inclusion
            for match in matches
            for candidate in match.effective_selected_candidates
            if (override := overrides[candidate.source_row_id]) is not None
        },
    )
    selected = writer_calculations(
        item for item in calculations if item.status.value.startswith("calculated")
    )
    if not selected:
        publish_unchanged_target(job.target, job.directory / "result.xlsx", job.target_digest)
        return job.directory / "result.xlsx", _feedback_records(state)
    result = write_target_report(
        job.target, job.directory / "result.xlsx", WriteDecision.ALLOW_WRITE, selected, schema
    )
    if getattr(result, "output_sha256", None) is None:
        raise RuntimeError("authoritative workbook write was not verified")
    return job.directory / "result.xlsx", _feedback_records(state)


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
        by_index[index, key] = target
    return _Catalog(labels, by_index)


def _sources(job) -> ReconciliationSourceBatch:
    from .reconciliation_sources import (
        ReconciliationSourceDescriptor,
        descriptor_from_upload_basename,
        extract_reconciliation_sources,
    )

    paths = job.sources or (job.source,)
    names = tuple(getattr(job, "source_names", ()) or ())
    descriptors = (
        tuple(descriptor_from_upload_basename(name) for name in names)
        if len(names) == len(paths)
        else tuple(ReconciliationSourceDescriptor(path.name) for path in paths)
    )
    workbooks = tuple(
        (path, f"source:{index}:{job.source_digests[index]}", descriptor)
        for index, (path, descriptor) in enumerate(zip(paths, descriptors, strict=True))
    )
    return extract_reconciliation_sources(workbooks, require_document_index=True)


def _review_rows(rows, targets, catalog: _Catalog, job) -> tuple[ReviewRow, ...]:
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
                and _source_index(candidate.source_row.source_filename) == target_index
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


def _available_categories(rows, catalog: _Catalog, job) -> dict[str, frozenset[str]]:
    by_index: dict[str, set[str]] = {}
    for index, category in catalog.targets:
        by_index.setdefault(index, set()).add(category)
    return {
        _review_row_id(job, row.source_row_id): frozenset(
            by_index.get(_source_index(row.source_filename) or "", set())
        )
        for row in rows
    }


def _group_category_availability(groups, rows, catalog: _Catalog, job) -> dict[str, frozenset[str]]:
    available = _available_categories(rows, catalog, job)
    return {
        group.group_id: frozenset.intersection(
            *(available.get(row_id, frozenset()) for row_id in group.member_ids)
        )
        for group in groups
    }


def _catalog_version(catalog: _Catalog) -> str:
    return sha256(
        json.dumps(
            sorted(catalog.labels.items()), ensure_ascii=False, separators=(",", ":")
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


def _selected_matches(state, overrides, catalog: _Catalog, job, source_rows):
    buckets: dict[str, tuple[object, list[MatchCandidate]]] = {}
    for row_id, override in sorted(overrides.items()):
        if override.action is None or override.target_category is None:
            continue
        source = source_rows[row_id]
        index = _source_index(source.source_filename)
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


def _source_index(filename: str) -> str | None:
    from .reconciliation_sources import document_index_from_basename

    index = extract_document_index(filename).value
    return index.main if index is not None else document_index_from_basename(filename)


def _target_id(job, target) -> str:
    return _hash(
        "target",
        "MatchingContract-12.0",
        f"target:{job.target_digest}",
        f"sha256:{job.target_digest}",
        target.sheet_name,
        target.row_number,
    )


def _review_row_id(job, source_row_id: str) -> str:
    return (
        "review-row-"
        + _hash(
            "ReconciliationReviewRow-1.0",
            job.target_digest,
            *job.source_digests,
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


def _feedback_records(state) -> tuple[FeedbackRecord, ...]:
    from report_processor.reconciliation_review import (
        feedback_from_decision,
        feedback_from_row_decision,
    )

    groups = state.groups
    values = [
        feedback_from_decision(groups[key], decision, sequence=index)
        for index, (key, decision) in enumerate(sorted(state.group_decisions.items()), 1)
    ]
    values.extend(
        feedback_from_row_decision(state.rows[key], decision, sequence=index)
        for index, (key, decision) in enumerate(
            sorted(state.row_decisions.items()), len(values) + 1
        )
    )
    return tuple(values)

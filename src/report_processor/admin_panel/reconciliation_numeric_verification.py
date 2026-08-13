"""Exact, private numeric oracle for reconciliation verification."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from report_processor.calculation import CalculationError, calculate_matches
from report_processor.normalization.models import TypoDictionaries
from report_processor.normalization.normalizers import normalize_unit
from report_processor.reconciliation_review import (
    AppliedOverride,
    ReviewAction,
    ReviewDecision,
    ReviewMode,
)

from .reconciliation_execution import _catalog, _review_row_id, _selected_matches
from .reconciliation_target import category_id, read_reconciliation_target, writer_calculations


class NumericVerificationFailure(RuntimeError):
    """A controlled condition which makes a numeric verdict unavailable."""


def verify_numeric(job, review) -> tuple[frozenset[str], int]:
    """Return failing review rows after replaying the authoritative writer path.

    Safe and accepted decisions select only a category/mode.  They do not make
    a source row pass until its writer-quantized contribution equals J/K.
    """

    state = review.state
    assert state is not None and review.source_batch is not None
    source_digests = _source_digests_by_filename(job)
    _reject_duplicate_source_identities(review.source_batch.rows, source_digests)
    try:
        _schema, targets = read_reconciliation_target(job.target, job.target_digest, job.stage)
        _reject_duplicate_target_keys(targets)
        catalog = _catalog(targets)
    except NumericVerificationFailure:
        raise
    except ValueError as error:
        raise NumericVerificationFailure("VERIFICATION_TARGET_BINDING_AMBIGUOUS") from error
    source_rows = {_review_row_id(job, row.source_row_id): row for row in review.source_batch.rows}
    if len(source_rows) != len(review.source_batch.rows) or not set(state.rows).issubset(
        source_rows
    ):
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")

    authorizations = _authorizations(state)
    failed = set(state.rows) - set(authorizations)
    accepted = {
        row_id: authorization
        for row_id, authorization in authorizations.items()
        if authorization.action is ReviewAction.ACCEPT
    }
    failed.update(set(authorizations) - set(accepted))
    if not accepted:
        return frozenset(failed), len(state.rows)

    overrides = {
        row_id: AppliedOverride(
            row_id,
            decision.target_category,
            decision.mode is ReviewMode.QUANTITY_COST,
            True,
            ReviewAction.ACCEPT,
        )
        for row_id, decision in accepted.items()
    }
    try:
        _validate_units(overrides, source_rows, catalog, job)
        matches = _selected_matches(state, overrides, catalog, job, source_rows)
        calculations = calculate_matches(
            matches, _rule_set(job), _candidate_inclusions(overrides, matches)
        )
    except NumericVerificationFailure:
        raise
    except (CalculationError, ValueError) as error:
        raise NumericVerificationFailure("VERIFICATION_CALCULATION_UNAVAILABLE") from error
    if any(not item.status.value.startswith("calculated") for item in calculations):
        raise NumericVerificationFailure("VERIFICATION_CALCULATION_UNAVAILABLE")
    written = writer_calculations(calculations)
    candidate_rows = _candidate_review_rows(matches, accepted)
    for calculation in written:
        row_ids = {
            _contribution_review_row_id(contribution, candidate_rows)
            for contribution in calculation.trace.contributions
        }
        modes = {accepted[row_id].mode for row_id in row_ids}
        if len(modes) != 1:
            raise NumericVerificationFailure("VERIFICATION_CATEGORY_AMBIGUOUS")
        if not _matches_target(calculation, next(iter(modes))):
            failed.update(row_ids)
    return frozenset(failed), len(state.rows)


def _candidate_review_rows(matches, accepted) -> dict[str, str]:
    """Bind calculation contributions back to opaque review-row identities."""

    values: dict[str, str] = {}
    for match in matches:
        for candidate in match.effective_selected_candidates:
            candidate_id = getattr(candidate, "candidate_id", None)
            row_id = getattr(candidate, "source_row_id", None)
            if (
                not isinstance(candidate_id, str)
                or not candidate_id
                or not isinstance(row_id, str)
                or row_id not in accepted
                or candidate_id in values
            ):
                raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
            values[candidate_id] = row_id
    if not values:
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
    return values


def _contribution_review_row_id(contribution, candidate_rows: dict[str, str]) -> str:
    candidate_id = getattr(contribution, "candidate_id", None)
    row_id = candidate_rows.get(candidate_id) if isinstance(candidate_id, str) else None
    if row_id is None:
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
    return row_id


def _authorizations(state) -> dict[str, ReviewDecision]:
    """Resolve explicit decisions first; safe packages supply only missing rows."""

    group_by_row = {
        row_id: group.group_id for group in state.groups.values() for row_id in group.member_ids
    }
    resolved: dict[str, ReviewDecision] = {}
    for decision in state.effective_decisions():
        if decision.row_id is not None:
            resolved[decision.row_id] = decision
        elif decision.group_id is not None:
            for row_id, group_id in group_by_row.items():
                if group_id == decision.group_id:
                    resolved[row_id] = decision
    for package in getattr(state.grouping, "packages", ()):
        if not package.safe:
            continue
        try:
            category, mode = package.package_key[:2]
            decision_mode = ReviewMode(mode)
        except (AttributeError, TypeError, ValueError):
            raise NumericVerificationFailure("VERIFICATION_CATEGORY_AMBIGUOUS") from None
        if not category:
            raise NumericVerificationFailure("VERIFICATION_CATEGORY_AMBIGUOUS")
        for group_id in package.member_group_ids:
            for row_id, member_group_id in group_by_row.items():
                if member_group_id == group_id:
                    resolved.setdefault(
                        row_id,
                        ReviewDecision(
                            ReviewAction.ACCEPT,
                            decision_mode,
                            category,
                            group_id=group_id,
                        ),
                    )
    return resolved


def _rule_set(job):
    from report_processor.business_rules import load_default_rule_set, load_rule_configuration

    validation = (
        load_rule_configuration(job.rules_path)
        if getattr(job, "rules_path", None)
        else load_default_rule_set()
    )
    if not validation.valid or validation.rule_set is None:
        raise NumericVerificationFailure("VERIFICATION_RULE_CONFIGURATION_INVALID")
    return validation.rule_set


def _candidate_inclusions(overrides, matches) -> dict[str, tuple[bool, bool]]:
    values = {}
    for match in matches:
        for candidate in match.effective_selected_candidates:
            override = overrides.get(candidate.source_row_id)
            if override is None:
                raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
            values[candidate.candidate_id] = override.candidate_inclusion
    return values


def _validate_units(overrides, source_rows, catalog, job) -> None:
    dictionaries = TypoDictionaries()
    for row_id, override in overrides.items():
        if not override.include_quantity:
            continue
        source = source_rows[row_id]
        index = _source_index(source.source_filename)
        target = catalog.targets.get((index or "", override.target_category or ""))
        source_unit = normalize_unit(source.unit, dictionaries)
        target_unit = normalize_unit(target.unit, dictionaries) if target is not None else None
        if target is None or source_unit is None or target_unit is None:
            raise NumericVerificationFailure("VERIFICATION_UNIT_UNAVAILABLE")
        if source_unit != target_unit:
            raise NumericVerificationFailure("VERIFICATION_UNIT_MISMATCH")


def _matches_target(calculation, mode: ReviewMode) -> bool:
    target_cost = _finite_target_value(calculation.target_row.selected_cost)
    if target_cost is None:
        raise NumericVerificationFailure("VERIFICATION_TARGET_VALUE_UNAVAILABLE")
    if (
        calculation.cost is None
        or not isinstance(calculation.cost, Decimal)
        or not calculation.cost.is_finite()
        or calculation.cost != target_cost
    ):
        return False
    if mode is ReviewMode.COST_ONLY:
        return True
    target_quantity = _finite_target_value(calculation.target_row.selected_quantity)
    if target_quantity is None:
        raise NumericVerificationFailure("VERIFICATION_TARGET_VALUE_UNAVAILABLE")
    return (
        isinstance(calculation.quantity, Decimal)
        and calculation.quantity.is_finite()
        and calculation.quantity == target_quantity
    )


def _finite_target_value(cell) -> Decimal | None:
    value = getattr(cell, "value", None)
    if not isinstance(value, Decimal) or not value.is_finite():
        return None
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _reject_duplicate_target_keys(targets) -> None:
    keys: set[tuple[str, str]] = set()
    for target in targets:
        key = (
            _terminal_index(target.document_index_normalized),
            category_id(target.work_name or ""),
        )
        if not all(key) or key in keys:
            raise NumericVerificationFailure("VERIFICATION_TARGET_BINDING_AMBIGUOUS")
        keys.add(key)


def _source_digests_by_filename(job) -> dict[str, str]:
    names = tuple(getattr(job, "source_names", ()) or ())
    digests = tuple(getattr(job, "source_digests", ()) or ())
    if len(names) != len(digests) or not names or len(set(names)) != len(names):
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
    if any(not isinstance(digest, str) or not digest.strip() for digest in digests):
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")
    return dict(zip(names, digests, strict=True))


def _reject_duplicate_source_identities(rows, source_digests: dict[str, str]) -> None:
    try:
        identities = [
            (
                source_digests[row.source_filename].strip().casefold(),
                row.source_sheet,
                row.source_row_number,
            )
            for row in rows
        ]
    except (AttributeError, KeyError):
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS") from None
    if len(identities) != len(set(identities)):
        raise NumericVerificationFailure("VERIFICATION_SOURCE_IDENTITY_AMBIGUOUS")


def _source_index(filename: str) -> str | None:
    from .reconciliation_execution import _source_index as source_index

    return source_index(filename)


def _terminal_index(value) -> str | None:
    from .reconciliation_target import terminal_index

    return terminal_index(value)

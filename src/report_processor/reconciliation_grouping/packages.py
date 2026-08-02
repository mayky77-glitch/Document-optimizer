"""Safe deterministic semantic families and global decision packages."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping

from report_processor.reconciliation_review.models import ReviewGroup, ReviewMode, ReviewRow

from .constraints import normalize_negative_pairs, validate_hard_constraints
from .features import extract_all
from .models import (
    PACKAGE_CONTRACT_VERSION,
    DecisionPackage,
    FeatureVector,
    GroupingException,
    GroupingResult,
    GroupInput,
    PackageVersionContext,
    SemanticFamily,
)
from .semantic_model import LocalSemanticAssist, SemanticAssistResult
from .zero_activity import partition_rows


def build_reconciliation_packages(
    rows: Iterable[ReviewRow],
    groups: Iterable[ReviewGroup],
    *,
    modes: Mapping[str, ReviewMode] | None = None,
    category_availability: Mapping[str, frozenset[str]] | None = None,
    negative_pairs: Iterable[tuple[str, str]] = (),
    version_context: PackageVersionContext,
) -> GroupingResult:
    """Build deterministic packages after zero rows are excluded from review groups.

    Use ``rank_with_local_assist`` after this function when optional local ranking
    is wanted. It cannot influence this authoritative result.
    """
    partition = partition_rows(rows)
    inputs = _group_inputs(
        partition.visible_rows,
        groups,
        modes=modes or {},
        category_availability=category_availability or {},
    )
    features = extract_all(
        inputs,
        feature_contract_version=version_context.feature_contract_version,
        rule_version=version_context.rule_version,
    )
    inputs_by_id = {item.group.group_id: item for item in inputs}
    exceptions = validate_hard_constraints(
        features,
        inputs_by_id,
        negative_pairs=normalize_negative_pairs(negative_pairs),
    )
    families = _build_families(features, exceptions, version_context=version_context)
    packages = _build_packages(families, version_context=version_context)
    return GroupingResult(
        partition=partition,
        version_context=version_context,
        features=features,
        families=families,
        packages=packages,
        exceptions=exceptions,
    )


def rank_with_local_assist(
    result: GroupingResult, semantic_assist: LocalSemanticAssist | None
) -> SemanticAssistResult:
    """Expose optional rankings separately so they cannot affect package membership."""
    if semantic_assist is None:
        return SemanticAssistResult(unavailable_reason="local_model_not_configured")
    return semantic_assist.rank(result.features)


def _group_inputs(
    visible_rows: tuple[ReviewRow, ...],
    groups: Iterable[ReviewGroup],
    *,
    modes: Mapping[str, ReviewMode],
    category_availability: Mapping[str, frozenset[str]],
) -> tuple[GroupInput, ...]:
    rows_by_id = {row.row_id: row for row in visible_rows}
    group_values = tuple(groups)
    if len({group.group_id for group in group_values}) != len(group_values):
        raise ValueError("review groups must have unique IDs")
    if set(rows_by_id) != {row.row_id for row in visible_rows}:
        raise ValueError("visible review rows must have unique IDs")
    inputs: list[GroupInput] = []
    seen_rows: set[str] = set()
    for group in sorted(group_values, key=lambda value: value.group_id):
        if any(row_id not in rows_by_id for row_id in group.member_ids):
            raise ValueError("zero-activity rows must be filtered before review grouping")
        if seen_rows.intersection(group.member_ids):
            raise ValueError("a visible row cannot belong to multiple ReviewGroups")
        seen_rows.update(group.member_ids)
        group_rows = tuple(rows_by_id[row_id] for row_id in group.member_ids)
        inputs.append(
            GroupInput(
                group=group,
                rows=group_rows,
                mode=modes.get(group.group_id, _default_mode(group_rows)),
                available_categories=category_availability.get(group.group_id),
            )
        )
    if seen_rows != set(rows_by_id):
        raise ValueError("every visible row must belong to one ReviewGroup")
    return tuple(inputs)


def _default_mode(rows: tuple[ReviewRow, ...]) -> ReviewMode:
    return (
        ReviewMode.QUANTITY_COST
        if any(row.quantity is not None and row.quantity != 0 for row in rows)
        else ReviewMode.COST_ONLY
    )


def _build_families(
    features: tuple[FeatureVector, ...],
    exceptions: tuple[GroupingException, ...],
    *,
    version_context: PackageVersionContext,
) -> tuple[SemanticFamily, ...]:
    reasons_by_group: dict[str, set[str]] = defaultdict(set)
    for exception in exceptions:
        for group_id in exception.group_ids:
            reasons_by_group[group_id].add(exception.reason)
    exception_group_ids = {group_id for exception in exceptions for group_id in exception.group_ids}
    grouped: dict[tuple[object, ...], list[FeatureVector]] = defaultdict(list)
    for feature in features:
        key = feature.family_key
        if feature.group_id in exception_group_ids:
            key = (*key, "explicit-exception", feature.group_id)
        grouped[key].append(feature)
    families: list[SemanticFamily] = []
    for key, members in sorted(grouped.items(), key=lambda item: repr(item[0])):
        member_ids = tuple(sorted(feature.group_id for feature in members))
        reasons = tuple(
            sorted({reason for group_id in member_ids for reason in reasons_by_group[group_id]})
        )
        member_versions = tuple(
            f"{feature.group_id}:{feature.group_version}"
            for feature in sorted(members, key=lambda feature: feature.group_id)
        )
        version = _digest(
            PACKAGE_CONTRACT_VERSION,
            version_context.fingerprint,
            *member_ids,
            *member_versions,
            repr(key),
        )
        families.append(
            SemanticFamily(
                family_id=f"reconciliation-family-{version[:24]}",
                version=version,
                package_key=members[0].package_key,
                member_group_ids=member_ids,
                exception_reasons=reasons,
            )
        )
    return tuple(sorted(families, key=lambda family: family.family_id))


def _build_packages(
    families: tuple[SemanticFamily, ...], *, version_context: PackageVersionContext
) -> tuple[DecisionPackage, ...]:
    grouped: dict[tuple[object, ...], list[SemanticFamily]] = defaultdict(list)
    for family in families:
        has_known_work_type = bool(family.package_key[3] and family.package_key[4])
        key: tuple[object, ...] = (*family.package_key, "safe")
        if not has_known_work_type:
            key = (*family.package_key, "unknown", family.family_id)
        elif family.exception_reasons:
            key = (*family.package_key, "manual")
        grouped[key].append(family)
    packages: list[DecisionPackage] = []
    for _key, members in sorted(grouped.items(), key=lambda item: repr(item[0])):
        key = members[0].package_key
        family_ids = tuple(sorted(family.family_id for family in members))
        group_ids = tuple(
            sorted(group_id for family in members for group_id in family.member_group_ids)
        )
        reasons = tuple(
            sorted({reason for family in members for reason in family.exception_reasons})
        )
        version = _digest(
            PACKAGE_CONTRACT_VERSION,
            version_context.fingerprint,
            *family_ids,
            *group_ids,
        )
        packages.append(
            DecisionPackage(
                package_id=f"reconciliation-package-{version[:24]}",
                version=version,
                package_key=key,
                family_ids=family_ids,
                member_group_ids=group_ids,
                safe=bool(key[0] and key[3] and key[4]) and not reasons,
                exception_reasons=reasons,
            )
        )
    return tuple(sorted(packages, key=lambda package: package.package_id))


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()

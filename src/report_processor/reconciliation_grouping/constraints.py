"""Hard package constraints that always run before any semantic assistance."""

from __future__ import annotations

from collections.abc import Iterable

from .models import FeatureVector, GroupingException, GroupInput

_INCOMPATIBLE = frozenset(
    {
        frozenset({"installation", "cost"}),
        frozenset({"installation", "testing"}),
        frozenset({"laying", "testing"}),
        frozenset({"installation", "dismantling"}),
        frozenset({"power", "low_current"}),
    }
)


def unavailable_category_exception(item: GroupInput) -> GroupingException | None:
    """Reject a group before package construction if its category is unavailable."""
    category = item.group.proposed_category
    if (
        category
        and item.available_categories is not None
        and category not in item.available_categories
    ):
        return GroupingException((item.group.group_id,), "category_unavailable")
    return None


def hard_conflict(
    left: FeatureVector,
    right: FeatureVector,
    *,
    negative_pairs: frozenset[tuple[str, str]],
) -> str | None:
    """Return a stable conflict reason or ``None`` when two groups may share a family."""
    if tuple(sorted((left.group_id, right.group_id))) in negative_pairs:
        return "explicit_negative_feedback"
    if left.category != right.category:
        return "category_mismatch"
    if left.mode is not right.mode:
        return "accounting_mode_mismatch"
    if left.unit_family is not right.unit_family:
        return "unit_family_mismatch"
    labels = set(left.critical_modifiers) | set(left.negative_markers)
    labels.update(right.critical_modifiers)
    labels.update(right.negative_markers)
    labels.update(value for value in (left.action, right.action) if value)
    for pair in _INCOMPATIBLE:
        if pair <= labels:
            return "hard_" + "_vs_".join(sorted(pair))
    if left.action != right.action or left.object_kind != right.object_kind:
        return None
    if left.critical_modifiers != right.critical_modifiers:
        return "critical_modifier_mismatch"
    if left.typed_modifiers != right.typed_modifiers:
        return "typed_modifier_mismatch"
    return None


def validate_hard_constraints(
    features: Iterable[FeatureVector],
    items_by_id: dict[str, GroupInput],
    *,
    negative_pairs: frozenset[tuple[str, str]],
) -> tuple[GroupingException, ...]:
    """Return all deterministic per-group and pair exceptions in stable order."""
    materialized = tuple(sorted(features, key=lambda feature: feature.group_id))
    exceptions = [
        exception
        for feature in materialized
        if (exception := unavailable_category_exception(items_by_id[feature.group_id])) is not None
    ]
    by_boundary: dict[tuple[str, str, str, str, str], list[FeatureVector]] = {}
    for feature in materialized:
        by_boundary.setdefault(feature.package_key, []).append(feature)
    for boundary in by_boundary.values():
        for index, left in enumerate(boundary):
            for right in boundary[index + 1 :]:
                reason = hard_conflict(left, right, negative_pairs=negative_pairs)
                if reason:
                    exceptions.append(GroupingException((left.group_id, right.group_id), reason))
    return tuple(sorted(set(exceptions), key=lambda value: (value.group_ids, value.reason)))


def normalize_negative_pairs(pairs: Iterable[tuple[str, str]]) -> frozenset[tuple[str, str]]:
    """Normalize externally supplied feedback pairs without accepting self-pairs."""
    normalized: set[tuple[str, str]] = set()
    for left, right in pairs:
        if not left or not right or left == right:
            raise ValueError("negative feedback pairs require two distinct group IDs")
        normalized.add(tuple(sorted((left, right))))
    return frozenset(normalized)

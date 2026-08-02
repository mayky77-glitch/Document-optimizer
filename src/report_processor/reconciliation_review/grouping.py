"""Deterministic, conservative grouping across all reconciliation uploads."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable

from .models import ReviewGroup, ReviewRow

_SPACE_RE = re.compile(r"\s+")
_SUFFIX_RE = re.compile(r"\s+(?:\([^)]*\)|[-–—:]\s*[^\s].*)$")


def normalize_name(value: str | None) -> str:
    """Normalize user-visible names without trying to infer synonyms."""
    return _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", value or "").casefold()).strip()


def normalize_unit(value: str | None) -> str | None:
    normalized = normalize_name(value).replace(".", "")
    return normalized or None


def build_review_groups(rows: Iterable[ReviewRow]) -> tuple[ReviewGroup, ...]:
    """Group exact names, then only observed complete-name prefix variants.

    A prefix is admissible only when it is itself an uploaded complete name and
    every longer member has a clearly-delimited terminal qualifier. This avoids
    broad grouping from generic opening words while supporting harmless variants.
    """
    materialized = tuple(rows)
    _ensure_unique_ids(materialized)
    by_exact: dict[tuple[str, str | None], list[ReviewRow]] = defaultdict(list)
    empty_rows: list[ReviewRow] = []
    for row in materialized:
        name = normalize_name(row.display_name)
        if not name:
            empty_rows.append(row)
        else:
            by_exact[name, normalize_unit(row.unit)].append(row)

    grouped: list[tuple[str | None, str | None, tuple[ReviewRow, ...]]] = []
    for (name, unit), members in sorted(by_exact.items(), key=_exact_group_sort_key):
        grouped.append((name, unit, tuple(members)))
    grouped = _merge_complete_prefix_groups(grouped)
    grouped.extend((None, normalize_unit(row.unit), (row,)) for row in empty_rows)
    return tuple(
        _review_group(name, unit, members)
        for name, unit, members in sorted(grouped, key=_group_sort_key)
    )


def _merge_complete_prefix_groups(
    groups: list[tuple[str | None, str | None, tuple[ReviewRow, ...]]],
) -> list[tuple[str | None, str | None, tuple[ReviewRow, ...]]]:
    pending = list(groups)
    merged: list[tuple[str | None, str | None, tuple[ReviewRow, ...]]] = []
    while pending:
        name, unit, members = pending.pop(0)
        assert name is not None
        compatible = [item for item in pending if item[1] == unit and _is_variant(name, item[0])]
        if compatible:
            pending = [item for item in pending if item not in compatible]
            members = (*members, *(row for _n, _u, part in compatible for row in part))
        merged.append((name, unit, tuple(members)))
    return merged


def _exact_group_sort_key(
    item: tuple[tuple[str, str | None], list[ReviewRow]],
) -> tuple[str, str]:
    (name, unit), _members = item
    return name, unit or ""


def _group_sort_key(
    item: tuple[str | None, str | None, tuple[ReviewRow, ...]],
) -> tuple[bool, str, str, tuple[str, ...]]:
    name, unit, members = item
    return name is None, name or "", unit or "", tuple(sorted(row.row_id for row in members))


def _is_variant(base: str, candidate: str | None) -> bool:
    if candidate is None or not candidate.startswith(base):
        return False
    suffix = candidate[len(base) :]
    return bool(_SUFFIX_RE.fullmatch(suffix))


def _review_group(
    name: str | None, unit: str | None, members: tuple[ReviewRow, ...]
) -> ReviewGroup:
    member_ids = tuple(sorted(row.row_id for row in members))
    category_values = {row.proposed_category for row in members if row.proposed_category}
    category = next(iter(category_values)) if len(category_values) == 1 else None
    fingerprint = _digest(name or "", unit or "", *member_ids)
    return ReviewGroup(
        group_id=f"reconciliation-group-{fingerprint[:24]}",
        version=fingerprint,
        normalized_name=name,
        normalized_unit=unit,
        member_ids=member_ids,
        proposed_category=category,
    )


def _digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _ensure_unique_ids(rows: tuple[ReviewRow, ...]) -> None:
    if len({row.row_id for row in rows}) != len(rows):
        raise ValueError("review rows must have unique row_id values")

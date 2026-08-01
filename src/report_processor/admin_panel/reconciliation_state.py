"""Job-local, optimistic-concurrency state for reconciliation review."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from report_processor.reconciliation_review import ReviewDecision, ReviewGroup, ReviewRow


@dataclass(slots=True)
class ReconciliationReviewState:
    """Keep only controlled decisions; source workbooks remain the authority."""

    rows: dict[str, ReviewRow]
    groups: dict[str, ReviewGroup]
    categories: Mapping[str, str]
    source_digests: tuple[str, ...]
    target_digest: str
    group_decisions: dict[str, ReviewDecision] = field(default_factory=dict)
    row_decisions: dict[str, ReviewDecision] = field(default_factory=dict)

    def group_snapshot(self) -> tuple[ReviewGroup, ...]:
        return tuple(
            replace(group, version=self._version(group))
            for group in sorted(self.groups.values(), key=lambda item: item.group_id)
        )

    def put_group(self, group_id: str, decision: ReviewDecision) -> None:
        group = self._group(group_id, decision.version)
        self._validate_decision(decision, group_id=group.group_id)
        self.group_decisions[group_id] = replace(decision, group_id=group_id, row_id=None)

    def put_row(self, row_id: str, decision: ReviewDecision) -> None:
        self._row_group(row_id, decision.version)
        self._validate_decision(decision, row_id=row_id)
        self.row_decisions[row_id] = replace(decision, group_id=None, row_id=row_id)

    def delete_row(self, row_id: str, version: str) -> None:
        self._row_group(row_id, version)
        self.row_decisions.pop(row_id, None)

    def effective_decisions(self) -> tuple[ReviewDecision, ...]:
        versions = {group.group_id: group.version for group in self.group_snapshot()}
        groups_by_row = {
            row_id: group.group_id for group in self.groups.values() for row_id in group.member_ids
        }
        values = [
            replace(decision, version=versions[group_id])
            for group_id, decision in sorted(self.group_decisions.items())
        ]
        values.extend(
            replace(decision, version=versions[groups_by_row[row_id]])
            for row_id, decision in sorted(self.row_decisions.items())
        )
        return tuple(values)

    def core_decisions(self) -> tuple[ReviewDecision, ...]:
        """Translate opaque client versions back to the frozen core group versions."""
        group_by_row = {
            row_id: group for group in self.groups.values() for row_id in group.member_ids
        }
        values = [
            replace(decision, version=self.groups[group_id].version)
            for group_id, decision in sorted(self.group_decisions.items())
        ]
        values.extend(
            replace(decision, version=group_by_row[row_id].version)
            for row_id, decision in sorted(self.row_decisions.items())
        )
        return tuple(values)

    def unresolved_row_ids(self) -> tuple[str, ...]:
        """Return source rows lacking either a group or a row decision."""
        resolved = set(self.row_decisions)
        for group_id in self.group_decisions:
            resolved.update(self.groups[group_id].member_ids)
        return tuple(sorted(set(self.rows) - resolved))

    def unresolved_groups(self) -> tuple[ReviewGroup, ...]:
        """Return only cards that still contain a row requiring an operator choice."""
        unresolved = set(self.unresolved_row_ids())
        return tuple(
            group for group in self.group_snapshot() if unresolved.intersection(group.member_ids)
        )

    def _group(self, group_id: str, version: str | None) -> ReviewGroup:
        group = self.groups.get(group_id)
        if group is None or version != self._version(group):
            raise ValueError("review version is stale")
        return group

    def _row_group(self, row_id: str, version: str | None) -> ReviewGroup:
        if row_id not in self.rows:
            raise ValueError("unknown review row")
        group = next((item for item in self.groups.values() if row_id in item.member_ids), None)
        if group is None or version != self._version(group):
            raise ValueError("review version is stale")
        return group

    def _validate_decision(
        self, decision: ReviewDecision, *, group_id: str | None = None, row_id: str | None = None
    ) -> None:
        category_id = decision.target_category
        if decision.action.value == "accept" and category_id not in self.categories:
            raise ValueError("unknown target category")
        if group_id is not None and decision.group_id not in {None, group_id}:
            raise ValueError("group identity does not match route")
        if row_id is not None and decision.row_id not in {None, row_id}:
            raise ValueError("row identity does not match route")

    def _version(self, group: ReviewGroup) -> str:
        payload = {
            "contract": "ReconciliationAuthoritativeAdmin-1.0",
            "sources": self.source_digests,
            "target": self.target_digest,
            "group": group.group_id,
            "members": group.member_ids,
            "catalog": sorted(self.categories),
            "groups": _decisions(self.group_decisions),
            "rows": _decisions(self.row_decisions),
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


def _decisions(
    values: Mapping[str, ReviewDecision],
) -> list[tuple[str, str, str | None, str | None]]:
    return [
        (key, value.action.value, value.mode.value if value.mode else None, value.target_category)
        for key, value in sorted(values.items())
    ]

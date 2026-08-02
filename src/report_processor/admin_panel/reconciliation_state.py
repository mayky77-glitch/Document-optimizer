"""Job-local, optimistic-concurrency state for reconciliation review."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from report_processor.reconciliation_grouping import DecisionPackage, GroupingResult, SemanticFamily
from report_processor.reconciliation_review import (
    ReviewAction,
    ReviewDecision,
    ReviewGroup,
    ReviewMode,
    ReviewRow,
)


@dataclass(frozen=True, slots=True)
class BatchReviewDecision:
    """Controlled decision shared by a package or semantic family."""

    action: ReviewAction
    mode: ReviewMode | None = None
    target_category: str | None = None
    version: str | None = None

    def __post_init__(self) -> None:
        if self.action is ReviewAction.ACCEPT:
            if (
                self.mode is None
                or not isinstance(self.target_category, str)
                or not self.target_category
            ):
                raise ValueError("an accepted decision needs a mode and target category")
        elif self.mode is not None or self.target_category is not None:
            raise ValueError("a rejected decision cannot carry category or mode")


@dataclass(frozen=True, slots=True)
class _DecisionSnapshot:
    packages: dict[str, BatchReviewDecision]
    families: dict[str, BatchReviewDecision]
    groups: dict[str, ReviewDecision]
    rows: dict[str, ReviewDecision]


@dataclass(slots=True)
class ReconciliationReviewState:
    """Keep controlled decisions separate from the source workbook and calculation path."""

    rows: dict[str, ReviewRow]
    groups: dict[str, ReviewGroup]
    categories: Mapping[str, str]
    source_digests: tuple[str, ...]
    target_digest: str
    available_categories: Mapping[str, frozenset[str]] = field(default_factory=dict)
    grouping: GroupingResult | None = None
    group_decisions: dict[str, ReviewDecision] = field(default_factory=dict)
    row_decisions: dict[str, ReviewDecision] = field(default_factory=dict)
    package_decisions: dict[str, BatchReviewDecision] = field(default_factory=dict)
    family_decisions: dict[str, BatchReviewDecision] = field(default_factory=dict)
    familiar_group_ids: set[str] = field(default_factory=set)
    last_action: str | None = None
    _undo: _DecisionSnapshot | None = None
    _autosave: Callable[[ReconciliationReviewState], None] | None = None

    def set_autosave(self, callback: Callable[[ReconciliationReviewState], None]) -> None:
        self._autosave = callback

    @property
    def version_fingerprint(self) -> str:
        payload = {
            "sources": self.source_digests,
            "target": self.target_digest,
            "categories": sorted(self.categories),
            "packages": [(item.package_id, item.version) for item in self._packages()],
            "families": [(item.family_id, item.version) for item in self._families()],
            "groups": [(item.group_id, item.version) for item in self.groups.values()],
        }
        return _digest(payload)

    def group_snapshot(self) -> tuple[ReviewGroup, ...]:
        return tuple(
            replace(group, version=self._version(group))
            for group in sorted(self.groups.values(), key=lambda item: item.group_id)
        )

    def put_package(self, package_id: str, decision: BatchReviewDecision) -> None:
        package = self._package(package_id, decision.version)
        self._validate_batch_decision(decision, package.member_group_ids)
        self._capture_undo()
        self.package_decisions[package_id] = replace(decision, version=package.version)
        self._changed("Решение для пакета сохранено.")

    def put_family(self, family_id: str, decision: BatchReviewDecision) -> None:
        family = self._family(family_id, decision.version)
        self._validate_batch_decision(decision, family.member_group_ids)
        self._capture_undo()
        self.family_decisions[family_id] = replace(decision, version=family.version)
        self._changed("Решение для семейства сохранено.")

    def accept_safe_packages(self, packages: Sequence[tuple[str, str]]) -> None:
        if not packages or len({item[0] for item in packages}) != len(packages):
            raise ValueError("safe packages must be a unique non-empty list")
        resolved = [self._package(package_id, version) for package_id, version in packages]
        if any(not package.safe for package in resolved):
            raise ValueError("only safe packages may be accepted together")
        decisions: dict[str, BatchReviewDecision] = {}
        for package in resolved:
            category, mode = package.package_key[0], package.package_key[1]
            if not category:
                raise ValueError("safe package has no proposed category")
            decisions[package.package_id] = BatchReviewDecision(
                ReviewAction.ACCEPT, ReviewMode(mode), category, package.version
            )
            self._validate_batch_decision(decisions[package.package_id], package.member_group_ids)
        self._capture_undo()
        self.package_decisions.update(decisions)
        self._changed("Безопасные пакеты приняты.")

    def put_group(self, group_id: str, decision: ReviewDecision) -> None:
        group = self._group(group_id, decision.version)
        self.validate_decision(decision, group_id=group.group_id)
        self._capture_undo()
        self.group_decisions[group_id] = replace(decision, group_id=group_id, row_id=None)
        self._changed("Решение для группы сохранено.")

    def put_row(self, row_id: str, decision: ReviewDecision) -> None:
        self._row_group(row_id, decision.version)
        self.validate_decision(decision, row_id=row_id)
        self._capture_undo()
        self.row_decisions[row_id] = replace(decision, group_id=None, row_id=row_id)
        self._changed("Решение для строки сохранено.")

    def delete_row(self, row_id: str, version: str) -> None:
        self._row_group(row_id, version)
        self._capture_undo()
        self.row_decisions.pop(row_id, None)
        self._changed("Решение для строки отменено.")

    def undo(self) -> None:
        if self._undo is None:
            raise ValueError("nothing to undo")
        previous = self._undo
        self.package_decisions = previous.packages
        self.family_decisions = previous.families
        self.group_decisions = previous.groups
        self.row_decisions = previous.rows
        self._undo = None
        self._changed("Последнее решение отменено.")

    def restore(
        self,
        *,
        package_decisions: Mapping[str, BatchReviewDecision],
        family_decisions: Mapping[str, BatchReviewDecision],
        group_decisions: Mapping[str, ReviewDecision],
        row_decisions: Mapping[str, ReviewDecision],
    ) -> None:
        """Restore an already fingerprint-checked private snapshot without creating undo history."""
        for package_id, decision in package_decisions.items():
            package = self._package(package_id, decision.version)
            self._validate_batch_decision(decision, package.member_group_ids)
        for family_id, decision in family_decisions.items():
            family = self._family(family_id, decision.version)
            self._validate_batch_decision(decision, family.member_group_ids)
        for group_id, decision in group_decisions.items():
            self._group(group_id, decision.version)
            self.validate_decision(decision, group_id=group_id)
        for row_id, decision in row_decisions.items():
            self._row_group(row_id, decision.version)
            self.validate_decision(decision, row_id=row_id)
        self.package_decisions = dict(package_decisions)
        self.family_decisions = dict(family_decisions)
        self.group_decisions = dict(group_decisions)
        self.row_decisions = dict(row_decisions)
        self.last_action = "Решения восстановлены."

    def effective_decisions(self) -> tuple[ReviewDecision, ...]:
        """Resolve package → family → group → row once, with the documented precedence."""
        group_values = self._resolved_group_decisions()
        versions = {group.group_id: group.version for group in self.group_snapshot()}
        groups_by_row = {
            row_id: group.group_id for group in self.groups.values() for row_id in group.member_ids
        }
        values = [
            replace(decision, version=versions[group_id])
            for group_id, decision in sorted(group_values.items())
        ]
        values.extend(
            replace(decision, version=versions[groups_by_row[row_id]])
            for row_id, decision in sorted(self.row_decisions.items())
        )
        return tuple(values)

    def core_decisions(self) -> tuple[ReviewDecision, ...]:
        """Translate client versions back to core group versions before ``apply_overrides``."""
        groups_by_row = {
            row_id: group for group in self.groups.values() for row_id in group.member_ids
        }
        values = [
            replace(decision, version=self.groups[group_id].version)
            for group_id, decision in sorted(self._resolved_group_decisions().items())
        ]
        values.extend(
            replace(decision, version=groups_by_row[row_id].version)
            for row_id, decision in sorted(self.row_decisions.items())
        )
        return tuple(values)

    def unresolved_row_ids(self) -> tuple[str, ...]:
        resolved_groups = self._resolved_group_decisions()
        resolved = set(self.row_decisions)
        for group_id in resolved_groups:
            resolved.update(self.groups[group_id].member_ids)
        return tuple(sorted(set(self.rows) - resolved))

    def unresolved_groups(self) -> tuple[ReviewGroup, ...]:
        unresolved = set(self.unresolved_row_ids())
        return tuple(
            group for group in self.group_snapshot() if unresolved.intersection(group.member_ids)
        )

    def package(self, package_id: str) -> DecisionPackage:
        return self._package(package_id, None)

    def family(self, family_id: str) -> SemanticFamily:
        return self._family(family_id, None)

    def _resolved_group_decisions(self) -> dict[str, ReviewDecision]:
        result: dict[str, ReviewDecision] = {}
        families = {item.family_id: item for item in self._families()}
        for package in self._packages():
            if (decision := self.package_decisions.get(package.package_id)) is not None:
                self._fanout(result, package.member_group_ids, decision)
        for family_id, decision in sorted(self.family_decisions.items()):
            self._fanout(result, families[family_id].member_group_ids, decision)
        result.update(self.group_decisions)
        return result

    @staticmethod
    def _fanout(
        destination: dict[str, ReviewDecision],
        group_ids: Iterable[str],
        decision: BatchReviewDecision,
    ) -> None:
        for group_id in group_ids:
            destination[group_id] = ReviewDecision(
                decision.action,
                decision.mode,
                decision.target_category,
                group_id=group_id,
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

    def _package(self, package_id: str, version: str | None) -> DecisionPackage:
        package = next((item for item in self._packages() if item.package_id == package_id), None)
        if package is None or (version is not None and version != package.version):
            raise ValueError("review version is stale")
        return package

    def _family(self, family_id: str, version: str | None) -> SemanticFamily:
        family = next((item for item in self._families() if item.family_id == family_id), None)
        if family is None or (version is not None and version != family.version):
            raise ValueError("review version is stale")
        return family

    def _packages(self) -> tuple[DecisionPackage, ...]:
        return self.grouping.packages if self.grouping is not None else ()

    def _families(self) -> tuple[SemanticFamily, ...]:
        return self.grouping.families if self.grouping is not None else ()

    def _validate_batch_decision(
        self, decision: BatchReviewDecision, group_ids: Iterable[str]
    ) -> None:
        if decision.action is not ReviewAction.ACCEPT:
            return
        assert decision.target_category is not None
        if decision.target_category not in self.categories:
            raise ValueError("unknown target category")
        member_ids = [
            row_id for group_id in group_ids for row_id in self.groups[group_id].member_ids
        ]
        if any(
            row_id in self.available_categories
            and decision.target_category not in self.available_categories[row_id]
            for row_id in member_ids
        ):
            raise ValueError("target category is unavailable for this package")

    def validate_decision(
        self, decision: ReviewDecision, *, group_id: str | None = None, row_id: str | None = None
    ) -> None:
        category_id = decision.target_category
        if decision.action is ReviewAction.ACCEPT and category_id not in self.categories:
            raise ValueError("unknown target category")
        if decision.action is ReviewAction.ACCEPT and group_id is not None:
            member_ids = self.groups[group_id].member_ids
            if any(
                member_id in self.available_categories
                and category_id not in self.available_categories[member_id]
                for member_id in member_ids
            ):
                raise ValueError("target category is unavailable for this group")
        if (
            decision.action is ReviewAction.ACCEPT
            and row_id is not None
            and row_id in self.available_categories
            and category_id not in self.available_categories[row_id]
        ):
            raise ValueError("target category is unavailable for this row")
        if group_id is not None and decision.group_id not in {None, group_id}:
            raise ValueError("group identity does not match route")
        if row_id is not None and decision.row_id not in {None, row_id}:
            raise ValueError("row identity does not match route")

    def _capture_undo(self) -> None:
        self._undo = _DecisionSnapshot(
            dict(self.package_decisions),
            dict(self.family_decisions),
            dict(self.group_decisions),
            dict(self.row_decisions),
        )

    def _changed(self, message: str) -> None:
        self.last_action = message
        if self._autosave is not None:
            self._autosave(self)

    def _version(self, group: ReviewGroup) -> str:
        payload = {
            "contract": "ReconciliationBatchDecision-1.0",
            "fingerprint": self.version_fingerprint,
            "group": group.group_id,
            "members": group.member_ids,
            "packages": _batch_decisions(self.package_decisions),
            "families": _batch_decisions(self.family_decisions),
            "groups": _decisions(self.group_decisions),
            "rows": _decisions(self.row_decisions),
        }
        return _digest(payload)


def _digest(payload: object) -> str:
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


def _batch_decisions(
    values: Mapping[str, BatchReviewDecision],
) -> list[tuple[str, str, str | None, str | None]]:
    return [
        (key, value.action.value, value.mode.value if value.mode else None, value.target_category)
        for key, value in sorted(values.items())
    ]

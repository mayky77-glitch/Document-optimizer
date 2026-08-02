"""Versioned, transport-neutral contracts for reconciliation package grouping."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from report_processor.reconciliation_review.models import ReviewGroup, ReviewMode, ReviewRow

FEATURE_CONTRACT_VERSION = "ReconciliationFeatureContract-1.0"
PACKAGE_CONTRACT_VERSION = "ReconciliationPackageContract-1.0"
FEATURE_RULE_VERSION = "reconciliation-features-1"


class UnitFamily(StrEnum):
    COUNT = "count"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    MASS = "mass"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class PackageVersionContext:
    """Immutable versions that stale a package whenever any consequential input changes."""

    source_digests: tuple[str, ...]
    target_digest: str
    category_catalog_version: str
    feature_contract_version: str = FEATURE_CONTRACT_VERSION
    rule_version: str = FEATURE_RULE_VERSION
    model_revision: str = "local-model-not-used"

    def __post_init__(self) -> None:
        if (
            not self.source_digests
            or tuple(sorted(set(self.source_digests))) != self.source_digests
        ):
            raise ValueError("source digests must be non-empty, unique and sorted")
        if any(not value.strip() for value in self.version_parts):
            raise ValueError("package version context values must not be empty")

    @property
    def version_parts(self) -> tuple[str, ...]:
        return (
            *self.source_digests,
            self.target_digest,
            self.category_catalog_version,
            self.feature_contract_version,
            self.rule_version,
            self.model_revision,
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256("\x1f".join(self.version_parts).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RowPartition:
    """Internal source rows split into the review-visible and hidden views."""

    source_rows: tuple[ReviewRow, ...]
    visible_rows: tuple[ReviewRow, ...]
    hidden_rows: tuple[ReviewRow, ...]

    def __post_init__(self) -> None:
        source_ids = tuple(row.row_id for row in self.source_rows)
        partition_ids = tuple(row.row_id for row in (*self.visible_rows, *self.hidden_rows))
        if (
            len(source_ids) != len(set(source_ids))
            or len(partition_ids) != len(source_ids)
            or set(source_ids) != set(partition_ids)
        ):
            raise ValueError("row partition must preserve every unique source row exactly once")


@dataclass(frozen=True, slots=True)
class GroupInput:
    """One existing review group plus controlled package-boundary facts."""

    group: ReviewGroup
    rows: tuple[ReviewRow, ...]
    mode: ReviewMode
    available_categories: frozenset[str] | None = None

    def __post_init__(self) -> None:
        member_ids = tuple(sorted(row.row_id for row in self.rows))
        if member_ids != self.group.member_ids:
            raise ValueError("group input rows must preserve exact ReviewGroup membership")
        if self.available_categories is not None and any(
            not category.strip() for category in self.available_categories
        ):
            raise ValueError("available categories must not contain empty values")


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Deterministic, versioned semantic facts for one exact review group."""

    group_id: str
    group_version: str
    normalized_name: str
    category: str | None
    mode: ReviewMode
    action: str | None
    object_kind: str | None
    critical_modifiers: tuple[str, ...]
    negative_markers: tuple[str, ...]
    typed_modifiers: tuple[str, ...]
    unit_family: UnitFamily
    token_ngrams: tuple[str, ...]
    feature_contract_version: str = FEATURE_CONTRACT_VERSION
    rule_version: str = FEATURE_RULE_VERSION

    @property
    def package_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.category or "",
            self.mode.value,
            self.unit_family.value,
            self.action or "",
            self.object_kind or "",
        )

    @property
    def family_key(self) -> tuple[object, ...]:
        base = (*self.package_key, self.critical_modifiers, self.typed_modifiers)
        # Unknown work types must not be broadly merged just because all fields are absent.
        return (*base, self.normalized_name) if not self.action or not self.object_kind else base


@dataclass(frozen=True, slots=True)
class GroupingException:
    """An explicit non-safe reason; it never changes source membership."""

    group_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.group_ids or tuple(sorted(set(self.group_ids))) != self.group_ids:
            raise ValueError("exception group IDs must be non-empty, unique and sorted")
        if not self.reason:
            raise ValueError("exception reason must not be empty")


@dataclass(frozen=True, slots=True)
class SemanticFamily:
    family_id: str
    version: str
    package_key: tuple[str, str, str, str, str]
    member_group_ids: tuple[str, ...]
    exception_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.family_id or not self.version or not self.member_group_ids:
            raise ValueError("family ID, version and members are required")
        if tuple(sorted(set(self.member_group_ids))) != self.member_group_ids:
            raise ValueError("family members must be unique and sorted")


@dataclass(frozen=True, slots=True)
class DecisionPackage:
    package_id: str
    version: str
    package_key: tuple[str, str, str, str, str]
    family_ids: tuple[str, ...]
    member_group_ids: tuple[str, ...]
    safe: bool
    exception_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.package_id
            or not self.version
            or not self.family_ids
            or not self.member_group_ids
        ):
            raise ValueError("package ID, version, families and members are required")
        if tuple(sorted(set(self.family_ids))) != self.family_ids:
            raise ValueError("package families must be unique and sorted")
        if tuple(sorted(set(self.member_group_ids))) != self.member_group_ids:
            raise ValueError("package members must be unique and sorted")
        if self.safe and self.exception_reasons:
            raise ValueError("safe packages cannot carry exception reasons")


@dataclass(frozen=True, slots=True)
class GroupingResult:
    """Internal grouping result with a deliberately narrow public projection."""

    partition: RowPartition
    version_context: PackageVersionContext
    features: tuple[FeatureVector, ...]
    families: tuple[SemanticFamily, ...]
    packages: tuple[DecisionPackage, ...]
    exceptions: tuple[GroupingException, ...]

    def public_payload(self) -> dict[str, object]:
        """Return opaque IDs and aggregate-safe fields only, never source facts."""
        return {
            "visible_row_ids": tuple(row.row_id for row in self.partition.visible_rows),
            "packages": tuple(
                {
                    "package_id": package.package_id,
                    "version": package.version,
                    "family_ids": package.family_ids,
                    "member_group_ids": package.member_group_ids,
                    "safe": package.safe,
                }
                for package in self.packages
            ),
            "exception_group_ids": tuple(
                sorted(
                    {group_id for exception in self.exceptions for group_id in exception.group_ids}
                )
            ),
        }


def finite_decimal_zero(value: Decimal | None) -> bool:
    """Return true only for a finite Decimal whose numeric value is exactly zero."""
    return isinstance(value, Decimal) and value.is_finite() and value == Decimal("0")

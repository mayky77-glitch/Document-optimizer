"""Immutable, path-safe contracts for Excel/PDF document packages."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import PurePosixPath

PACKAGE_WORKBOOK_FACTS_VERSION = "PackageWorkbookFacts-1.0"


def _relative_path(value: PurePosixPath) -> None:
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("only a safe relative path is allowed")


@dataclass(frozen=True, slots=True)
class PackageIssue:
    """A deterministic, non-fatal fact that prevents automatic comparison."""

    code: str
    message: str
    workbook_path: PurePosixPath | None = None
    sheet_name: str | None = None
    row_number: int | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("issue code and message are required")
        if self.workbook_path is not None:
            _relative_path(self.workbook_path)
        if self.row_number is not None and self.row_number < 1:
            raise ValueError("row number must be positive")


@dataclass(frozen=True, slots=True)
class DocumentPackage:
    """One package root and its inputs, represented without absolute paths."""

    relative_root: PurePosixPath
    workbook_paths: tuple[PurePosixPath, ...]
    pdf_paths: tuple[PurePosixPath, ...]

    def __post_init__(self) -> None:
        _relative_path(self.relative_root)
        if not self.workbook_paths:
            raise ValueError("a document package requires at least one workbook")
        for path in (*self.workbook_paths, *self.pdf_paths):
            _relative_path(path)
        if tuple(sorted(set(self.workbook_paths))) != self.workbook_paths:
            raise ValueError("workbook paths must be unique and sorted")
        if tuple(sorted(set(self.pdf_paths))) != self.pdf_paths:
            raise ValueError("PDF paths must be unique and sorted")


@dataclass(frozen=True, slots=True)
class PackageDiscovery:
    """Deterministic package discovery result for a single trusted root."""

    packages: tuple[DocumentPackage, ...]
    issues: tuple[PackageIssue, ...] = ()

    def __post_init__(self) -> None:
        roots = tuple(item.relative_root for item in self.packages)
        if tuple(sorted(set(roots))) != roots:
            raise ValueError("package roots must be unique and sorted")


@dataclass(frozen=True, slots=True)
class WorkbookRowFact:
    """Comparable KS-2 row facts; missing values are explicit rather than inferred."""

    sheet_name: str
    row_number: int
    act_number: str | None
    period: str | None
    object_code: str | None
    work_code: str | None
    drawing_code: str | None
    basis: str | None
    work_name: str | None
    unit: str | None
    quantity: Decimal | None
    total_cost: Decimal | None

    def __post_init__(self) -> None:
        if not self.sheet_name or self.row_number < 1:
            raise ValueError("sheet name and positive row number are required")
        for value in (self.quantity, self.total_cost):
            if value is not None and not value.is_finite():
                raise ValueError("numeric workbook facts must be finite")


@dataclass(frozen=True, slots=True)
class WorkbookSheetFacts:
    """Read-only facts extracted from one worksheet."""

    sheet_name: str
    act_number: str | None
    period: str | None
    object_code: str | None
    rows: tuple[WorkbookRowFact, ...]
    issues: tuple[PackageIssue, ...] = ()

    def __post_init__(self) -> None:
        if not self.sheet_name:
            raise ValueError("sheet name is required")


@dataclass(frozen=True, slots=True)
class PackageWorkbookFacts:
    """Versioned, serializable workbook extraction result for later PDF matching."""

    workbook_path: PurePosixPath
    sheets: tuple[WorkbookSheetFacts, ...]
    issues: tuple[PackageIssue, ...] = ()
    contract_version: str = PACKAGE_WORKBOOK_FACTS_VERSION

    def __post_init__(self) -> None:
        _relative_path(self.workbook_path)
        names = tuple(item.sheet_name for item in self.sheets)
        if len(names) != len(set(names)):
            raise ValueError("worksheet facts must have unique sheet names")
        if self.contract_version != PACKAGE_WORKBOOK_FACTS_VERSION:
            raise ValueError("unsupported workbook facts contract version")

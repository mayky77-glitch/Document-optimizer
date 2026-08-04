"""Safe, local-only Excel/PDF package reconciliation primitives."""

from .discovery import discover_document_packages
from .models import (
    PACKAGE_WORKBOOK_FACTS_VERSION,
    DocumentPackage,
    PackageDiscovery,
    PackageIssue,
    PackageWorkbookFacts,
    WorkbookRowFact,
    WorkbookSheetFacts,
)
from .pipeline import reconcile_package
from .report import ReconciliationReport, write_report_atomically
from .workbook import extract_package_workbook_facts

__all__ = [
    "PACKAGE_WORKBOOK_FACTS_VERSION",
    "DocumentPackage",
    "PackageDiscovery",
    "PackageIssue",
    "PackageWorkbookFacts",
    "ReconciliationReport",
    "WorkbookRowFact",
    "WorkbookSheetFacts",
    "discover_document_packages",
    "extract_package_workbook_facts",
    "reconcile_package",
    "write_report_atomically",
]

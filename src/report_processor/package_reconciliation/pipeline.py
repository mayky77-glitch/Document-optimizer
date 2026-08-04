"""Bounded package orchestration: extract only exact work-code AОСР candidates."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath

from .discovery import discover_document_packages
from .matcher import drawing_codes_for_row, normalize_work_code, reconcile_row
from .models import DocumentPackage, PackageWorkbookFacts, WorkbookRowFact
from .pdf_documents import PdfDocumentEvidence, analyse_pdf_document, classify_document_name
from .report import ReconciliationReport
from .workbook import extract_package_workbook_facts

WorkbookExtractor = Callable[[Path, PurePosixPath], PackageWorkbookFacts]
PdfExtractor = Callable[[Path, PurePosixPath], PdfDocumentEvidence]


def reconcile_package(
    package_root: Path,
    *,
    workbook_extractor: WorkbookExtractor = extract_package_workbook_facts,
    pdf_extractor: PdfExtractor = analyse_pdf_document,
) -> ReconciliationReport:
    """Reconcile discovered packages without broad PDF OCR or guessed pairings."""
    root = Path(package_root).resolve(strict=True)
    discovery = discover_document_packages(root)
    results = []
    for package in discovery.packages:
        results.extend(
            _reconcile_document_package(root, package, workbook_extractor, pdf_extractor)
        )
    return ReconciliationReport(tuple(results))


def _reconcile_document_package(
    root: Path,
    package: DocumentPackage,
    workbook_extractor: WorkbookExtractor,
    pdf_extractor: PdfExtractor,
) -> list:
    all_rows: list[tuple[PurePosixPath, WorkbookRowFact, tuple[WorkbookRowFact, ...]]] = []
    for workbook_path in package.workbook_paths:
        facts = workbook_extractor(root, workbook_path)
        for sheet in facts.sheets:
            sheet_rows = sheet.rows
            all_rows.extend((workbook_path, row, sheet_rows) for row in sheet_rows)
    candidates_by_code = _exact_aosr_candidates(root, package, all_rows, pdf_extractor)
    return [
        reconcile_row(
            row,
            workbook_path,
            candidates_by_code.get(normalize_work_code(row.work_code), ()),
            drawing_codes=drawing_codes_for_row(row, sheet_rows),
        )
        for workbook_path, row, sheet_rows in all_rows
    ]


def _exact_aosr_candidates(
    root: Path,
    package: DocumentPackage,
    rows: list[tuple[PurePosixPath, WorkbookRowFact, tuple[WorkbookRowFact, ...]]],
    pdf_extractor: PdfExtractor,
) -> dict[str, tuple[PdfDocumentEvidence, ...]]:
    codes = {normalize_work_code(row.work_code) for _path, row, _rows in rows}
    result: dict[str, list[PdfDocumentEvidence]] = {}
    for relative_path in package.pdf_paths:
        work_code = normalize_work_code(relative_path.parent.name)
        if work_code not in codes:
            continue
        if classify_document_name(relative_path.name) != "aosr":
            continue
        evidence = pdf_extractor(root.joinpath(*relative_path.parts), relative_path)
        result.setdefault(work_code, []).append(evidence)
    return {
        key: tuple(sorted(value, key=lambda item: item.relative_path.as_posix()))
        for key, value in result.items()
    }

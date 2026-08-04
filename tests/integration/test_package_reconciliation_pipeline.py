from decimal import Decimal
from pathlib import Path, PurePosixPath

import pytest

from report_processor.package_reconciliation.models import (
    PackageWorkbookFacts,
    WorkbookRowFact,
    WorkbookSheetFacts,
)
from report_processor.package_reconciliation.pdf_documents import PdfDocumentEvidence
from report_processor.package_reconciliation.pipeline import reconcile_package


def test_pipeline_ocr_extracts_only_exact_work_code_aosr_candidate(tmp_path: Path) -> None:
    (tmp_path / "act.xlsx").touch()
    exact = tmp_path / "2.4.6.8.10"
    exact.mkdir()
    (exact / "АОСР.pdf").touch()
    (exact / "ОЖР.pdf").touch()
    other = tmp_path / "2.4.6.8.11"
    other.mkdir()
    (other / "АОСР.pdf").touch()
    rows = (
        WorkbookRowFact(
            "Лист",
            8,
            None,
            None,
            None,
            "2.4.6.8",
            "DEMO.321.PROJ-123",
            None,
            "Раздел",
            None,
            None,
            None,
        ),
        WorkbookRowFact(
            "Лист",
            9,
            None,
            None,
            None,
            "2.4.6.8.10",
            None,
            None,
            "Устройство основания",
            "м",
            Decimal("1"),
            None,
        ),
    )
    calls: list[PurePosixPath] = []

    def workbook(_root: Path, path: PurePosixPath) -> PackageWorkbookFacts:
        return PackageWorkbookFacts(path, (WorkbookSheetFacts("Лист", None, None, None, rows),))

    def evidence(_path: Path, relative: PurePosixPath) -> PdfDocumentEvidence:
        calls.append(relative)
        return PdfDocumentEvidence(
            relative,
            "aosr",
            1,
            "text_layer",
            None,
            None,
            ("DEMO.321.PROJ-123",),
            "Устройство основания",
            (),
            (),
            None,
            (),
        )

    report = reconcile_package(tmp_path, workbook_extractor=workbook, pdf_extractor=evidence)

    assert calls == [PurePosixPath("2.4.6.8.10/АОСР.pdf")]
    assert len(report.results) == 1
    assert report.results[0].status == "MATCH"


def test_pipeline_preserves_discovery_symlink_root_rejection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(source, target_is_directory=True)

    with pytest.raises(ValueError, match="symlinked package root"):
        reconcile_package(linked)


def test_exact_scope_unsupported_pdf_returns_review_without_extraction(tmp_path: Path) -> None:
    (tmp_path / "act.xlsx").touch()
    code_directory = tmp_path / "1.1"
    code_directory.mkdir()
    (code_directory / "ОЖР.pdf").touch()
    row = WorkbookRowFact(
        "Лист", 2, None, None, None, "1.1", None, None, "Монтаж опор", "шт", Decimal("2"), None
    )

    def workbook(_root: Path, path: PurePosixPath) -> PackageWorkbookFacts:
        return PackageWorkbookFacts(path, (WorkbookSheetFacts("Лист", None, None, None, (row,)),))

    def evidence(*_args: object) -> PdfDocumentEvidence:
        raise AssertionError("unsupported PDF must not be extracted")

    report = reconcile_package(tmp_path, workbook_extractor=workbook, pdf_extractor=evidence)

    assert report.results[0].status == "NEEDS_REVIEW"
    assert report.results[0].reason_codes == ("unsupported_document_type",)
    assert report.results[0].pdf_path == PurePosixPath("1.1/ОЖР.pdf")
    assert report.results[0].candidate_paths == (PurePosixPath("1.1/ОЖР.pdf"),)


def test_multiple_unsupported_candidates_are_ambiguous_without_extraction(tmp_path: Path) -> None:
    (tmp_path / "act.xlsx").touch()
    code_directory = tmp_path / "1.1"
    code_directory.mkdir()
    (code_directory / "ОЖР-B.pdf").touch()
    (code_directory / "ОЖР-A.pdf").touch()
    row = WorkbookRowFact(
        "Лист", 2, None, None, None, "1.1", None, None, "Монтаж опор", "шт", Decimal("2"), None
    )

    def workbook(_root: Path, path: PurePosixPath) -> PackageWorkbookFacts:
        return PackageWorkbookFacts(path, (WorkbookSheetFacts("Лист", None, None, None, (row,)),))

    def evidence(*_args: object) -> PdfDocumentEvidence:
        raise AssertionError("unsupported PDF must not be extracted")

    report = reconcile_package(tmp_path, workbook_extractor=workbook, pdf_extractor=evidence)

    result = report.results[0]
    assert result.status == "AMBIGUOUS"
    assert result.pdf_path is None
    assert result.candidate_paths == (
        PurePosixPath("1.1/ОЖР-A.pdf"),
        PurePosixPath("1.1/ОЖР-B.pdf"),
    )


def test_package_with_no_comparable_rows_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "act.xlsx").touch()
    row = WorkbookRowFact(
        "Лист", 2, None, None, None, "1.1", None, None, "Раздел", None, None, None
    )

    def workbook(_root: Path, path: PurePosixPath) -> PackageWorkbookFacts:
        return PackageWorkbookFacts(path, (WorkbookSheetFacts("Лист", None, None, None, (row,)),))

    with pytest.raises(ValueError, match="no comparable rows"):
        reconcile_package(tmp_path, workbook_extractor=workbook)

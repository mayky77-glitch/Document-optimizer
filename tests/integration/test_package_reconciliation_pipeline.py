from pathlib import Path, PurePosixPath

from report_processor.package_reconciliation.models import (
    PackageWorkbookFacts,
    WorkbookRowFact,
    WorkbookSheetFacts,
)
from report_processor.package_reconciliation.pdf_documents import PdfDocumentEvidence
from report_processor.package_reconciliation.pipeline import reconcile_package


def test_pipeline_ocr_extracts_only_exact_work_code_aosr_candidate(tmp_path: Path) -> None:
    (tmp_path / "act.xlsx").touch()
    exact = tmp_path / "6.1.10.1.1"
    exact.mkdir()
    (exact / "АОСР.pdf").touch()
    (exact / "ОЖР.pdf").touch()
    other = tmp_path / "6.1.10.1.2"
    other.mkdir()
    (other / "АОСР.pdf").touch()
    rows = (
        WorkbookRowFact(
            "Лист",
            8,
            None,
            None,
            None,
            "6.1.10.1",
            "0092.049.Р-123",
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
            "6.1.10.1.1",
            None,
            None,
            "Устройство основания",
            "м",
            None,
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
            ("0092.049.Р-123",),
            "Устройство основания",
            (),
            (),
            None,
            (),
        )

    report = reconcile_package(tmp_path, workbook_extractor=workbook, pdf_extractor=evidence)

    assert calls == [PurePosixPath("6.1.10.1.1/АОСР.pdf")]
    assert report.results[1].status == "MATCH"

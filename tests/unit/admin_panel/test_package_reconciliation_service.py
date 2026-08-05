from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path, PurePosixPath

import pytest

from report_processor.admin_panel.package_reconciliation_service import (
    PackageReconciliationService,
)
from report_processor.package_reconciliation.matcher import RowReconciliation
from report_processor.package_reconciliation.report import ReconciliationReport


def _report(_root: Path) -> ReconciliationReport:
    return ReconciliationReport(
        (
            RowReconciliation(
                status="MATCH",
                workbook_path=PurePosixPath("acts/act.xlsx"),
                sheet_name="Sheet1",
                row_number=2,
                work_code="1.1",
                pdf_path=PurePosixPath("acts/1.1/aosr.pdf"),
                confidence=Decimal("1"),
                reason_codes=("project_code_match",),
                quantity_comparison="MATCH",
                workbook_quantity=Decimal("2"),
                workbook_unit="шт",
                pdf_quantity=Decimal("2"),
                pdf_unit="шт",
            ),
        )
    )


def test_service_stores_validated_folder_privately_and_exposes_only_safe_payload(
    tmp_path: Path,
) -> None:
    service = PackageReconciliationService(tmp_path / "private", runner=_report)

    job = service.create_job(files=[("acts/act.xlsx", b"workbook"), ("acts/1.1/aosr.pdf", b"pdf")])
    payload = service.payload_for(job.job_id)
    result, name = service.get_result(job.job_id)

    assert job.status == "ready"
    assert result.is_file() and result.stat().st_mode & 0o777 == 0o600
    assert name == "package-reconciliation.json"
    assert payload["summary"] == {"MATCH": 1}
    assert payload["results"][0]["workbook_path"] == "acts/act.xlsx"
    assert str(tmp_path) not in str(payload)
    assert "ocr" not in str(payload).casefold()


@pytest.mark.parametrize(
    "files",
    [
        [("../act.xlsx", b"x")],
        [("/act.xlsx", b"x")],
        [("acts\\act.xlsx", b"x")],
        [("acts/act.xls", b"x")],
        [("acts/aosr.pdf", b"x")],
        [("acts/act.xlsx", b"x"), ("ACTS/ACT.xlsx", b"y")],
        [("акты/е\u0308.xlsx", b"x"), ("акты/ё.xlsx", b"y"), ("акты/aosr.pdf", b"z")],
    ],
)
def test_service_rejects_unsafe_or_duplicate_folder_paths(
    tmp_path: Path, files: list[tuple[str, bytes]]
) -> None:
    service = PackageReconciliationService(tmp_path / "private", runner=_report)

    with pytest.raises(ValueError):
        service.create_job(files=files)


def test_service_returns_controlled_failure_without_retaining_runner_exception(
    tmp_path: Path,
) -> None:
    def failed(_root: Path) -> ReconciliationReport:
        raise RuntimeError("/private/ocr-dump")

    service = PackageReconciliationService(tmp_path / "private", runner=failed)
    job = service.create_job(files=[("act.xlsx", b"workbook"), ("aosr.pdf", b"pdf")])

    assert service.payload_for(job.job_id) == {
        "job_id": job.job_id,
        "status": "failed",
        "summary": {},
        "results": [],
        "download_url": None,
        "error": "Не удалось обработать пакет. Проверьте состав и файлы пакета.",
    }
    with pytest.raises(KeyError):
        service.get_result(job.job_id)


def test_service_allows_workbook_only_folder(tmp_path: Path) -> None:
    calls: list[Path] = []

    def runner(root: Path) -> ReconciliationReport:
        calls.append(root)
        return _report(root)

    service = PackageReconciliationService(tmp_path / "private", runner=runner)
    job = service.create_job(files=[("act.xlsx", b"workbook")])

    assert job.status == "ready"
    assert calls == [job.input_root]


@dataclass(frozen=True)
class _ExtraResult:
    status: str = "MATCH"
    workbook_path: PurePosixPath = field(default_factory=lambda: PurePosixPath("act.xlsx"))
    sheet_name: str = "Sheet1"
    row_number: int = 2
    work_code: str = "1.1"
    pdf_path: PurePosixPath = field(default_factory=lambda: PurePosixPath("aosr.pdf"))
    confidence: Decimal = Decimal("1")
    reason_codes: tuple[str, ...] = ("project_code_match",)
    quantity_comparison: str = "MATCH"
    workbook_quantity: Decimal = Decimal("2")
    workbook_unit: str = "шт"
    pdf_quantity: Decimal = Decimal("2")
    pdf_unit: str = "шт"
    raw_ocr: str = "secret OCR text"
    absolute_secret: str = "/private/local/path"


@dataclass(frozen=True)
class _ExtraReport:
    results: tuple[_ExtraResult, ...] = (_ExtraResult(),)
    contract_version: str = "ExcelPdfReconciliation-1.0"


def test_download_uses_only_explicit_report_fields(tmp_path: Path) -> None:
    service = PackageReconciliationService(
        tmp_path / "private", runner=lambda _root: _ExtraReport()
    )
    job = service.create_job(files=[("act.xlsx", b"workbook"), ("aosr.pdf", b"pdf")])
    result, _name = service.get_result(job.job_id)
    downloaded = json.loads(result.read_text(encoding="utf-8"))

    assert downloaded == {
        "contract_version": "ExcelPdfReconciliation-1.0",
        "results": [
            {
                "confidence": "1",
                "pdf_path": "aosr.pdf",
                "pdf_quantity": "2",
                "pdf_unit": "шт",
                "quantity_comparison": "MATCH",
                "reason_codes": ["project_code_match"],
                "row_number": 2,
                "sheet_name": "Sheet1",
                "status": "MATCH",
                "work_code": "1.1",
                "workbook_path": "act.xlsx",
                "workbook_quantity": "2",
                "workbook_unit": "шт",
            }
        ],
    }

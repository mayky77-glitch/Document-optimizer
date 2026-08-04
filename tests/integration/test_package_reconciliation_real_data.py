"""Opt-in pilot only; never discovers or embeds user corpus locations."""

import os
from pathlib import Path

import pytest

from report_processor.package_reconciliation import discover_document_packages
from report_processor.package_reconciliation.matcher import STATUSES
from report_processor.package_reconciliation.pipeline import reconcile_package


@pytest.mark.integration
def test_opt_in_real_pilot_package() -> None:
    pilot = os.environ.get("REPORT_PROCESSOR_RECONCILIATION_PILOT")
    if not pilot:
        pytest.skip("set REPORT_PROCESSOR_RECONCILIATION_PILOT to run designated small pilot")
    discovery = discover_document_packages(Path(pilot))
    workbook_count = sum(len(package.workbook_paths) for package in discovery.packages)
    pdf_count = sum(len(package.pdf_paths) for package in discovery.packages)
    assert 0 < workbook_count <= 2
    assert 0 < pdf_count <= 6
    report = reconcile_package(Path(pilot))
    assert report.contract_version == "ExcelPdfReconciliation-1.0"
    assert report.results
    assert {result.status for result in report.results} <= STATUSES
    assert any(result.pdf_path is not None for result in report.results)
    for result in report.results:
        assert not result.workbook_path.is_absolute()
        assert result.pdf_path is None or not result.pdf_path.is_absolute()

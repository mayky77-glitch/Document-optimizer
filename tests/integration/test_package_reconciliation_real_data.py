"""Opt-in pilot only; never discovers or embeds user corpus locations."""

import os
from pathlib import Path

import pytest

from report_processor.package_reconciliation.pipeline import reconcile_package


@pytest.mark.integration
def test_opt_in_real_pilot_package() -> None:
    pilot = os.environ.get("REPORT_PROCESSOR_RECONCILIATION_PILOT")
    if not pilot:
        pytest.skip("set REPORT_PROCESSOR_RECONCILIATION_PILOT to run designated small pilot")
    report = reconcile_package(Path(pilot))
    assert report.contract_version == "ExcelPdfReconciliation-1.0"

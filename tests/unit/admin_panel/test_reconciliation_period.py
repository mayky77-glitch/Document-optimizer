"""Strict immutable reporting-period contracts."""

import pytest

from report_processor.admin_panel.reconciliation_period import (
    ReconciliationPeriodError,
    ReportingPeriod,
)


def test_reporting_period_is_exact_zero_padded_month() -> None:
    period = ReportingPeriod.parse("2026-08")

    assert (period.year, period.month, period.label) == (2026, 8, "Август 2026")


@pytest.mark.parametrize("value", ("2026-8", "08-2026", "2026-13", "2026-08 "))
def test_reporting_period_rejects_noncanonical_input(value: str) -> None:
    with pytest.raises(ReconciliationPeriodError, match="REPORTING_PERIOD_INVALID"):
        ReportingPeriod.parse(value)

import json
import stat
from decimal import Decimal
from pathlib import Path, PurePosixPath

from report_processor.package_reconciliation.matcher import RowReconciliation
from report_processor.package_reconciliation.report import (
    ReconciliationReport,
    write_report_atomically,
)


def test_writes_private_canonical_report_without_absolute_path(tmp_path: Path) -> None:
    report = ReconciliationReport(
        (
            RowReconciliation(
                "MATCH",
                PurePosixPath("акт.xlsx"),
                "Лист",
                8,
                "1.2",
                PurePosixPath("1.2/АОСР.pdf"),
                Decimal("1"),
                ("project_code_match",),
                "NOT_COMPARABLE",
                Decimal("2"),
                "м",
                None,
                None,
                candidate_paths=(PurePosixPath("1.2/АОСР.pdf"),),
            ),
        )
    )
    target = tmp_path / "result.json"

    write_report_atomically(report, target)

    payload = json.loads(target.read_text())
    assert payload["results"][0]["workbook_path"] == "акт.xlsx"
    assert payload["results"][0]["candidate_paths"] == ["1.2/АОСР.pdf"]
    assert str(tmp_path) not in target.read_text()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600

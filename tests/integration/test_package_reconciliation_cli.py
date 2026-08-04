import json
from pathlib import Path

from openpyxl import Workbook

from report_processor.cli import main


def test_cli_writes_report_for_runtime_synthetic_workbook(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for column, value in enumerate(("Позиция", "Наименование работ", "Ед. изм.", "Количество"), 1):
        sheet.cell(1, column, value)
    sheet.append(("1.1", "Монтаж опор", "шт", 2))
    workbook.save(tmp_path / "акт.xlsx")
    workbook.close()
    output = tmp_path / "report.json"

    assert main(["reconcile-package", "--package", str(tmp_path), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["results"][0]["status"] == "NO_EVIDENCE"

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from report_processor.drawing_card.periods import discover_workbook_periods


def test_discovers_all_periods_from_filename_and_workbook_values(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("Период", "Дата", "Примечание"))
    sheet.append(("июль 2026", date(2026, 6, 30), "закрытие 31.05.2026"))
    sheet.append(("июнь 2026", "05.2026", "план 2026-04"))
    sheet.append(("посторонняя дата", date(2069, 1, 1), "январь 2069"))
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()

    periods = discover_workbook_periods(
        [("КС-2 2026-04.xlsx", stream.getvalue())],
        temporary_root=tmp_path,
    )

    assert periods == ("2026-04", "2026-05", "2026-06", "2026-07")
    assert list(tmp_path.iterdir()) == []

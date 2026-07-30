from pathlib import Path

from openpyxl import Workbook

from conftest import schema_candidate
from report_processor.schema.config import create_default_schema_config
from report_processor.schema.models import SheetType
from report_processor.schema.scan_window import scan_worksheet_window
from report_processor.schema.sheet_classifier import classify_worksheet
from report_processor.workflow import prepared_workbook_session


def _create_ks6a_content(path: Path, sheet_name: str) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet["A2"] = "Наименование этапа выполнения работ"
    worksheet["B2"] = "Единица измерения"
    worksheet["C2"] = "Выполнено с начала строительства"
    worksheet["D2"] = "Остаток работ по договору"
    worksheet["A3"] = "Монтаж"
    worksheet["B3"] = "м"
    worksheet["C3"] = 10
    worksheet["D3"] = 2
    workbook.save(path)
    workbook.close()


def test_uninformative_name_is_corrected_by_strong_content(tmp_path: Path) -> None:
    path = tmp_path / "content.xlsx"
    _create_ks6a_content(path, "Лист1")
    config = create_default_schema_config()
    with prepared_workbook_session(schema_candidate(path)) as session:
        scan = scan_worksheet_window(session, "Лист1", config.scan)
        result = classify_worksheet(session, "Лист1", config, scan=scan)
    assert result.sheet_type == SheetType.KS6A
    assert result.content_score >= 0.65
    assert result.status == "OK"


def test_name_content_conflict_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "conflict.xlsx"
    _create_ks6a_content(path, "КС-2")
    config = create_default_schema_config()
    with prepared_workbook_session(schema_candidate(path)) as session:
        scan = scan_worksheet_window(session, "КС-2", config.scan)
        result = classify_worksheet(session, "КС-2", config, scan=scan)
    assert result.status == "AMBIGUOUS_SHEET_TYPE"
    assert result.sheet_type in {SheetType.KS2, SheetType.KS6A}
    assert any(item.startswith("SHEET_TYPE_CONFLICT") for item in result.warnings)

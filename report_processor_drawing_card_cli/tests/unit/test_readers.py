from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook

from report_processor.drawing_card.sources.readers import OpenXmlWorkbookReader


def test_shared_formula_is_translated_for_each_row(tmp_path: Path) -> None:
    source = tmp_path / "shared_formula.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Data"
    sheet["A1"] = 10
    sheet["A2"] = 20
    sheet["B1"] = "=A1*2"
    sheet["B2"] = "=A2*2"
    workbook.save(source)
    workbook.close()

    patched = tmp_path / "patched.xlsx"
    with ZipFile(source) as src, ZipFile(patched, "w", ZIP_DEFLATED) as dst:
        for info in src.infolist():
            payload = src.read(info.filename)
            if info.filename == "xl/worksheets/sheet1.xml":
                text = payload.decode("utf-8")
                text = text.replace(
                    "<f>A1*2</f>",
                    '<f t="shared" ref="B1:B2" si="0">A1*2</f>',
                )
                text = text.replace("<f>A2*2</f>", '<f t="shared" si="0"/>')
                payload = text.encode("utf-8")
            dst.writestr(info, payload)

    reader = OpenXmlWorkbookReader(patched)
    try:
        rows = list(reader.iter_rows("Data", min_row=1, max_row=2, max_col=2))
    finally:
        reader.close()
    assert rows[0][0][1] == "=A1*2"
    assert rows[1][0][1] == "=A2*2"

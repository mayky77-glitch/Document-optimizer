from hashlib import sha256
from pathlib import Path

from conftest import candidate, regular_entry
from report_processor.excel.cell_reader import read_cell_snapshot
from report_processor.workflow import prepared_workbook_session


def test_regular_workbook_is_not_modified_or_deleted(workbook_path: Path):
    before = (
        workbook_path.stat().st_size,
        workbook_path.stat().st_mtime_ns,
        sha256(workbook_path.read_bytes()).hexdigest(),
    )
    with prepared_workbook_session(candidate(regular_entry(workbook_path))) as session:
        assert read_cell_snapshot(session, "Данные", "A1").formula_value == 10
        assert session.source.local_path == workbook_path
    after = (
        workbook_path.stat().st_size,
        workbook_path.stat().st_mtime_ns,
        sha256(workbook_path.read_bytes()).hexdigest(),
    )
    assert before == after
    assert workbook_path.exists()


def test_repeated_opening_works(workbook_path: Path):
    item = candidate(regular_entry(workbook_path))
    for _ in range(2):
        with prepared_workbook_session(item) as session:
            assert session.metadata.sheet_count == 3


def test_xlsm_opens_with_vba_context(tmp_path: Path, workbook_path: Path):
    xlsm = tmp_path / "sample.xlsm"
    xlsm.write_bytes(workbook_path.read_bytes())
    with prepared_workbook_session(candidate(regular_entry(xlsm))) as session:
        assert session.keep_vba is True
        assert session.formula_workbook.vba_archive is not None
        assert session.value_workbook.vba_archive is not None

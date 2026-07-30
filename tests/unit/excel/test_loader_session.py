from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from conftest import regular_entry
from report_processor.domain.exceptions import WorkbookOpenError
from report_processor.excel.models import WorkbookOpenRequest
from report_processor.excel.workbook_loader import build_openpyxl_parameters, load_dual_workbooks
from report_processor.excel.workbook_session import open_dual_workbook
from report_processor.materialization.regular_file import resolve_regular_file


def _request(path: Path) -> WorkbookOpenRequest:
    source = resolve_regular_file(regular_entry(path), max_file_size_bytes=10**7)
    return WorkbookOpenRequest(source=source)


def test_open_parameters_are_consistent(workbook_path: Path, tmp_path: Path):
    request = _request(workbook_path)
    formula = build_openpyxl_parameters(request, data_only=False)
    values = build_openpyxl_parameters(request, data_only=True)
    assert formula["read_only"] is True
    assert formula["keep_links"] is True
    assert formula["data_only"] is False
    assert values["data_only"] is True
    assert formula["keep_vba"] is False

    xlsm_path = tmp_path / "sample.xlsm"
    xlsm_path.write_bytes(workbook_path.read_bytes())
    assert build_openpyxl_parameters(_request(xlsm_path), data_only=False)["keep_vba"] is True


def test_dual_session_opens_and_closes(workbook_path: Path):
    request = _request(workbook_path)
    with open_dual_workbook(request) as session:
        assert session.formula_workbook.data_only is False
        assert session.value_workbook.data_only is True
        assert not session.closed
    assert session.closed


def test_first_workbook_is_closed_if_second_open_fails(workbook_path: Path):
    request = _request(workbook_path)
    first = MagicMock()
    with patch("report_processor.excel.workbook_loader.openpyxl.load_workbook") as loader:
        loader.side_effect = [first, ValueError("second failed")]
        with pytest.raises(WorkbookOpenError):
            load_dual_workbooks(request)
    first.close.assert_called_once()


def test_user_exception_still_closes_workbooks(workbook_path: Path):
    request = _request(workbook_path)
    with pytest.raises(RuntimeError), open_dual_workbook(request) as session:
        raise RuntimeError("boom")
    assert session.closed


def test_source_can_be_opened_again_after_context(workbook_path: Path):
    request = _request(workbook_path)
    with open_dual_workbook(request):
        pass
    with open_dual_workbook(request) as session:
        assert session.formula_workbook.sheetnames[0] == "Данные"

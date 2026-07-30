from pathlib import Path

import pytest

from conftest import candidate, create_zip_with_workbook
from report_processor.excel.cell_reader import read_cell_snapshot
from report_processor.workflow import prepared_workbook_session


def test_zip_workbook_exists_only_inside_context(tmp_path: Path, workbook_path: Path):
    archive = tmp_path / "source.zip"
    entry = create_zip_with_workbook(archive, workbook_path)
    local_path = None
    with prepared_workbook_session(
        candidate(entry),
        workspace_root=tmp_path / "workspaces",
    ) as session:
        local_path = session.source.local_path
        assert local_path.exists()
        assert read_cell_snapshot(session, "Данные", "A3").is_formula
    assert local_path is not None
    assert not local_path.exists()


def test_exception_inside_zip_context_still_cleans(tmp_path: Path, workbook_path: Path):
    archive = tmp_path / "source.zip"
    entry = create_zip_with_workbook(archive, workbook_path)
    local_path = None
    with (
        pytest.raises(RuntimeError),
        prepared_workbook_session(
            candidate(entry),
            workspace_root=tmp_path / "workspaces",
        ) as session,
    ):
        local_path = session.source.local_path
        raise RuntimeError("boom")
    assert local_path is not None and not local_path.exists()

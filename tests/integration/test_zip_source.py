from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from report_processor.inventory.file_manifest import build_file_manifest
from report_processor.workflow import prepared_workbook_session


def test_single_zip_entry_is_materialized_and_removed(tmp_path: Path):
    workbook_path = tmp_path / "source.xlsx"
    workbook = Workbook()
    workbook.active["A1"] = "ok"
    workbook.save(workbook_path)
    workbook.close()
    archive = tmp_path / "reports.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.write(workbook_path, "nested/source.xlsx")
    entry = build_file_manifest(archive).entries[0]
    from report_processor.selection.models import SourceCandidate

    candidate = SourceCandidate(entry.file_id, entry, 0, None, True, (), (), ())
    with prepared_workbook_session(candidate) as session:
        materialized = session.source.local_path
        assert materialized.exists()
        assert session.formula_workbook.active["A1"].value == "ok"
    assert not materialized.exists()


def test_zip_slip_path_is_rejected(tmp_path: Path):
    archive = tmp_path / "reports.zip"
    with zipfile.ZipFile(archive, "w") as target:
        target.writestr("../evil.xlsx", b"bad")
    manifest = build_file_manifest(archive)
    assert manifest.entries[0].status != "OK"


def test_exception_from_session_body_is_not_wrapped(tmp_path: Path):
    workbook_path = tmp_path / "source.xlsx"
    workbook = Workbook()
    workbook.save(workbook_path)
    workbook.close()
    entry = build_file_manifest(workbook_path).entries[0]
    from report_processor.selection.models import SourceCandidate

    candidate = SourceCandidate(entry.file_id, entry, 0, None, True, (), (), ())

    with pytest.raises(RuntimeError, match="body failure"):  # noqa: SIM117
        with prepared_workbook_session(candidate):
            raise RuntimeError("body failure")

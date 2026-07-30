import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from conftest import create_zip_with_workbook, zip_entry
from report_processor.domain.exceptions import MaterializationError, UnsafeArchiveEntryError
from report_processor.domain.statuses import StatusCode
from report_processor.materialization.zip_entry import materialize_zip_entry


def test_extracts_only_exact_selected_entry(tmp_path: Path, workbook_path: Path):
    archive = tmp_path / "source.zip"
    entry = create_zip_with_workbook(archive, workbook_path, "one/sample.xlsx")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with (
        patch.object(zipfile.ZipFile, "extract", side_effect=AssertionError),
        patch.object(zipfile.ZipFile, "extractall", side_effect=AssertionError),
    ):
        result = materialize_zip_entry(entry, workspace, max_file_size_bytes=10**7)
    assert result.local_path.exists()
    assert result.was_extracted and result.temporary
    assert len(list(workspace.iterdir())) == 1
    assert "other" not in {path.name for path in workspace.iterdir()}


def test_duplicate_basenames_use_exact_internal_path(tmp_path: Path, workbook_path: Path):
    archive = tmp_path / "duplicates.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("a/same.xlsx", workbook_path.read_bytes())
        output.writestr("b/same.xlsx", b"wrong")
    with zipfile.ZipFile(archive) as source:
        info = source.getinfo("a/same.xlsx")
    entry = zip_entry(archive, "a/same.xlsx", info.file_size, info.CRC)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    result = materialize_zip_entry(entry, workspace, max_file_size_bytes=10**7)
    assert result.local_path.read_bytes() == workbook_path.read_bytes()


def test_unsafe_path_is_rejected_before_opening(tmp_path: Path):
    archive = tmp_path / "unsafe.zip"
    archive.write_bytes(b"not relevant")
    entry = zip_entry(archive, "../../unsafe.xlsx", 1, 0)
    with pytest.raises(UnsafeArchiveEntryError) as caught:
        materialize_zip_entry(entry, tmp_path, max_file_size_bytes=10)
    assert caught.value.status == StatusCode.UNSAFE_ARCHIVE_PATH


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("missing_archive", StatusCode.ARCHIVE_NOT_FOUND),
        ("broken_archive", StatusCode.BROKEN_ARCHIVE),
        ("missing_entry", StatusCode.ARCHIVE_ENTRY_NOT_FOUND),
        ("declared_too_large", StatusCode.ARCHIVE_ENTRY_TOO_LARGE),
    ],
)
def test_zip_failures(tmp_path: Path, workbook_path: Path, scenario: str, expected: StatusCode):
    archive = tmp_path / "source.zip"
    if scenario == "missing_archive":
        entry = zip_entry(archive, "sample.xlsx", 1, 0)
    elif scenario == "broken_archive":
        archive.write_bytes(b"broken")
        entry = zip_entry(archive, "sample.xlsx", 1, 0)
    else:
        valid_entry = create_zip_with_workbook(archive, workbook_path, "sample.xlsx")
        if scenario == "missing_entry":
            entry = zip_entry(archive, "missing.xlsx", 1, 0)
        else:
            entry = valid_entry
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    limit = 1 if scenario == "declared_too_large" else 10**7
    with pytest.raises(MaterializationError) as caught:
        materialize_zip_entry(entry, workspace, max_file_size_bytes=limit)
    assert caught.value.status == expected
    assert list(workspace.iterdir()) == []


def test_actual_stream_limit_stops_copying():
    from io import BytesIO

    from report_processor.materialization.zip_entry import _copy_limited

    with pytest.raises(MaterializationError) as caught:
        _copy_limited(BytesIO(b"123456"), BytesIO(), 5)
    assert caught.value.status == StatusCode.ARCHIVE_ENTRY_TOO_LARGE


def test_crc_mismatch_removes_partial_file(tmp_path: Path, workbook_path: Path):
    archive = tmp_path / "crc.zip"
    inner = "sample.xlsx"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        output.write(workbook_path, inner)
    with zipfile.ZipFile(archive) as source:
        info = source.getinfo(inner)
        entry = zip_entry(archive, inner, info.file_size, info.CRC)
        offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    payload = bytearray(archive.read_bytes())
    payload[offset + 10] ^= 0xFF
    archive.write_bytes(payload)

    workspace = tmp_path / "workspace_crc"
    workspace.mkdir()
    with pytest.raises(MaterializationError) as caught:
        materialize_zip_entry(entry, workspace, max_file_size_bytes=10**7)
    assert caught.value.status == StatusCode.CRC_MISMATCH
    assert list(workspace.iterdir()) == []

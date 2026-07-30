from pathlib import Path

import pytest

from conftest import regular_entry
from report_processor.domain.exceptions import MaterializationError
from report_processor.domain.statuses import StatusCode
from report_processor.materialization.regular_file import resolve_regular_file


def test_regular_file_is_used_without_copy(workbook_path: Path):
    result = resolve_regular_file(regular_entry(workbook_path), max_file_size_bytes=10**7)
    assert result.local_path == workbook_path
    assert not result.was_extracted
    assert not result.cleanup_required


def test_changed_manifest_size_adds_warning(workbook_path: Path):
    entry = regular_entry(workbook_path, size_bytes=1)
    result = resolve_regular_file(entry, max_file_size_bytes=10**7)
    assert StatusCode.FILE_METADATA_CHANGED.value in result.warnings


@pytest.mark.parametrize("kind", ["missing", "directory", "large"])
def test_regular_file_failures(tmp_path: Path, workbook_path: Path, kind: str):
    if kind == "missing":
        path = tmp_path / "missing.xlsx"
        entry = regular_entry(path)
        expected = StatusCode.SOURCE_FILE_NOT_FOUND
        limit = 10**7
    elif kind == "directory":
        path = tmp_path / "folder.xlsx"
        path.mkdir()
        entry = regular_entry(path, size_bytes=None)
        expected = StatusCode.SOURCE_FILE_NOT_FOUND
        limit = 10**7
    else:
        entry = regular_entry(workbook_path)
        expected = StatusCode.FILE_TOO_LARGE
        limit = 1
    with pytest.raises(MaterializationError) as caught:
        resolve_regular_file(entry, max_file_size_bytes=limit)
    assert caught.value.status == expected


def test_symlink_is_rejected(tmp_path: Path, workbook_path: Path):
    link = tmp_path / "link.xlsx"
    try:
        link.symlink_to(workbook_path)
    except OSError:
        pytest.skip("Symlinks are unavailable")
    with pytest.raises(MaterializationError) as caught:
        resolve_regular_file(regular_entry(link), max_file_size_bytes=10**7)
    assert caught.value.status == StatusCode.SYMLINK_NOT_ALLOWED

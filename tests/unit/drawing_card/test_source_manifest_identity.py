from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from report_processor.drawing_card.sources.manifest import (
    scan_archive,
    scan_directory,
    scan_file,
)


def test_direct_file_identity_is_content_derived_across_private_job_directories(
    tmp_path: Path,
) -> None:
    first = tmp_path / "job-a" / "book.xlsx"
    second = tmp_path / "job-b" / "book.xlsx"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"identical workbook")
    second.write_bytes(b"identical workbook")

    [first_entry] = scan_file(first)
    [second_entry] = scan_file(second)

    assert first_entry.file_id == second_entry.file_id
    assert str(first.parent) not in first_entry.file_id
    assert str(second.parent) not in second_entry.file_id


def test_changed_workbook_content_changes_direct_file_identity(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    path.write_bytes(b"first workbook")
    [before] = scan_file(path)
    path.write_bytes(b"other workbook")
    [after] = scan_file(path)

    assert before.file_id != after.file_id


def test_directory_members_keep_safe_logical_paths_in_identity(tmp_path: Path) -> None:
    source = tmp_path / "job" / "sources"
    for logical_path in ("one/book.xlsx", "two/book.xlsx"):
        target = source / logical_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"identical workbook")

    entries = scan_directory(source)

    assert [entry.logical_path for entry in entries] == ["one/book.xlsx", "two/book.xlsx"]
    assert len({entry.file_id for entry in entries}) == 2


def test_archive_members_use_one_outer_digest_and_safe_logical_paths(tmp_path: Path) -> None:
    archive = tmp_path / "job" / "sources.zip"
    archive.parent.mkdir()
    with ZipFile(archive, "w") as output:
        output.writestr("one/book.xlsx", b"identical workbook")
        output.writestr("two/book.xlsx", b"identical workbook")

    entries = scan_archive(archive)

    assert [entry.logical_path for entry in entries] == ["one/book.xlsx", "two/book.xlsx"]
    assert len({entry.file_id for entry in entries}) == 2
    assert all(str(archive.parent) not in entry.file_id for entry in entries)

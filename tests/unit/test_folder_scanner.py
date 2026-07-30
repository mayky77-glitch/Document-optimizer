"""Тесты инвентаризации обычного каталога."""

from pathlib import Path

import pytest

from report_processor.domain.exceptions import SourceAccessError
from report_processor.domain.statuses import StatusCode
from report_processor.inventory.scanner import scan_directory


def _touch(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_recursive_and_non_recursive_scanning(tmp_path: Path) -> None:
    _touch(tmp_path / "root.xlsx")
    _touch(tmp_path / "nested" / "child.csv")

    recursive = scan_directory(tmp_path, recursive=True)
    non_recursive = scan_directory(tmp_path, recursive=False)

    assert [entry.relative_path for entry in recursive] == ["nested/child.csv", "root.xlsx"]
    assert [entry.relative_path for entry in non_recursive] == ["root.xlsx"]


def test_order_is_deterministic(tmp_path: Path) -> None:
    for filename in ["z.txt", "B.txt", "a.txt", "nested/c.txt"]:
        _touch(tmp_path / filename)

    first = [entry.relative_path for entry in scan_directory(tmp_path)]
    second = [entry.relative_path for entry in scan_directory(tmp_path)]

    assert first == second
    assert first == ["a.txt", "B.txt", "nested/c.txt", "z.txt"]


def test_temporary_and_unknown_files(tmp_path: Path) -> None:
    _touch(tmp_path / "~$КС-6а.xlsx")
    _touch(tmp_path / "binary.weird")

    entries = {entry.filename: entry for entry in scan_directory(tmp_path)}

    assert entries["~$КС-6а.xlsx"].is_temporary is True
    assert entries["binary.weird"].document_type == "unknown"
    assert entries["binary.weird"].extension == ".weird"


def test_empty_directory(tmp_path: Path) -> None:
    assert scan_directory(tmp_path) == []


def test_symlinks_are_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "target"
    _touch(target / "inside.xlsx")
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return

    paths = [entry.relative_path for entry in scan_directory(tmp_path)]

    assert paths == ["target/inside.xlsx"]


def test_possible_duplicates_in_different_directories(tmp_path: Path) -> None:
    _touch(tmp_path / "a" / "КС-2.xlsx", b"same-size")
    _touch(tmp_path / "b" / "КС-2.xlsx", b"same-size")

    entries = scan_directory(tmp_path)

    assert len(entries) == 2
    assert all(StatusCode.POSSIBLE_DUPLICATE.value in entry.warnings for entry in entries)
    assert all(entry.status == StatusCode.WARNING.value for entry in entries)


def test_file_id_is_stable_for_unchanged_file(tmp_path: Path) -> None:
    _touch(tmp_path / "stable.xlsx", b"content")

    first = scan_directory(tmp_path)[0].file_id
    second = scan_directory(tmp_path)[0].file_id

    assert first == second


def test_zip_inside_directory_is_not_opened(tmp_path: Path) -> None:
    broken_zip = tmp_path / "broken.zip"
    broken_zip.write_bytes(b"not a zip")

    [entry] = scan_directory(tmp_path)

    assert entry.filename == "broken.zip"
    assert entry.document_type == "archive"
    assert entry.status == StatusCode.OK.value


def test_root_directory_symlink_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target_root"
    target.mkdir()
    link = tmp_path / "root_link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        return

    with pytest.raises(SourceAccessError):
        scan_directory(link)

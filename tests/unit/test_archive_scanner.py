"""Тесты чтения каталога ZIP без распаковки."""

import zipfile
from pathlib import Path

import pytest

from report_processor.domain.exceptions import BrokenArchiveError
from report_processor.domain.statuses import StatusCode
from report_processor.inventory.archive_scanner import scan_zip_archive
from report_processor.inventory.file_manifest import build_file_manifest


def test_zip_entries_nested_paths_and_unsafe_path(tmp_path: Path) -> None:
    archive_path = tmp_path / "reports.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("empty/", b"")
        archive.writestr("КС-2.xlsx", b"one")
        archive.writestr("nested/СВВР.xlsx", b"two")
        archive.writestr("../../unsafe.xlsx", b"danger")

    before = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}
    entries = scan_zip_archive(archive_path)
    after = {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")}

    assert [entry.relative_path for entry in entries] == [
        "../../unsafe.xlsx",
        "nested/СВВР.xlsx",
        "КС-2.xlsx",
    ]
    assert all(entry.is_archive_entry for entry in entries)
    assert entries[0].warnings == [StatusCode.UNSAFE_ARCHIVE_PATH.value]
    assert "empty/" not in [entry.relative_path for entry in entries]
    assert before == after
    assert not (tmp_path / "nested").exists()


def test_windows_absolute_zip_path_is_unsafe(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe_windows.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(r"C:\absolute\file.xlsx", b"x")

    [entry] = scan_zip_archive(archive_path)

    assert StatusCode.UNSAFE_ARCHIVE_PATH.value in entry.warnings


def test_suspicious_compression_ratio(tmp_path: Path) -> None:
    archive_path = tmp_path / "compressed.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("huge.txt", b"0" * 200_000)

    [entry] = scan_zip_archive(archive_path, max_compression_ratio=10)

    assert StatusCode.SUSPICIOUS_COMPRESSION_RATIO.value in entry.warnings


def test_large_entry_warning_uses_configurable_limit(tmp_path: Path) -> None:
    archive_path = tmp_path / "large.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("large.txt", b"12345")

    [entry] = scan_zip_archive(archive_path, max_single_entry_uncompressed_size=4)

    assert StatusCode.VERY_LARGE_ARCHIVE_ENTRY.value in entry.warnings


def test_broken_zip_raises_controlled_error(tmp_path: Path) -> None:
    archive_path = tmp_path / "broken.zip"
    archive_path.write_bytes(b"not a zip")

    with pytest.raises(BrokenArchiveError):
        scan_zip_archive(archive_path)


def test_build_manifest_does_not_fallback_for_broken_zip(tmp_path: Path) -> None:
    archive_path = tmp_path / "broken.zip"
    archive_path.write_bytes(b"not a zip")

    with pytest.raises(BrokenArchiveError):
        build_file_manifest(archive_path)


def test_zip_summary_contains_sizes(tmp_path: Path) -> None:
    archive_path = tmp_path / "summary.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.txt", b"a" * 100)
        archive.writestr("b.txt", b"b" * 200)

    manifest = build_file_manifest(archive_path)

    assert manifest.source_kind == "zip"
    assert manifest.summary.total_entries == 2
    assert manifest.summary.total_uncompressed_size == 300
    assert manifest.summary.total_compressed_size is not None
    assert manifest.summary.compression_ratio is not None


def test_zip_scanner_never_reads_or_extracts_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_path = tmp_path / "metadata_only.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("КС-2.xlsx", b"content")

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"ZIP content method called: {args}, {kwargs}")

    monkeypatch.setattr(zipfile.ZipFile, "read", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extract", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", forbidden)

    entries = scan_zip_archive(archive_path)

    assert [entry.filename for entry in entries] == ["КС-2.xlsx"]


def _clear_utf8_filename_flag(zip_bytes: bytes) -> bytes:
    data = bytearray(zip_bytes)
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        position = 0
        while True:
            position = data.find(signature, position)
            if position < 0:
                break
            flag_slice = data[position + flag_offset : position + flag_offset + 2]
            current = int.from_bytes(flag_slice, "little")
            data[position + flag_offset : position + flag_offset + 2] = (current & ~0x800).to_bytes(
                2, "little"
            )
            position += 4
    return bytes(data)


def test_recovers_utf8_filename_without_zip_flag(tmp_path: Path) -> None:
    from report_processor.domain.statuses import StatusCode

    archive_path = tmp_path / "legacy_names.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("КС-2 июль.xlsx", b"x")
    archive_path.write_bytes(_clear_utf8_filename_flag(archive_path.read_bytes()))

    [entry] = scan_zip_archive(archive_path)

    assert entry.filename == "КС-2 июль.xlsx"
    assert entry.document_type == "ks2"
    assert StatusCode.ZIP_FILENAME_ENCODING_RECOVERED.value in entry.warnings


def test_macos_metadata_directory_is_temporary(tmp_path: Path) -> None:
    archive_path = tmp_path / "macos.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("__MACOSX/folder/._КС-2.xlsx", b"x")

    [entry] = scan_zip_archive(archive_path)

    assert entry.is_temporary is True

"""Минимальные проверки кодов завершения CLI."""

import zipfile
from pathlib import Path

from report_processor.cli import (
    EXIT_BROKEN_ARCHIVE,
    EXIT_OK,
    EXIT_SOURCE_NOT_FOUND,
    main,
)


def test_cli_success(tmp_path: Path, capsys: object) -> None:
    source = tmp_path / "КС-2.xlsx"
    source.write_bytes(b"data")
    output = tmp_path / "manifest.json"

    result = main(
        [
            "inventory",
            "--source",
            str(source),
            "--output",
            str(output),
            "--log-level",
            "ERROR",
        ]
    )

    assert result == EXIT_OK
    assert output.exists()
    captured = capsys.readouterr()
    assert "Найдено файлов: 1" in captured.out


def test_cli_missing_source(tmp_path: Path) -> None:
    result = main(["inventory", "--source", str(tmp_path / "missing"), "--log-level", "ERROR"])

    assert result == EXIT_SOURCE_NOT_FOUND


def test_cli_broken_zip(tmp_path: Path) -> None:
    archive_path = tmp_path / "broken.zip"
    archive_path.write_bytes(b"broken")

    result = main(["inventory", "--source", str(archive_path), "--log-level", "ERROR"])

    assert result == EXIT_BROKEN_ARCHIVE


def test_cli_valid_zip(tmp_path: Path) -> None:
    archive_path = tmp_path / "valid.zip"
    output = tmp_path / "zip.json"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("СВВР.xlsx", b"x")

    result = main(
        [
            "inventory",
            "--source",
            str(archive_path),
            "--output",
            str(output),
            "--log-level",
            "ERROR",
        ]
    )

    assert result == EXIT_OK
    assert output.exists()

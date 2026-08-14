"""Private LibreOffice recalculation for formula-free XLSX publication."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .exceptions import ExcelWriterAtomicError
from .ooxml import (
    admit_archive,
    formula_coordinates,
    materialize_formula_package,
    numeric_formula_values,
    verify_materialized_package,
    worksheet_part_map,
)

_RECALCULATION_TIMEOUT_SECONDS = 120


def recalculate_and_materialize(path: Path) -> None:
    """Recalculate a private copy, then replace all formulas with numeric literals."""

    authoritative_parts = worksheet_part_map(path)
    coordinates_by_part = _formula_coordinates(path, authoritative_parts)
    with tempfile.TemporaryDirectory(prefix="excel-writer-recalc-") as directory:
        workspace = Path(directory)
        profile = workspace / "profile"
        output_directory = workspace / "output"
        input_path = workspace / path.name
        profile.mkdir()
        output_directory.mkdir()
        shutil.copy2(path, input_path)
        _run_libreoffice(input_path, output_directory, profile)
        recalculated = output_directory / path.name
        if not recalculated.is_file():
            raise ExcelWriterAtomicError(
                "FORMULA_RECALCULATION_FAILED", "LibreOffice produced no XLSX"
            )
        values_by_part = _recalculated_values(
            recalculated, authoritative_parts, coordinates_by_part
        )
    materialize_formula_package(path, authoritative_parts, values_by_part)
    verify_materialized_package(path, values_by_part)


def _formula_coordinates(path: Path, parts: dict[str, str]) -> dict[str, tuple[str, ...]]:
    try:
        with zipfile.ZipFile(path) as package:
            admit_archive(package, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED")
            return {part: formula_coordinates(package.read(part)) for part in parts.values()}
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", str(error)) from error


def _recalculated_values(
    recalculated: Path,
    authoritative_parts: dict[str, str],
    coordinates_by_part: dict[str, tuple[str, ...]],
) -> dict[str, dict[str, str]]:
    recalculated_parts = worksheet_part_map(recalculated)
    values_by_part: dict[str, dict[str, str]] = {}
    try:
        with zipfile.ZipFile(recalculated) as package:
            admit_archive(package, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED")
            for sheet_name, authoritative_part in authoritative_parts.items():
                recalculated_part = recalculated_parts.get(sheet_name)
                if recalculated_part is None:
                    raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", sheet_name)
                values_by_part[authoritative_part] = numeric_formula_values(
                    package.read(recalculated_part), coordinates_by_part[authoritative_part]
                )
    except ExcelWriterAtomicError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", str(error)) from error
    return values_by_part


def _run_libreoffice(input_path: Path, output_directory: Path, profile: Path) -> None:
    executable = shutil.which("soffice")
    if executable is None:
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_UNAVAILABLE", "soffice not found")
    command = (
        executable,
        "--headless",
        f"-env:UserInstallation={profile.as_uri()}",
        "--convert-to",
        "xlsx",
        "--outdir",
        str(output_directory),
        str(input_path),
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=_RECALCULATION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_FAILED", "LibreOffice timed out"
        ) from error
    except OSError as error:
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_UNAVAILABLE", str(error)) from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", detail or "LibreOffice failed")

"""Private LibreOffice recalculation for formula-free XLSX publication."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from .exceptions import ExcelWriterAtomicError
from .ooxml import (
    MaterializedFormulaPackage,
    admitted_zipfile,
    formula_coordinates,
    materialize_formula_package,
    numeric_formula_values,
    read_archive_part,
    worksheet_part_map,
)

_RECALCULATION_TIMEOUT_SECONDS = 120


def recalculate_and_materialize(
    path: Path, source_descriptor: int | None = None
) -> MaterializedFormulaPackage:
    """Recalculate a private copy, then replace all formulas with numeric literals."""

    try:
        source = source_descriptor if source_descriptor is not None else path
        authoritative_parts = worksheet_part_map(
            source, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED"
        )
        coordinates_by_part = _formula_coordinates(source, authoritative_parts)
        with tempfile.TemporaryDirectory(prefix="excel-writer-recalc-") as directory:
            workspace = Path(directory)
            profile = workspace / "profile"
            output_directory = workspace / "output"
            input_path = workspace / path.name
            profile.mkdir()
            output_directory.mkdir()
            if source_descriptor is None:
                shutil.copy2(path, input_path)
            else:
                _copy_descriptor(source_descriptor, input_path)
            _run_libreoffice(input_path, output_directory, profile)
            recalculated = output_directory / path.name
            if not recalculated.is_file():
                raise ExcelWriterAtomicError(
                    "FORMULA_RECALCULATION_FAILED", "LibreOffice produced no XLSX"
                )
            values_by_part = _recalculated_values(
                recalculated, authoritative_parts, coordinates_by_part
            )
        materialized = materialize_formula_package(
            path,
            authoritative_parts,
            values_by_part,
            source_descriptor=source_descriptor,
        )
        # ``materialize_formula_package`` validates using its owned result fd;
        # pass that fd through so the engine can adopt it without reopening.
        return materialized
    except ExcelWriterAtomicError as error:
        if error.code == "FORMULA_RECALCULATION_UNAVAILABLE":
            raise
        if error.code == "FORMULA_RECALCULATION_FAILED":
            raise
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_FAILED", "formula processing failed"
        ) from error
    except Exception as error:
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_FAILED", "formula processing failed"
        ) from error


def _formula_coordinates(path: Path | int, parts: dict[str, str]) -> dict[str, tuple[str, ...]]:
    try:
        with admitted_zipfile(
            path, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED"
        ) as package:
            return {
                part: formula_coordinates(
                    read_archive_part(
                        package,
                        part,
                        ExcelWriterAtomicError,
                        "FORMULA_RECALCULATION_FAILED",
                        worksheet=True,
                    )
                )
                for part in parts.values()
            }
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_FAILED", "formula package could not be read"
        ) from error


def _recalculated_values(
    recalculated: Path,
    authoritative_parts: dict[str, str],
    coordinates_by_part: dict[str, tuple[str, ...]],
) -> dict[str, dict[str, str]]:
    recalculated_parts = worksheet_part_map(
        recalculated, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED"
    )
    values_by_part: dict[str, dict[str, str]] = {}
    try:
        with admitted_zipfile(
            recalculated, ExcelWriterAtomicError, "FORMULA_RECALCULATION_FAILED"
        ) as package:
            for sheet_name, authoritative_part in authoritative_parts.items():
                recalculated_part = recalculated_parts.get(sheet_name)
                if recalculated_part is None:
                    raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", sheet_name)
                values_by_part[authoritative_part] = numeric_formula_values(
                    read_archive_part(
                        package,
                        recalculated_part,
                        ExcelWriterAtomicError,
                        "FORMULA_RECALCULATION_FAILED",
                        worksheet=True,
                    ),
                    coordinates_by_part[authoritative_part],
                )
    except ExcelWriterAtomicError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_FAILED", "recalculated package could not be read"
        ) from error
    return values_by_part


def _copy_descriptor(descriptor: int, destination: Path) -> None:
    """Copy an already-admitted inode; never reopen its mutable pathname."""

    stream = os.fdopen(os.dup(descriptor), "rb")
    try:
        stream.seek(0)
        with destination.open("xb") as target:
            shutil.copyfileobj(stream, target, length=1_048_576)
            target.flush()
            os.fsync(target.fileno())
    finally:
        stream.close()


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
        raise ExcelWriterAtomicError(
            "FORMULA_RECALCULATION_UNAVAILABLE", "LibreOffice is unavailable"
        ) from error
    if result.returncode:
        raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", "LibreOffice failed")

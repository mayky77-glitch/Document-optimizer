"""Private LibreOffice recalculation for formula-free XLSX publication."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .exceptions import ExcelWriterAtomicError
from .ooxml import (
    materialize_formula_package,
    verify_materialized_package,
    worksheet_part_map,
)

_RECALCULATION_TIMEOUT_SECONDS = 60


def recalculate_and_materialize(path: Path) -> None:
    """Recalculate a private copy, then replace all formulas with numeric literals."""

    parts = worksheet_part_map(path)
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
        try:
            os.replace(recalculated, path)
        except OSError as error:
            raise ExcelWriterAtomicError("FORMULA_RECALCULATION_FAILED", str(error)) from error
    values_by_part = materialize_formula_package(path, parts)
    verify_materialized_package(path, values_by_part)


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

"""Файловые и диагностические вспомогательные функции."""

from __future__ import annotations

import shutil
import unicodedata
from pathlib import Path

from .constants import SAFE_FILENAME_INVALID_RE, WHITESPACE_RE


def safe_filename(value: str, fallback: str = "sheet") -> str:
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = SAFE_FILENAME_INVALID_RE.sub("_", text)
    text = WHITESPACE_RE.sub(" ", text).strip(" .")
    return text[:120] or fallback

def human_size(size_bytes: int) -> str:
    value = float(size_bytes)

    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if value < 1024 or unit == "ТБ":
            return f"{value:.1f} {unit}"
        value /= 1024

    return f"{size_bytes} Б"

def prepare_result_directory(
    output_directory: Path,
    workbook_stem: str,
    overwrite: bool,
) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    result = output_directory / f"{safe_filename(workbook_stem)}_tad"

    if result.exists():
        if overwrite:
            shutil.rmtree(result)
        else:
            counter = 2
            base = result

            while result.exists():
                result = Path(f"{base}_{counter}")
                counter += 1

    result.mkdir(parents=True, exist_ok=False)
    return result

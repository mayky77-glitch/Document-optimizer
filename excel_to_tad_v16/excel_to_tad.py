#!/usr/bin/env python3
"""Совместимый запуск: python3 excel_to_tad.py ..."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_package() -> None:
    """Явно загружает одноимённый пакет рядом с этим launcher-файлом."""
    package_directory = Path(__file__).resolve().parent / "excel_to_tad"
    spec = importlib.util.spec_from_file_location(
        "excel_to_tad",
        package_directory / "__init__.py",
        submodule_search_locations=[str(package_directory)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить пакет excel_to_tad.")

    package = importlib.util.module_from_spec(spec)
    sys.modules["excel_to_tad"] = package
    spec.loader.exec_module(package)


_load_package()
from excel_to_tad.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())

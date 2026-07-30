"""Алгоритмы определения границ и типов таблиц."""

from .generic import build_generic_trimmed_dataframe
from .ks2 import build_ks2_dataframe, is_ks2_sheet, sheet_name_has_ks2

__all__ = [
    "build_generic_trimmed_dataframe", "build_ks2_dataframe",
    "is_ks2_sheet", "sheet_name_has_ks2",
]

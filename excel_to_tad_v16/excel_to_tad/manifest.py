"""Создание manifest.json без привязки к конвертеру."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import TARGET_HEADERS

CONVERTER_VERSION = 16


def build_manifest(
    input_path: Path,
    source_reader: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    input_extension = input_path.suffix.lower()
    return {
        "source_file": str(input_path),
        "source_format": input_extension.lstrip("."),
        "source_reader": source_reader,
        "created_at": datetime.now().astimezone().isoformat(),
        "converter_version": CONVERTER_VERSION,
        "engine": (
            "modular format-aware sparse cache "
            "(.xlsx/.xlsm via openpyxl, .xlsb via pyxlsb) + in-memory Polars"
        ),
        "compression": args.compression,
        "compression_level": args.compression_level,
        "polars_threads": args.threads or "automatic",
        "schema_sample_rows": args.schema_sample_rows,
        "io_policy": {
            "intermediate_csv": False,
            "optional_csv_from_polars": args.keep_csv,
        },
        "xlsb_policy": {
            "enabled": True,
            "reader": "pyxlsb",
            "formula_values": "cached_results_saved_inside_workbook",
            "date_handling": (
                "date-formatted cells are converted when exposed by pyxlsb; "
                "older pyxlsb versions may expose Excel date serials as numbers"
            ),
        },
        "type_policy": {
            "numeric_measures": "float64",
            "numeric_rounding": None,
            "float_noise_cleanup": "adaptive_decimal_snap_with_absolute_tolerance_1e-12",
            "identifiers_numbering_and_stages": "strict_utf8_text_without_trailing_dot_zero",
            "identifier_post_write_validation": True,
            "mixed_columns": "text",
            "explicit_true_false": "boolean",
            "russian_yes_no": "text",
            "zero_one_as_boolean": "only_for_boolean_header_columns",
        },
        "other_sheets_policy": {
            "automatic_table_detection": not args.no_trim_other_sheets,
            "remove_title_and_company_blocks": not args.no_trim_other_sheets,
            "remove_signature_blocks": not args.no_trim_other_sheets,
            "skip_non_tabular_sheets": (
                not args.keep_non_tabular_sheets
                and not args.no_trim_other_sheets
            ),
        },
        "ks2_policy": {
            "sheet_name_detection": (
                "нечёткое название + сигнатура формы + "
                "структурная проверка заголовков"
            ),
            "visible_columns": TARGET_HEADERS,
            "table_boundary": "ordinal_column_from_1_until_first_non_numeric",
            "remove_signatures": True,
            "numeric_rounding": None,
            "only_detailed_rows": args.only_detailed_ks2,
        },
        "sheets": [],
        "errors": [],
    }

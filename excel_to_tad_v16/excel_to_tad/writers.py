"""Запись Parquet, необязательного CSV и проекта Tad."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .constants import TARGET_HEADERS
from .normalization import (
    is_text_identifier_header,
    stringify_identifier_cell,
)


def _force_identifier_columns_to_text(
    polars: Any,
    dataframe: Any,
) -> tuple[Any, dict[str, Any]]:
    """
    Последний защитный слой перед записью Parquet.

    Номерные, кодовые и этапные колонки принудительно пересобираются как
    String, даже если на предыдущем этапе тип был определён неверно. Значения
    вида 1.0 и ``"1.0"`` превращаются в ``"1"``; ведущие нули строковых
    кодов сохраняются.
    """
    identifier_columns: list[str] = []
    cleaned_values = 0

    for column_name in dataframe.columns:
        if not is_text_identifier_header(column_name):
            continue

        identifier_columns.append(column_name)
        source_values = dataframe.get_column(column_name).to_list()
        converted: list[str | None] = []

        for value in source_values:
            normalized_value = stringify_identifier_cell(value)
            converted.append(normalized_value)
            if value is not None and str(value) != str(normalized_value):
                cleaned_values += 1

        dataframe = dataframe.with_columns(
            polars.Series(
                column_name,
                converted,
                dtype=polars.String,
            )
        )

    return dataframe, {
        "identifier_columns_forced_to_string": identifier_columns,
        "identifier_values_normalized": cleaned_values,
    }


def _validate_identifier_columns(
    dataframe: Any,
) -> None:
    """Не допускает сохранение номерных колонок как чисел или ``1.0``."""
    invalid_examples: dict[str, list[str]] = {}

    for column_name, dtype in dataframe.schema.items():
        if not is_text_identifier_header(column_name):
            continue

        if str(dtype) not in {"String", "Utf8"}:
            raise RuntimeError(
                "Номерная колонка должна быть текстовой: "
                f"{column_name!r}, получен тип {dtype}."
            )

        examples: list[str] = []
        for value in dataframe.get_column(column_name).to_list():
            if not isinstance(value, str):
                continue
            compact = (
                value.strip()
                .replace("\xa0", "")
                .replace("\u202f", "")
                .replace(" ", "")
            )
            lowered = compact.lower()
            if lowered.endswith(".0") or lowered.endswith(",0"):
                integer_part = lowered[:-2]
                if integer_part.lstrip("+-").isdigit():
                    examples.append(value)
                    if len(examples) >= 5:
                        break

        if examples:
            invalid_examples[column_name] = examples

    if invalid_examples:
        details = "; ".join(
            f"{column}: {values}"
            for column, values in invalid_examples.items()
        )
        raise RuntimeError(
            "После нормализации в номерных колонках остались значения "
            f"с суффиксом .0: {details}"
        )


def write_dataframe_outputs(
    polars: Any,
    dataframe: Any,
    parquet_path: Path,
    csv_path: Path | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Записывает DataFrame напрямую в Parquet и проверяет итоговую схему."""
    dataframe, identifier_info = _force_identifier_columns_to_text(
        polars,
        dataframe,
    )
    _validate_identifier_columns(dataframe)

    parquet_kwargs: dict[str, Any] = {
        "compression": args.compression,
        "statistics": True,
        "row_group_size": args.row_group_size,
    }
    if args.compression in {"zstd", "gzip", "brotli"}:
        parquet_kwargs["compression_level"] = args.compression_level

    dataframe.write_parquet(parquet_path, **parquet_kwargs)
    if csv_path is not None:
        dataframe.write_csv(csv_path)

    written_schema = polars.read_parquet_schema(parquet_path)
    for column_name in identifier_info["identifier_columns_forced_to_string"]:
        written_dtype = written_schema.get(column_name)
        if str(written_dtype) not in {"String", "Utf8"}:
            parquet_path.unlink(missing_ok=True)
            if csv_path is not None:
                csv_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Проверка записанного Parquet не пройдена: колонка "
                f"{column_name!r} имеет тип {written_dtype}, а не String."
            )

    return {
        "schema_mode": "semantic_typed_in_memory_v16",
        "parquet_rows": dataframe.height,
        "parquet_columns": dataframe.width,
        "parquet_schema": {
            name: str(dtype)
            for name, dtype in written_schema.items()
        },
        "identifier_validation": "passed",
        **identifier_info,
    }


def write_tad_project(
    parquet_path: Path,
    tad_path: Path,
) -> None:
    """
    Создаёт готовое представление Tad.
    Открывать следует файл .tad, а не .parquet.
    """
    project = {
        "tadFileFormatVersion": 1,
        "contents": {
            "targetPath": str(parquet_path.resolve()),
            "viewParams": {
                "aggMap": {},
                "columnFormats": {},
                "defaultFormats": {
                    "boolean": {
                        "commas": True,
                        "decimalPlaces": 0,
                    },
                    "integer": {
                        "commas": True,
                        "decimalPlaces": 0,
                    },
                    "real": {
                        "commas": True,
                    },
                    "text": {
                        "urlsAsHyperlinks": True,
                    },
                },
                "displayColumns": TARGET_HEADERS,
                "openPaths": {
                    "_rep": {},
                },
                "pivotLeafColumn": None,
                "showHiddenCols": False,
                "showRoot": False,
                "sortKey": [],
                "vpivots": [],
            },
        },
    }

    tad_path.write_text(
        json.dumps(
            project,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

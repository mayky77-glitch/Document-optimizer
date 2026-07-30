"""Оркестрация преобразования книги по одному листу."""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .constants import SUPPORTED_EXTENSIONS
from .dataframe import build_full_cached_sheet_dataframe
from .detection import (
    build_generic_trimmed_dataframe,
    build_ks2_dataframe,
    is_ks2_sheet,
    sheet_name_has_ks2,
)
from .manifest import build_manifest
from .models import CachedWorksheet
from .readers import open_source_workbook
from .utils import human_size, prepare_result_directory, safe_filename
from .writers import write_dataframe_outputs, write_tad_project


def _validate_args(args: argparse.Namespace) -> None:
    if args.threads < 0:
        raise ValueError("--threads не может быть меньше 0")
    if args.schema_sample_rows <= 0:
        raise ValueError("--schema-sample-rows должен быть больше 0")
    if args.row_group_size <= 0:
        raise ValueError("--row-group-size должен быть больше 0")


def _empty_extraction(polars: Any, warning: str) -> tuple[Any, dict[str, Any]]:
    return polars.DataFrame(), {
        "mode": "skipped_non_tabular",
        "written_rows": 0,
        "columns": 0,
        "generic_trim_warning": warning,
    }


def _extract_sheet(
    polars: Any,
    worksheet: CachedWorksheet,
    sheet_name: str,
    args: argparse.Namespace,
    prefix: str,
) -> tuple[Any, dict[str, Any], bool]:
    ks2_name_hint = sheet_name_has_ks2(sheet_name)
    ks2_mode = is_ks2_sheet(sheet_name, worksheet)

    if ks2_mode:
        print(f"{prefix} Возможная форма КС-2: проверяю структуру заголовков.")
        try:
            dataframe, extraction = build_ks2_dataframe(
                polars, worksheet, only_detailed=args.only_detailed_ks2
            )
            print(
                f"{prefix} Структура КС-2 подтверждена: "
                "создаю компактное представление."
            )
            return dataframe, extraction, True
        except ValueError as detection_error:
            if args.strict_ks2:
                raise
            ks2_mode = False
            print(
                f"{prefix} Структура КС-2 не подтверждена. "
                f"Причина: {detection_error}",
                file=sys.stderr,
            )
            warning = str(detection_error)
    else:
        warning = ""

    if not args.no_trim_other_sheets:
        try:
            dataframe, extraction = build_generic_trimmed_dataframe(
                polars, worksheet
            )
        except ValueError as generic_error:
            if args.keep_non_tabular_sheets:
                dataframe, extraction = build_full_cached_sheet_dataframe(
                    polars, worksheet
                )
                extraction["generic_trim_warning"] = str(generic_error)
            else:
                dataframe, extraction = _empty_extraction(
                    polars, str(generic_error)
                )
    else:
        dataframe, extraction = build_full_cached_sheet_dataframe(
            polars, worksheet
        )

    if warning:
        extraction["ks2_detection_warning"] = warning
    elif ks2_name_hint:
        extraction["ks2_detection_warning"] = (
            "Название содержит КС-2, но лист исключён "
            "как реестр/журнал/сводный лист."
        )

    return dataframe, extraction, ks2_mode


def convert(args: argparse.Namespace) -> Path:
    _validate_args(args)
    if args.threads > 0:
        os.environ["POLARS_MAX_THREADS"] = str(args.threads)

    try:
        import polars as pl
    except ImportError as exc:
        raise RuntimeError(
            "Не установлен polars. Выполните:\n"
            "python3 -m pip install --upgrade polars openpyxl pyxlsb"
        ) from exc

    input_path = Path(args.input_file).expanduser().resolve()
    output_directory = Path(args.output_directory).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Файл не найден: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Указан не файл: {input_path}")
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Поддерживаются только .xlsx, .xlsm и .xlsb")

    source = open_source_workbook(input_path)
    result_directory = prepare_result_directory(
        output_directory, input_path.stem, args.overwrite
    )
    manifest = build_manifest(input_path, source.source_reader, args)
    total_started = time.perf_counter()

    print(f"Исходный файл: {input_path}")
    print(f"Формат: {input_path.suffix.lower()} ({source.source_reader})")
    print(f"Результат: {result_directory}")
    print("Открываю книгу…")

    try:
        print(f"Листов: {len(source.sheet_names)}")
        for order, sheet_name in enumerate(source.sheet_names, start=1):
            started = time.perf_counter()
            prefix = f"[{order}/{len(source.sheet_names)}]"
            safe_sheet = safe_filename(sheet_name, f"sheet_{order}")
            parquet_path = result_directory / f"{order:03d}_{safe_sheet}.parquet"
            csv_path = (
                result_directory / f"{order:03d}_{safe_sheet}.csv"
                if args.keep_csv
                else None
            )
            print(f"\n{prefix} {sheet_name!r}")
            worksheet: CachedWorksheet | None = None
            dataframe: Any = None

            try:
                cache_started = time.perf_counter()
                worksheet = source.cache_sheet(sheet_name)
                cache_elapsed = time.perf_counter() - cache_started
                print(
                    f"{prefix} Лист прочитан один раз: "
                    f"{worksheet.max_row:,} строк × "
                    f"{worksheet.max_column:,} столбцов "
                    f"за {cache_elapsed:.2f} сек."
                )

                dataframe, extraction, ks2_mode = _extract_sheet(
                    pl, worksheet, sheet_name, args, prefix
                )
                extraction["cache_seconds"] = round(cache_elapsed, 3)
                extraction["cached_nonempty_rows"] = worksheet.max_row
                extraction["cached_used_columns"] = worksheet.max_column
                extraction["source_reader"] = source.source_reader

                if extraction.get("written_rows", 0) == 0:
                    skip_reason = extraction.get(
                        "generic_trim_warning", "Нет строк данных."
                    )
                    print(f"{prefix} Лист пропущен: {skip_reason}")
                    manifest["sheets"].append(
                        {
                            "sheet_name": sheet_name,
                            "status": "skipped_empty",
                            **extraction,
                        }
                    )
                    continue

                parquet_info = write_dataframe_outputs(
                    pl,
                    dataframe,
                    parquet_path,
                    csv_path,
                    args,
                )
                expected_rows = int(extraction["written_rows"])
                actual_rows = int(parquet_info["parquet_rows"])
                if expected_rows != actual_rows:
                    parquet_path.unlink(missing_ok=True)
                    if csv_path is not None:
                        csv_path.unlink(missing_ok=True)
                    raise RuntimeError(
                        "Количество строк не совпало: "
                        f"ожидалось {expected_rows:,}, записано {actual_rows:,}."
                    )

                tad_path: Path | None = None
                if ks2_mode:
                    tad_path = parquet_path.with_suffix(".tad")
                    write_tad_project(parquet_path, tad_path)

                elapsed = time.perf_counter() - started
                size_bytes = parquet_path.stat().st_size
                manifest["sheets"].append(
                    {
                        "sheet_name": sheet_name,
                        "sheet_id": order,
                        "status": "converted",
                        "file_name": parquet_path.name,
                        "csv_file": csv_path.name if csv_path else None,
                        "tad_project": tad_path.name if tad_path else None,
                        "size_bytes": size_bytes,
                        "elapsed_seconds": round(elapsed, 3),
                        **extraction,
                        **parquet_info,
                    }
                )
                print(
                    f"{prefix} Готово: {actual_rows:,} строк, "
                    f"{human_size(size_bytes)}, {elapsed:.1f} сек."
                )
                if tad_path is not None:
                    print(f"{prefix} Открывай в Tad: {tad_path.name}")

            except Exception as exc:
                parquet_path.unlink(missing_ok=True)
                parquet_path.with_suffix(".tad").unlink(missing_ok=True)
                if csv_path is not None:
                    csv_path.unlink(missing_ok=True)
                error_message = f"{type(exc).__name__}: {exc}"
                manifest["errors"].append(
                    {
                        "sheet_name": sheet_name,
                        "sheet_id": order,
                        "error": error_message,
                    }
                )
                print(f"{prefix} Ошибка: {error_message}", file=sys.stderr)
            finally:
                del dataframe
                del worksheet
                gc.collect()
    finally:
        source.close()

    total_elapsed = time.perf_counter() - total_started
    manifest["elapsed_seconds"] = round(total_elapsed, 3)
    manifest["successful_sheets"] = sum(
        1 for item in manifest["sheets"] if item.get("status") == "converted"
    )
    manifest["total_sheets"] = len(source.sheet_names)
    manifest_path = result_directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 68)
    print(
        f"Преобразовано: {manifest['successful_sheets']} "
        f"из {manifest['total_sheets']} листов"
    )
    print(f"Время: {total_elapsed:.1f} сек.")
    print(f"Папка: {result_directory}")
    print(f"Отчёт: {manifest_path}")
    if manifest["errors"]:
        print(
            f"Ошибок: {len(manifest['errors'])}. Подробности в manifest.json.",
            file=sys.stderr,
        )
    if manifest["successful_sheets"] == 0:
        raise RuntimeError("Не удалось преобразовать ни одного листа.")
    return result_directory

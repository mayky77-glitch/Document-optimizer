from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from report_processor.report_serialization import save_inspection_report

from .exceptions import ExtractionSerializationError
from .models import CanonicalSourceRow, ExtractionResult, JsonlWriteResult

SCHEMA_VERSION = "6.0"


def _to_json_compatible(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_json_compatible(item) for key, item in asdict(value).items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, tuple | list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    return value


def _atomic_write_json(data: Any, output_path: Path) -> None:
    save_inspection_report(_to_json_compatible(data), output_path)


def _meta_path(output_path: Path) -> Path:
    return output_path.with_suffix(".meta.json")


def save_extraction_result_json(result: ExtractionResult, output_path: Path) -> None:
    try:
        _atomic_write_json(result, Path(output_path))
    except Exception as exc:
        raise ExtractionSerializationError(
            f"Не удалось сохранить JSON результата {output_path}: {exc}"
        ) from exc


def _write_rows_to_temp(
    rows: Iterable[CanonicalSourceRow],
    *,
    output_path: Path,
) -> tuple[Path, int, int, CanonicalSourceRow | None]:
    temporary_path: Path | None = None
    count = 0
    first_row: CanonicalSourceRow | None = None
    completed = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            for row in rows:
                if first_row is None:
                    first_row = row
                payload = json.dumps(
                    _to_json_compatible(row),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                stream.write(payload)
                stream.write("\n")
                count += 1
            stream.flush()
            os.fsync(stream.fileno())
        completed = True
        return temporary_path, count, temporary_path.stat().st_size, first_row
    except (OSError, TypeError, ValueError) as exc:
        raise ExtractionSerializationError(f"Ошибка потоковой записи JSONL: {exc}") from exc
    finally:
        if not completed and temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _write_json_to_temp(data: Any, *, output_path: Path) -> Path:
    temporary_path: Path | None = None
    completed = False
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(
                _to_json_compatible(data),
                stream,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        completed = True
        return temporary_path
    except (OSError, TypeError, ValueError) as exc:
        raise ExtractionSerializationError(f"Ошибка потоковой записи метаданных: {exc}") from exc
    finally:
        if not completed and temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _reserve_sibling_path(path: Path, *, suffix: str) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=suffix,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    temporary_path.unlink()
    return temporary_path


def _replace_jsonl_pair(
    *,
    rows_temp_path: Path,
    metadata_temp_path: Path,
    output_path: Path,
    meta_path: Path,
) -> None:
    targets = (output_path, meta_path)
    staged = (rows_temp_path, metadata_temp_path)
    backups: dict[Path, Path] = {}
    committed: set[Path] = set()
    try:
        for target in targets:
            if target.exists():
                backup_path = _reserve_sibling_path(target, suffix=".bak")
                target.replace(backup_path)
                backups[target] = backup_path
        for staged_path, target in zip(staged, targets, strict=True):
            staged_path.replace(target)
            committed.add(target)
    except OSError as exc:
        rollback_errors: list[OSError] = []
        for target in targets:
            try:
                if target in committed:
                    target.unlink(missing_ok=True)
                backup_path = backups.get(target)
                if backup_path is not None:
                    backup_path.replace(target)
            except OSError as rollback_exc:
                rollback_errors.append(rollback_exc)
        if rollback_errors:
            raise ExtractionSerializationError(
                f"Не удалось завершить запись JSONL и восстановить прежнюю пару: {exc}; "
                f"rollback: {rollback_errors[0]}"
            ) from exc
        raise ExtractionSerializationError(f"Не удалось завершить запись JSONL: {exc}") from exc
    finally:
        for path in (*staged, *backups.values()):
            path.unlink(missing_ok=True)


def _default_metadata(
    *,
    first_row: CanonicalSourceRow | None,
    total_rows: int,
) -> dict[str, Any]:
    if first_row is None:
        source_file_id = ""
        filename = ""
        sheet_results: list[dict[str, Any]] = []
    else:
        location = first_row.source_location
        source_file_id = location.source_file_id
        filename = location.filename
        sheet_results = [
            {
                "sheet_name": location.sheet_name,
                "sheet_type": first_row.source_type,
                "scanned_row_count": None,
                "extracted_row_count": total_rows,
                "status": "STREAM_ONLY",
            }
        ]
    return {
        "source_file_id": source_file_id,
        "filename": filename,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "total_rows": total_rows,
        "sheet_results": sheet_results,
        "warnings": [],
    }


def save_rows_jsonl(
    rows: Iterable[CanonicalSourceRow],
    output_path: Path,
    *,
    metadata: dict[str, Any] | None = None,
    metadata_factory: Callable[[int], dict[str, Any]] | None = None,
) -> JsonlWriteResult:
    if metadata is not None and metadata_factory is not None:
        raise ValueError("Нельзя одновременно передать metadata и metadata_factory")
    output_path = Path(output_path)
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExtractionSerializationError(
            f"Не удалось создать каталог для JSONL {output_path.parent}: {exc}"
        ) from exc
    temp_path, count, bytes_written, first_row = _write_rows_to_temp(
        rows,
        output_path=output_path,
    )
    meta_path = _meta_path(output_path)
    committed = False
    try:
        if metadata_factory is not None:
            meta_payload = metadata_factory(count)
        else:
            meta_payload = metadata or _default_metadata(
                first_row=first_row,
                total_rows=count,
            )
        meta_payload = {**meta_payload, "total_rows": count}
        metadata_temp_path = _write_json_to_temp(meta_payload, output_path=meta_path)
        _replace_jsonl_pair(
            rows_temp_path=temp_path,
            metadata_temp_path=metadata_temp_path,
            output_path=output_path,
            meta_path=meta_path,
        )
        committed = True
    except ExtractionSerializationError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        raise ExtractionSerializationError(f"Не удалось завершить запись JSONL: {exc}") from exc
    finally:
        if not committed:
            temp_path.unlink(missing_ok=True)
    return JsonlWriteResult(output_path, meta_path, count, bytes_written)


def build_extraction_metadata(results: tuple[ExtractionResult, ...]) -> dict[str, Any]:
    first = results[0] if results else None
    warnings: list[str] = []
    sheet_results = []
    total_rows = 0
    for result in results:
        total_rows += result.extracted_row_count
        warnings.extend(result.warnings)
        sheet_results.append(
            {
                "sheet_name": result.sheet_name,
                "sheet_type": result.sheet_type.value,
                "scanned_row_count": result.scanned_row_count,
                "extracted_row_count": result.extracted_row_count,
                "skipped_empty_row_count": result.skipped_empty_row_count,
                "skipped_header_row_count": result.skipped_header_row_count,
                "failed_row_count": result.failed_row_count,
                "stop_reason": result.stop_reason,
                "status": result.status,
            }
        )
    return {
        "source_file_id": first.source_file_id if first else "",
        "filename": first.filename if first else "",
        "created_at": datetime.now(UTC).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "total_rows": total_rows,
        "sheet_results": sheet_results,
        "warnings": list(dict.fromkeys(warnings)),
    }


def save_extraction_results_jsonl(
    results: tuple[ExtractionResult, ...],
    output_path: Path,
) -> JsonlWriteResult:
    rows = (row for result in results for row in result.rows)
    return save_rows_jsonl(rows, output_path, metadata=build_extraction_metadata(results))


def save_extraction_results_json(
    results: tuple[ExtractionResult, ...],
    output_path: Path,
) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "sheet_results": results,
    }
    try:
        _atomic_write_json(payload, Path(output_path))
    except (OSError, TypeError, ValueError) as exc:
        raise ExtractionSerializationError(f"Не удалось сохранить JSON: {exc}") from exc

"""Сериализация и атомарное хранение файлового манифеста."""

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from report_processor.domain.exceptions import ManifestReadError, ManifestWriteError
from report_processor.domain.models import (
    MANIFEST_SCHEMA_VERSION,
    FileManifest,
    FileManifestEntry,
    ManifestSummary,
)
from report_processor.domain.statuses import StatusCode

LOGGER = logging.getLogger(__name__)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Объект типа {type(value).__name__} не поддерживается JSON")


def manifest_to_dict(manifest: FileManifest) -> dict[str, Any]:
    """Преобразовать манифест в JSON-совместимый словарь."""

    return json.loads(json.dumps(asdict(manifest), default=_json_default))


def _parse_datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} должен быть строкой ISO 8601 или null")
    return datetime.fromisoformat(value)


def _string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} должен быть списком строк")
    return list(value)


def _string_int_dict(value: Any, field_name: str) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} должен быть объектом")
    result: dict[str, int] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"{field_name} должен содержать пары строка → целое число")
        result[key] = item
    return result


def _required(mapping: Mapping[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"отсутствует обязательное поле {key}")
    return mapping[key]


def _required_str(mapping: Mapping[str, Any], key: str) -> str:
    value = _required(mapping, key)
    if not isinstance(value, str):
        raise ValueError(f"{key} должен быть строкой")
    return value


def _required_bool(mapping: Mapping[str, Any], key: str) -> bool:
    value = _required(mapping, key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} должен быть логическим значением")
    return value


def _required_int(mapping: Mapping[str, Any], key: str) -> int:
    value = _required(mapping, key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} должен быть целым числом")
    return value


def _required_datetime(mapping: Mapping[str, Any], key: str) -> datetime:
    value = _parse_datetime(_required(mapping, key), key)
    if value is None:
        raise ValueError(f"{key} не может быть null")
    return value


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} должен быть целым числом или null")
    return value


def _entry_from_dict(payload: Mapping[str, Any]) -> FileManifestEntry:
    warnings = _string_list(_required(payload, "warnings"), "warnings")
    for warning in warnings:
        StatusCode(warning)
    status = _required_str(payload, "status")
    if status not in {
        StatusCode.OK.value,
        StatusCode.WARNING.value,
        StatusCode.UNREADABLE_FILE.value,
    }:
        raise ValueError(f"недопустимый статус записи: {status}")

    return FileManifestEntry(
        file_id=_required_str(payload, "file_id"),
        source_type=_required_str(payload, "source_type"),
        source_root=_required_str(payload, "source_root"),
        relative_path=_required_str(payload, "relative_path"),
        filename=_required_str(payload, "filename"),
        extension=_required_str(payload, "extension"),
        size_bytes=_optional_int(payload.get("size_bytes"), "size_bytes"),
        compressed_size_bytes=_optional_int(
            payload.get("compressed_size_bytes"), "compressed_size_bytes"
        ),
        modified_at=_parse_datetime(payload.get("modified_at"), "modified_at"),
        crc32=_optional_int(payload.get("crc32"), "crc32"),
        is_archive_entry=_required_bool(payload, "is_archive_entry"),
        archive_path=(
            None
            if payload.get("archive_path") is None
            else _required_str(payload, "archive_path")
        ),
        document_type=_required_str(payload, "document_type"),
        document_markers=_string_list(
            _required(payload, "document_markers"), "document_markers"
        ),
        is_temporary=_required_bool(payload, "is_temporary"),
        is_probable_copy=_required_bool(payload, "is_probable_copy"),
        is_probably_outdated=_required_bool(payload, "is_probably_outdated"),
        status=status,
        warnings=warnings,
    )


def _summary_from_dict(payload: Mapping[str, Any]) -> ManifestSummary:
    return ManifestSummary(
        total_entries=_required_int(payload, "total_entries"),
        total_size_bytes=_required_int(payload, "total_size_bytes"),
        files_by_extension=_string_int_dict(
            _required(payload, "files_by_extension"), "files_by_extension"
        ),
        files_by_document_type=_string_int_dict(
            _required(payload, "files_by_document_type"), "files_by_document_type"
        ),
        files_by_document_marker=_string_int_dict(
            payload.get("files_by_document_marker", {}), "files_by_document_marker"
        ),
        temporary_files=_required_int(payload, "temporary_files"),
        probable_copies=_required_int(payload, "probable_copies"),
        probably_outdated_files=_required_int(payload, "probably_outdated_files"),
        unsafe_archive_entries=_required_int(payload, "unsafe_archive_entries"),
        warnings_count=_required_int(payload, "warnings_count"),
        unreadable_files=_optional_int(payload.get("unreadable_files", 0), "unreadable_files") or 0,
        total_compressed_size=_optional_int(
            payload.get("total_compressed_size"), "total_compressed_size"
        ),
        total_uncompressed_size=_optional_int(
            payload.get("total_uncompressed_size"), "total_uncompressed_size"
        ),
        compression_ratio=(
            None
            if payload.get("compression_ratio") is None
            else float(payload["compression_ratio"])
        ),
    )


def manifest_from_dict(payload: Mapping[str, Any]) -> FileManifest:
    """Восстановить типизированный манифест из словаря с проверкой контракта."""

    entries_payload = _required(payload, "entries")
    summary_payload = _required(payload, "summary")
    if not isinstance(entries_payload, list):
        raise ValueError("entries должен быть списком")
    if not isinstance(summary_payload, Mapping):
        raise ValueError("summary должен быть объектом")

    entries: list[FileManifestEntry] = []
    for item in entries_payload:
        if not isinstance(item, Mapping):
            raise ValueError("каждый элемент entries должен быть объектом")
        entries.append(_entry_from_dict(item))

    source_kind = _required_str(payload, "source_kind")
    if source_kind not in {"directory", "zip", "file"}:
        raise ValueError(f"неподдерживаемый source_kind: {source_kind}")
    schema_version = payload.get("schema_version", MANIFEST_SCHEMA_VERSION)
    if not isinstance(schema_version, str):
        raise ValueError("schema_version должен быть строкой")

    summary = _summary_from_dict(summary_payload)
    if summary.total_entries != len(entries):
        raise ValueError("summary.total_entries не совпадает с количеством entries")

    return FileManifest(
        source_path=_required_str(payload, "source_path"),
        source_kind=source_kind,
        created_at=_required_datetime(payload, "created_at"),
        entries=entries,
        summary=summary,
        schema_version=schema_version,
    )


def save_manifest_json(manifest: FileManifest, output_path: Path) -> None:
    """Атомарно сохранить манифест в читаемый UTF-8 JSON."""

    output_path = output_path.expanduser()
    temporary_path: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
        )
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    except (OSError, TypeError, ValueError) as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                LOGGER.warning("Не удалось удалить временный файл: %s", temporary_path)
        raise ManifestWriteError(output_path, str(exc)) from exc

    LOGGER.info("Манифест сохранён: %s", output_path)


def load_manifest_json(input_path: Path) -> FileManifest:
    """Прочитать JSON-манифест и проверить его типизированный контракт."""

    input_path = input_path.expanduser()
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("корневое значение должно быть объектом")
        return manifest_from_dict(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ManifestReadError(input_path, str(exc)) from exc

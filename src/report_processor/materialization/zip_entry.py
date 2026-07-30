from __future__ import annotations

import logging
import zipfile
from pathlib import Path

from report_processor.domain.exceptions import MaterializationError, UnsafeArchiveEntryError
from report_processor.domain.models import FileManifestEntry
from report_processor.domain.statuses import StatusCode

from .models import MaterializedSource
from .safety import is_unsafe_archive_path, safe_local_filename
from .source_resolver import archive_entry_path

LOGGER = logging.getLogger(__name__)
_CHUNK_SIZE = 1024 * 1024
_RECOGNIZED_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}


def _copy_limited(source, destination, limit: int) -> int:
    total = 0
    while True:
        chunk = source.read(_CHUNK_SIZE)
        if not chunk:
            return total
        total += len(chunk)
        if total > limit:
            raise MaterializationError(
                StatusCode.ARCHIVE_ENTRY_TOO_LARGE,
                f"Фактический поток превысил лимит {limit} байт",
            )
        destination.write(chunk)


def materialize_zip_entry(
    entry: FileManifestEntry,
    workspace: Path,
    *,
    max_file_size_bytes: int,
    verify_crc: bool = True,
) -> MaterializedSource:
    if is_unsafe_archive_path(entry.relative_path):
        raise UnsafeArchiveEntryError(
            StatusCode.UNSAFE_ARCHIVE_PATH,
            f"Опасный внутренний путь ZIP: {entry.relative_path}",
        )

    archive_path = archive_entry_path(entry)
    if not archive_path.exists() or not archive_path.is_file():
        raise MaterializationError(
            StatusCode.ARCHIVE_NOT_FOUND,
            f"ZIP-архив не найден: {archive_path}",
        )

    extension = (entry.extension or Path(entry.relative_path).suffix).lower()
    if extension not in _RECOGNIZED_EXCEL_EXTENSIONS:
        raise MaterializationError(
            StatusCode.UNSUPPORTED_EXCEL_FORMAT,
            f"Неподдерживаемое расширение Excel: {extension or '<none>'}",
        )

    output_name = safe_local_filename(entry.file_id, entry.relative_path, extension)
    output_path = workspace / output_name
    warnings: list[str] = []

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            try:
                info = archive.getinfo(entry.relative_path)
            except KeyError as error:
                raise MaterializationError(
                    StatusCode.ARCHIVE_ENTRY_NOT_FOUND,
                    f"Запись не найдена в ZIP: {entry.relative_path}",
                ) from error

            if info.is_dir():
                raise MaterializationError(
                    StatusCode.ARCHIVE_ENTRY_NOT_FOUND,
                    "Выбранная ZIP-запись является каталогом",
                )
            if info.file_size > max_file_size_bytes:
                raise MaterializationError(
                    StatusCode.ARCHIVE_ENTRY_TOO_LARGE,
                    f"Заявленный размер записи {info.file_size} превышает лимит",
                )
            if entry.size_bytes is not None and entry.size_bytes != info.file_size:
                warnings.append(StatusCode.FILE_METADATA_CHANGED.value)
            if entry.crc32 is not None and entry.crc32 != info.CRC:
                warnings.append(StatusCode.FILE_METADATA_CHANGED.value)

            try:
                with archive.open(info, "r") as source, output_path.open("xb") as destination:
                    actual_size = _copy_limited(source, destination, max_file_size_bytes)
            except zipfile.BadZipFile as error:
                status = (
                    StatusCode.CRC_MISMATCH
                    if "CRC" in str(error).upper() and verify_crc
                    else StatusCode.BROKEN_ARCHIVE
                )
                raise MaterializationError(status, f"Ошибка чтения ZIP-записи: {error}") from error

            if actual_size != info.file_size:
                warnings.append(StatusCode.FILE_METADATA_CHANGED.value)
            LOGGER.debug("ZIP entry materialized to %s", output_path)
    except zipfile.BadZipFile as error:
        raise MaterializationError(
            StatusCode.BROKEN_ARCHIVE,
            f"Повреждённый ZIP-архив: {error}",
        ) from error
    except BaseException:
        output_path.unlink(missing_ok=True)
        raise

    return MaterializedSource(
        local_path=output_path,
        original_file_id=entry.file_id,
        original_relative_path=entry.relative_path,
        source_kind="zip_entry",
        archive_path=str(archive_path),
        was_extracted=True,
        temporary=True,
        size_bytes=actual_size,
        extension=extension,
        cleanup_required=True,
        warnings=tuple(dict.fromkeys(warnings)),
    )

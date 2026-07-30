from __future__ import annotations

from report_processor.domain.exceptions import MaterializationError
from report_processor.domain.models import FileManifestEntry
from report_processor.domain.statuses import StatusCode

from .models import MaterializedSource
from .source_resolver import regular_entry_path

_RECOGNIZED_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".xlsb", ".ods"}


def resolve_regular_file(
    entry: FileManifestEntry,
    *,
    max_file_size_bytes: int,
) -> MaterializedSource:
    path = regular_entry_path(entry)
    if path.is_symlink():
        raise MaterializationError(
            StatusCode.SYMLINK_NOT_ALLOWED,
            "Символическая ссылка не разрешена для безопасного чтения",
        )
    if not path.exists() or not path.is_file():
        raise MaterializationError(
            StatusCode.SOURCE_FILE_NOT_FOUND,
            f"Файл-источник не найден: {entry.relative_path}",
        )

    stat = path.stat()
    if stat.st_size > max_file_size_bytes:
        raise MaterializationError(
            StatusCode.FILE_TOO_LARGE,
            f"Размер файла {stat.st_size} превышает лимит {max_file_size_bytes}",
        )

    extension = (entry.extension or path.suffix).lower()
    if extension not in _RECOGNIZED_EXCEL_EXTENSIONS:
        raise MaterializationError(
            StatusCode.UNSUPPORTED_EXCEL_FORMAT,
            f"Неподдерживаемое расширение Excel: {extension or '<none>'}",
        )

    warnings: list[str] = []
    if entry.size_bytes is not None and entry.size_bytes != stat.st_size:
        warnings.append(StatusCode.FILE_METADATA_CHANGED.value)

    return MaterializedSource(
        local_path=path,
        original_file_id=entry.file_id,
        original_relative_path=entry.relative_path,
        source_kind="regular_file",
        archive_path=None,
        was_extracted=False,
        temporary=False,
        size_bytes=stat.st_size,
        extension=extension,
        cleanup_required=False,
        warnings=tuple(warnings),
    )

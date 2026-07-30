"""Сканирование обычных файлов и каталогов без чтения содержимого."""

import hashlib
import logging
import os
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from report_processor.domain.exceptions import SourceAccessError, SourceNotFoundError
from report_processor.domain.models import FileManifestEntry
from report_processor.domain.statuses import StatusCode
from report_processor.inventory.file_classifier import classify_file_by_name

LOGGER = logging.getLogger(__name__)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def _absolute_path_text(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path.absolute())


def _regular_file_id(path: Path, size: int | None, modified_ns: int | None) -> str:
    return _sha256_text(f"{_absolute_path_text(path)}\0{size}\0{modified_ns}")


def _entry_status(warnings: list[str]) -> str:
    if StatusCode.UNREADABLE_FILE.value in warnings:
        return StatusCode.UNREADABLE_FILE.value
    if warnings:
        return StatusCode.WARNING.value
    return StatusCode.OK.value


def create_file_entry(path: Path, source_root: Path, relative_path: Path) -> FileManifestEntry:
    """Создать запись манифеста для одного обычного файла без чтения содержимого."""

    warnings: list[str] = []
    size: int | None = None
    modified_at: datetime | None = None
    modified_ns: int | None = None

    try:
        stat_result = path.stat(follow_symlinks=False)
        size = stat_result.st_size
        modified_ns = stat_result.st_mtime_ns
        modified_at = datetime.fromtimestamp(stat_result.st_mtime, tz=UTC)
    except OSError as exc:
        warnings.append(StatusCode.UNREADABLE_FILE.value)
        LOGGER.warning("Не удалось прочитать метаданные файла %s: %s", path, exc)

    classification = classify_file_by_name(path.name)
    return FileManifestEntry(
        file_id=_regular_file_id(path, size, modified_ns),
        source_type="file",
        source_root=_absolute_path_text(source_root),
        relative_path=relative_path.as_posix(),
        filename=path.name,
        extension=path.suffix.casefold(),
        size_bytes=size,
        compressed_size_bytes=None,
        modified_at=modified_at,
        crc32=None,
        is_archive_entry=False,
        archive_path=None,
        document_type=classification.document_type,
        document_markers=list(classification.document_markers),
        is_temporary=classification.is_temporary,
        is_probable_copy=classification.is_probable_copy,
        is_probably_outdated=classification.is_probably_outdated,
        status=_entry_status(warnings),
        warnings=warnings,
    )


def _iter_directory_files(directory_path: Path, recursive: bool) -> list[tuple[Path, Path]]:
    found: list[tuple[Path, Path]] = []

    def visit(current: Path) -> None:
        try:
            with os.scandir(current) as iterator:
                directory_entries = sorted(
                    iterator, key=lambda item: (item.name.casefold(), item.name)
                )
        except OSError as exc:
            if current == directory_path:
                raise SourceAccessError(directory_path, str(exc)) from exc
            LOGGER.warning("Недоступный вложенный каталог пропущен: %s (%s)", current, exc)
            return

        for item in directory_entries:
            item_path = Path(item.path)
            try:
                if item.is_symlink():
                    LOGGER.debug("Символическая ссылка пропущена: %s", item_path)
                    continue
                if item.is_file(follow_symlinks=False):
                    found.append((item_path, item_path.relative_to(directory_path)))
                elif recursive and item.is_dir(follow_symlinks=False):
                    visit(item_path)
            except OSError as exc:
                LOGGER.warning("Не удалось исследовать путь %s: %s", item_path, exc)

    visit(directory_path)
    return found


def _duplicate_key(entry: FileManifestEntry) -> tuple[str, int | None, str]:
    normalized_filename = unicodedata.normalize("NFKC", entry.filename).casefold()
    normalized_filename = " ".join(normalized_filename.split())
    return normalized_filename, entry.size_bytes, entry.extension


def mark_possible_duplicates(entries: list[FileManifestEntry]) -> None:
    """Пометить кандидатов в дубли без сравнения содержимого файлов."""

    grouped: dict[tuple[str, int | None, str], list[FileManifestEntry]] = defaultdict(list)
    for entry in entries:
        if entry.size_bytes is not None:
            grouped[_duplicate_key(entry)].append(entry)

    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        for entry in candidates:
            warning = StatusCode.POSSIBLE_DUPLICATE.value
            if warning not in entry.warnings:
                entry.warnings.append(warning)
            if entry.status == StatusCode.OK.value:
                entry.status = StatusCode.WARNING.value


def scan_directory(directory_path: Path, recursive: bool = True) -> list[FileManifestEntry]:
    """Построить детерминированный список файлов каталога без перехода по ссылкам."""

    directory_path = directory_path.expanduser()
    if not directory_path.exists():
        raise SourceNotFoundError(directory_path)
    if directory_path.is_symlink():
        raise SourceAccessError(directory_path, "символические ссылки не поддерживаются")
    if not directory_path.is_dir():
        raise SourceAccessError(directory_path, "путь не является каталогом")

    entries = [
        create_file_entry(path, directory_path, relative_path)
        for path, relative_path in _iter_directory_files(directory_path, recursive)
    ]
    entries.sort(key=lambda entry: (entry.relative_path.casefold(), entry.relative_path))
    mark_possible_duplicates(entries)
    LOGGER.info("В каталоге %s найдено файлов: %d", directory_path, len(entries))
    return entries

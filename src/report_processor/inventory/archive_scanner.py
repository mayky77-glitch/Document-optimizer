"""Чтение каталога ZIP-архива без извлечения и чтения записей."""

import hashlib
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from report_processor.domain.exceptions import (
    BrokenArchiveError,
    SourceAccessError,
    SourceNotFoundError,
)
from report_processor.domain.models import FileManifestEntry
from report_processor.domain.statuses import StatusCode
from report_processor.inventory.file_classifier import classify_file_by_name
from report_processor.inventory.scanner import mark_possible_duplicates

LOGGER = logging.getLogger(__name__)

DEFAULT_MAX_SINGLE_ENTRY_UNCOMPRESSED_SIZE = 5 * 1024**3
DEFAULT_MAX_COMPRESSION_RATIO = 200.0
_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:[\\/]")
_UTF8_FLAG = 0x800


def _archive_file_id(archive_path: Path, info: zipfile.ZipInfo) -> str:
    value = f"{archive_path.resolve(strict=False)}\0{info.filename}\0{info.CRC}\0{info.file_size}"
    return hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()


def is_unsafe_archive_path(member_path: str) -> bool:
    """Проверить путь записи ZIP на абсолютный путь и обход родительских каталогов."""

    normalized = member_path.replace("\\", "/")
    return (
        normalized.startswith(("/", "//"))
        or bool(_WINDOWS_DRIVE_RE.match(member_path))
        or ".." in PurePosixPath(normalized).parts
    )


def _looks_like_utf8_mojibake(original: str, candidate: str) -> bool:
    has_box_drawing = any("\u2500" <= character <= "\u259f" for character in original)
    has_cyrillic = any("\u0400" <= character <= "\u04ff" for character in candidate)
    return candidate != original and has_box_drawing and has_cyrillic


def repair_zip_member_name(info: zipfile.ZipInfo) -> tuple[str, bool]:
    """Восстановить UTF-8 имя, ошибочно сохранённое без UTF-8 флага ZIP."""

    if info.flag_bits & _UTF8_FLAG:
        return info.filename, False
    try:
        candidate = info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename, False
    if _looks_like_utf8_mojibake(info.filename, candidate):
        return candidate, True
    return info.filename, False


def _zip_modified_at(info: zipfile.ZipInfo) -> datetime | None:
    try:
        return datetime(*info.date_time)
    except (TypeError, ValueError):
        return None


def _compression_ratio(uncompressed_size: int, compressed_size: int) -> float | None:
    if compressed_size == 0:
        return None
    return uncompressed_size / compressed_size


def _member_filename(member_path: str) -> str:
    normalized = member_path.replace("\\", "/").rstrip("/")
    return PurePosixPath(normalized).name


def _entry_warnings(
    member_path: str,
    info: zipfile.ZipInfo,
    *,
    encoding_recovered: bool,
    max_single_entry_uncompressed_size: int,
    max_compression_ratio: float,
) -> list[str]:
    warnings: list[str] = []
    if is_unsafe_archive_path(member_path):
        warnings.append(StatusCode.UNSAFE_ARCHIVE_PATH.value)

    ratio = _compression_ratio(info.file_size, info.compress_size)
    if (info.compress_size == 0 and info.file_size > 0) or (
        ratio is not None and ratio > max_compression_ratio
    ):
        warnings.append(StatusCode.SUSPICIOUS_COMPRESSION_RATIO.value)
    if info.file_size > max_single_entry_uncompressed_size:
        warnings.append(StatusCode.VERY_LARGE_ARCHIVE_ENTRY.value)
    if encoding_recovered:
        warnings.append(StatusCode.ZIP_FILENAME_ENCODING_RECOVERED.value)
    return warnings


def scan_zip_archive(
    archive_path: Path,
    *,
    max_single_entry_uncompressed_size: int = DEFAULT_MAX_SINGLE_ENTRY_UNCOMPRESSED_SIZE,
    max_compression_ratio: float = DEFAULT_MAX_COMPRESSION_RATIO,
) -> list[FileManifestEntry]:
    """Прочитать только центральный каталог ZIP и вернуть записи манифеста."""

    archive_path = archive_path.expanduser()
    if not archive_path.exists():
        raise SourceNotFoundError(archive_path)
    if archive_path.is_symlink():
        raise SourceAccessError(archive_path, "символические ссылки не поддерживаются")
    if not archive_path.is_file():
        raise SourceAccessError(archive_path, "путь не является файлом")

    absolute_archive = archive_path.resolve(strict=False)
    entries: list[FileManifestEntry] = []
    try:
        with zipfile.ZipFile(archive_path, mode="r") as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue

                member_path, encoding_recovered = repair_zip_member_name(info)
                warnings = _entry_warnings(
                    member_path,
                    info,
                    encoding_recovered=encoding_recovered,
                    max_single_entry_uncompressed_size=max_single_entry_uncompressed_size,
                    max_compression_ratio=max_compression_ratio,
                )
                filename = _member_filename(member_path)
                classification = classify_file_by_name(filename)
                normalized_path = member_path.replace("\\", "/")
                is_macos_metadata = normalized_path.startswith("__MACOSX/")

                entries.append(
                    FileManifestEntry(
                        file_id=_archive_file_id(archive_path, info),
                        source_type="zip_entry",
                        source_root=str(absolute_archive),
                        relative_path=member_path,
                        filename=filename,
                        extension=Path(filename).suffix.casefold(),
                        size_bytes=info.file_size,
                        compressed_size_bytes=info.compress_size,
                        modified_at=_zip_modified_at(info),
                        crc32=info.CRC,
                        is_archive_entry=True,
                        archive_path=str(absolute_archive),
                        document_type=classification.document_type,
                        document_markers=list(classification.document_markers),
                        is_temporary=classification.is_temporary or is_macos_metadata,
                        is_probable_copy=classification.is_probable_copy,
                        is_probably_outdated=classification.is_probably_outdated,
                        status=(StatusCode.WARNING.value if warnings else StatusCode.OK.value),
                        warnings=warnings,
                    )
                )
    except (zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise BrokenArchiveError(archive_path, str(exc)) from exc
    except OSError as exc:
        raise SourceAccessError(archive_path, str(exc)) from exc

    entries.sort(key=lambda entry: (entry.relative_path.casefold(), entry.relative_path))
    mark_possible_duplicates(entries)
    LOGGER.info("В ZIP-архиве %s найдено записей: %d", archive_path, len(entries))
    warning_count = sum(len(entry.warnings) for entry in entries)
    if warning_count:
        LOGGER.warning("ZIP-архив содержит предупреждений: %d", warning_count)
    return entries

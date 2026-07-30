"""Централизованные статусы и предупреждения инвентаризации."""

from enum import StrEnum


class StatusCode(StrEnum):
    """Допустимые статусы записей, ошибок и предупреждений блока 1."""

    OK = "OK"
    WARNING = "WARNING"
    UNREADABLE_FILE = "UNREADABLE_FILE"
    BROKEN_ARCHIVE = "BROKEN_ARCHIVE"
    UNSAFE_ARCHIVE_PATH = "UNSAFE_ARCHIVE_PATH"
    SUSPICIOUS_COMPRESSION_RATIO = "SUSPICIOUS_COMPRESSION_RATIO"
    VERY_LARGE_ARCHIVE_ENTRY = "VERY_LARGE_ARCHIVE_ENTRY"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    ZIP_FILENAME_ENCODING_RECOVERED = "ZIP_FILENAME_ENCODING_RECOVERED"

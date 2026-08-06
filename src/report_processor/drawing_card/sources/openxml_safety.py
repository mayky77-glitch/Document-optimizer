"""Bounded, pre-decompression validation for OpenXML containers."""

from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from ..statuses import Status

MAX_OPENXML_MEMBERS = 4_096
MAX_OPENXML_MEMBER_BYTES = 128 * 1024 * 1024
MAX_OPENXML_TOTAL_BYTES = 512 * 1024 * 1024
MAX_OPENXML_COMPRESSION_RATIO = 100


def validate_openxml_bytes(content: bytes) -> None:
    """Reject unsafe ZIP metadata before a workbook member is read."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            validate_openxml_archive(archive)
    except BadZipFile as error:
        raise ValueError("invalid workbook content") from error


def validate_openxml_archive(archive: ZipFile) -> None:
    """Validate central-directory metadata without decompressing any member."""
    infos = archive.infolist()
    if len(infos) > MAX_OPENXML_MEMBERS:
        raise ValueError(Status.VERY_LARGE_ARCHIVE_ENTRY.value)
    total = 0
    for info in infos:
        _validate_member(info)
        total += info.file_size
        if total > MAX_OPENXML_TOTAL_BYTES:
            raise ValueError(Status.VERY_LARGE_ARCHIVE_ENTRY.value)


def _validate_member(info: ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    raw_parts = info.filename.split("/")
    if (
        not info.filename
        or "\x00" in info.filename
        or "\\" in info.filename
        or path.is_absolute()
        or any(part in {".", ".."} for part in raw_parts)
        or any(not part for part in raw_parts[:-1])
    ):
        raise ValueError(Status.UNSAFE_ARCHIVE_PATH.value)
    if info.is_dir():
        return
    if info.file_size > MAX_OPENXML_MEMBER_BYTES:
        raise ValueError(Status.VERY_LARGE_ARCHIVE_ENTRY.value)
    if info.file_size and (
        not info.compress_size
        or info.file_size > info.compress_size * MAX_OPENXML_COMPRESSION_RATIO
    ):
        raise ValueError(Status.SUSPICIOUS_COMPRESSION_RATIO.value)

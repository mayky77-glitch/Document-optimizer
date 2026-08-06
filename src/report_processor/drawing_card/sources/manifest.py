"""Safe discovery of Excel sources in files, directories and ZIP archives."""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path, PurePosixPath

from ..models import ManifestEntry
from ..statuses import Status
from .normalization import extract_filename_object_candidates, stable_id

_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xlsb"}
_TEMP_PREFIXES = ("~$", "._")
_COPY_WORD_RE = re.compile(r"\b(?:копи[яи]|copy)\b", re.IGNORECASE)
_COPY_SUFFIX_RE = re.compile(r"\(\d{1,2}\)\s*$")
_REV_RE = re.compile(r"(?:ред(?:акция)?\s*|rev\s*)(\d+)", re.IGNORECASE)
_FULL_DATE4_RE = re.compile(
    r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[._/-](0?[1-9]|1[0-2])[._/-](20\d{2})(?!\d)"
)
_FULL_DATE2_RE = re.compile(
    r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[._/-](0?[1-9]|1[0-2])[._/-](\d{2})(?!\d)"
)
_YEAR_MONTH_RE = re.compile(r"(?<!\d)(20\d{2})[._/-](0?[1-9]|1[0-2])(?!\d)")
_MONTH_YEAR_RE = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])[._/-](20\d{2})(?!\d)")
_DIGEST_BLOCK_SIZE = 1024 * 1024


def _content_digest(path: Path) -> str:
    """Return a bounded-memory digest without retaining private path data."""
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(_DIGEST_BLOCK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _ignored_name(name: str) -> bool:
    path = PurePosixPath(name)
    if any(part == "__MACOSX" for part in path.parts):
        return True
    base = path.name
    if base == ".DS_Store" or base.startswith(_TEMP_PREFIXES):
        return True
    return not base


def _safe_zip_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _document_type(name: str) -> str | None:
    low = name.lower()
    if "виср" in low:
        return "visr"
    if "кс-6" in low or "кс6" in low:
        return "ks6a"
    if "кс-2" in low or "кс2" in low:
        return "ks2"
    if "сввр" in low:
        return "svvr"
    if "пуо" in low:
        return "puo"
    if "вуо" in low:
        return "vuo"
    return None


def _period(name: str) -> str | None:
    low = name.lower()
    full_date = _FULL_DATE4_RE.search(low)
    if full_date:
        month, year = full_date.groups()
        return f"{year}-{int(month):02d}"
    short_date = _FULL_DATE2_RE.search(low)
    if short_date:
        month, year = short_date.groups()
        return f"{2000 + int(year):04d}-{int(month):02d}"
    year_month = _YEAR_MONTH_RE.search(low)
    if year_month:
        return f"{year_month.group(1)}-{int(year_month.group(2)):02d}"
    month_year = _MONTH_YEAR_RE.search(low)
    if month_year:
        return f"{month_year.group(2)}-{int(month_year.group(1)):02d}"
    months = {
        "янв": 1,
        "фев": 2,
        "мар": 3,
        "апр": 4,
        "май": 5,
        "июн": 6,
        "июл": 7,
        "авг": 8,
        "сен": 9,
        "окт": 10,
        "ноя": 11,
        "дек": 12,
    }
    year = re.search(r"20\d{2}", low)
    for prefix, month in months.items():
        if prefix in low and year:
            return f"{year.group(0)}-{month:02d}"
    return None


def _decode_zip_name(name: str) -> str:
    try:
        decoded = name.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name
    return decoded if decoded.count("�") == 0 else name


def _entry(
    *,
    source_kind: str,
    container_path: Path,
    logical_path: str,
    size: int,
    compressed_size: int | None,
    content_digest: str,
    analysis_path: str | None = None,
) -> ManifestEntry:
    path_text = (analysis_path or logical_path).replace("\\", "/")
    filename = PurePosixPath(path_text).name
    extension = Path(filename).suffix.lower()
    candidates = extract_filename_object_candidates(path_text)
    revision_match = _REV_RE.search(path_text)
    warnings: list[str] = []
    is_temp = filename.startswith(_TEMP_PREFIXES)
    stem = Path(filename).stem
    is_copy = bool(_COPY_WORD_RE.search(stem) or _COPY_SUFFIX_RE.search(stem))
    is_outdated = any(token in path_text.lower() for token in ("неакт", "устар", "архив", "old"))
    status = Status.OK.value
    if is_temp:
        status = Status.WARNING.value
        warnings.append("TEMPORARY_FILE")
    if is_copy:
        warnings.append("POSSIBLE_COPY")
    if is_outdated:
        warnings.append("OUTDATED_SOURCE")
    return ManifestEntry(
        file_id=stable_id(source_kind, content_digest, logical_path),
        source_kind=source_kind,
        container_path=str(container_path.resolve()),
        logical_path=logical_path,
        filename=filename,
        extension=extension,
        size=size,
        compressed_size=compressed_size,
        object_index_hint=candidates[0] if candidates else None,
        document_type=_document_type(filename) or _document_type(path_text),
        period=_period(filename) or _period(path_text),
        revision=revision_match.group(1) if revision_match else None,
        is_temporary=is_temp,
        is_copy=is_copy,
        is_outdated=is_outdated,
        status=status,
        warnings=tuple(warnings),
    )


def scan_file(path: Path) -> list[ManifestEntry]:
    if path.suffix.lower() == ".zip":
        return scan_archive(path)
    if path.suffix.lower() not in _EXCEL_EXTENSIONS or _ignored_name(path.name):
        return []
    stat = path.stat()
    return [
        _entry(
            source_kind="file",
            container_path=path,
            logical_path=path.name,
            size=stat.st_size,
            compressed_size=None,
            content_digest=_content_digest(path),
        )
    ]


def scan_directory(path: Path) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    for item in sorted(path.rglob("*")):
        if not item.is_file() or _ignored_name(item.name):
            continue
        if item.suffix.lower() not in _EXCEL_EXTENSIONS:
            continue
        stat = item.stat()
        entries.append(
            _entry(
                source_kind="directory",
                container_path=path,
                logical_path=item.relative_to(path).as_posix(),
                size=stat.st_size,
                compressed_size=None,
                content_digest=_content_digest(item),
            )
        )
    return entries


def scan_archive(path: Path, max_entry_size: int = 2 * 1024**3) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    archive_digest = _content_digest(path)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            decoded_name = _decode_zip_name(info.filename)
            if info.is_dir() or _ignored_name(decoded_name):
                continue
            extension = Path(decoded_name).suffix.lower()
            if extension not in _EXCEL_EXTENSIONS:
                continue
            warnings: list[str] = []
            if not _safe_zip_name(decoded_name):
                warnings.append(Status.UNSAFE_ARCHIVE_PATH.value)
            if info.file_size > max_entry_size:
                warnings.append(Status.VERY_LARGE_ARCHIVE_ENTRY.value)
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > 250:
                warnings.append(Status.SUSPICIOUS_COMPRESSION_RATIO.value)
            base = _entry(
                source_kind="zip",
                container_path=path,
                logical_path=decoded_name,
                size=info.file_size,
                compressed_size=info.compress_size,
                content_digest=archive_digest,
                analysis_path=decoded_name,
            )
            if warnings:
                base = ManifestEntry(
                    **{
                        field: getattr(base, field)
                        for field in base.__dataclass_fields__
                        if field != "warnings"
                    },
                    warnings=base.warnings + tuple(warnings),
                )
            entries.append(base)
    return entries


def build_manifest(
    inputs: Iterable[Path] = (),
    input_dir: Path | None = None,
    archive: Path | None = None,
) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    for path in inputs:
        entries.extend(scan_file(path))
    if input_dir is not None:
        entries.extend(scan_directory(input_dir))
    if archive is not None:
        entries.extend(scan_archive(archive))
    unique: dict[str, ManifestEntry] = {entry.file_id: entry for entry in entries}
    return sorted(
        unique.values(), key=lambda item: (item.object_index_hint or "", item.logical_path)
    )


def expand_input_globs(values: Iterable[str]) -> tuple[Path, ...]:
    result: list[Path] = []
    for value in values:
        path = Path(value).expanduser()
        if any(char in value for char in "*?["):
            parent = path.parent if str(path.parent) != "." else Path.cwd()
            result.extend(sorted(parent.glob(path.name)))
        else:
            result.append(path)
    return tuple(result)

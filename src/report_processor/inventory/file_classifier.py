"""Классификация документов исключительно по имени файла."""

import re
import unicodedata
from pathlib import Path

from report_processor.domain.models import FileClassification

_DASHES = "‐‑‒–—―−﹘﹣－"
_DASH_TRANSLATION = str.maketrans({character: "-" for character in _DASHES})
_SEPARATOR_RE = re.compile(r"[\s_.\-]+")
_SPACE_RE = re.compile(r"\s+")

_DOCUMENT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "additional_report": (
        re.compile(r"(?<!\w)доп\s*отчет(?:а|у|ом|е)?(?!\w)"),
        re.compile(r"(?<!\w)дополнительн(?:ый|ого|ому|ым|ом)\s+отчет(?:а|у|ом|е)?(?!\w)"),
    ),
    "ks6a": (re.compile(r"(?<!\w)(?:(?:кс|ks)\s*)?6\s*[аa](?!\w)"),),
    "svvr": (
        re.compile(r"(?<!\w)сввр(?!\w)"),
        re.compile(r"(?<!\w)сводная\s+ведомость\s+выполненных\s+работ(?!\w)"),
        re.compile(r"(?<!\w)ведомость\s+выполненных\s+работ(?!\w)"),
    ),
    "ks2_registry": (
        re.compile(r"(?<!\w)реестр(?:\s+актов)?\s+(?:кс|ks)\s*2(?!\w)"),
        re.compile(r"(?<!\w)(?:кс|ks)\s*2\s+реестр(?!\w)"),
    ),
    "subobject_reference": (
        re.compile(r"(?<!\w)перечень\s+подобъектов(?!\w)"),
        re.compile(r"(?<!\w)справочник\s+подобъектов(?!\w)"),
    ),
    "visr": (
        re.compile(r"(?<!\w)ви\s*ср(?!\w)"),
        re.compile(r"(?<!\w)виср(?!\w)"),
    ),
    "drdc": (re.compile(r"(?<!\w)дрдц(?!\w)"),),
    "ks2": (re.compile(r"(?<!\w)(?:кс|ks)\s*2(?!\w)"),),
    "ks3": (re.compile(r"(?<!\w)(?:кс|ks)\s*3(?!\w)"),),
}

# Specific compound types precede their generic markers.
_PRIORITY = (
    "additional_report",
    "ks6a",
    "svvr",
    "ks2_registry",
    "subobject_reference",
    "visr",
    "drdc",
    "ks2",
    "ks3",
)

_COPY_WORD_RE = re.compile(r"(?<!\w)(?:копия|copy|дубликат|duplicate)(?!\w)")
_COPY_SUFFIX_RE = re.compile(r"\((?P<number>\d{1,2})\)\s*$")
_OUTDATED_PATTERNS = (
    re.compile(r"(?<!\w)стар(?:ый|ая|ое|ые)(?!\w)"),
    re.compile(r"(?<!\w)не\s*актуал\w*(?!\w)"),
    re.compile(r"(?<!\w)неактуал\w*(?!\w)"),
    re.compile(r"(?<!\w)obsolete(?!\w)"),
    re.compile(r"(?<!\w)old(?!\w)"),
    re.compile(r"(?<!\w)черновик(?!\w)"),
    re.compile(r"(?<!\w)draft(?!\w)"),
)
_ARCHIVE_WORD_RE = re.compile(r"(?<!\w)(?:архив|archive)(?!\w)")


def normalize_filename(filename: str) -> str:
    """Нормализовать имя без расширения для устойчивого поиска маркеров."""

    basename = Path(filename).name
    suffix = Path(basename).suffix
    stem = basename[: -len(suffix)] if suffix else basename
    normalized = unicodedata.normalize("NFKC", stem).casefold().replace("ё", "е")
    normalized = normalized.translate(_DASH_TRANSLATION)
    normalized = _SEPARATOR_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def classify_file_by_name(filename: str) -> FileClassification:
    """Классифицировать файл по имени, не открывая и не читая его содержимое."""

    normalized = normalize_filename(filename)
    extension = Path(filename).suffix.casefold()
    markers = [
        document_type
        for document_type in _PRIORITY
        if any(pattern.search(normalized) for pattern in _DOCUMENT_PATTERNS[document_type])
    ]

    if extension == ".zip":
        markers = ["archive", *markers]
        document_type = "archive"
    else:
        document_type = markers[0] if markers else "unknown"

    basename_casefold = unicodedata.normalize("NFKC", Path(filename).name).casefold()
    is_temporary = (
        basename_casefold.startswith(("~$", "._"))
        or basename_casefold in {".ds_store", "thumbs.db"}
        or extension in {".tmp", ".temp"}
    )
    is_probable_copy = bool(_COPY_WORD_RE.search(normalized) or _COPY_SUFFIX_RE.search(normalized))
    is_probably_outdated = any(pattern.search(normalized) for pattern in _OUTDATED_PATTERNS)
    if extension != ".zip":
        is_probably_outdated = is_probably_outdated or bool(_ARCHIVE_WORD_RE.search(normalized))

    return FileClassification(
        normalized_name=normalized,
        document_type=document_type,
        document_markers=markers,
        is_temporary=is_temporary,
        is_probable_copy=is_probable_copy,
        is_probably_outdated=is_probably_outdated,
    )

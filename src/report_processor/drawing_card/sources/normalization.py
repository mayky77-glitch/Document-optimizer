"""Text, unit, drawing-code and number normalization."""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from ..models import DrawingCode
from ..statuses import Status

_SPACE_RE = re.compile(r"\s+")
_OBJECT_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_OBJECT_LABEL_RE = re.compile(
    r"(?:индекс(?:\s+объекта)?|объект|об\.)\s*[:№#-]*\s*(\d{4})(?!\d)",
    re.IGNORECASE,
)
_OBJECT_BEFORE_DOCUMENT_RE = re.compile(
    r"(?<!\d)(\d{4})(?!\d)"
    r"(?=\s*(?:\(\d+\))?\s*[_\- ]*"
    r"(?:кс\s*[-–—]?\s*(?:2|3|6а?)|виср|сввр|пуо|вуо)\b)",
    re.IGNORECASE,
)
_OBJECT_PREFIX_RE = re.compile(r"^\s*#?\s*(\d{4})(?=\D|$)", re.IGNORECASE)
_OBJECT_PATH_SEGMENT_RE = re.compile(r"(?:^|[/\\])\s*#?\s*(\d{4})(?=\D|$)")

_UNIT_ALIASES = {
    "м³": "м3",
    "м^3": "м3",
    "куб.м": "м3",
    "куб м": "м3",
    "м.п.": "м",
    "п.м": "м",
    "пог.м": "м",
    "тонн": "т",
    "тонна": "т",
    "тонны": "т",
    "штук": "шт",
    "шт.": "шт",
}


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").replace("ё", "е").replace("Ё", "Е")
    text = text.strip().lower()
    return _SPACE_RE.sub(" ", text)


def normalize_unit(value: str | None) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    compact = text.replace(" ", "")
    return _UNIT_ALIASES.get(text, _UNIT_ALIASES.get(compact, compact))


def _normalize_excel_binary_artifact(value: Decimal) -> tuple[Decimal, tuple[str, ...]]:
    """Remove only microscopic IEEE-754 tails while preserving real precision.

    Cached Excel formulas may contain values such as ``184178.2699999998``.
    The canonical value is snapped to at most six decimal places only when the
    difference is many orders of magnitude smaller than the value.  Raw cached
    values remain available in ``DrawingSourceRow.cached_values`` for audit.
    """

    if not value.is_finite() or value == value.to_integral_value():
        return value, ()
    for places in range(0, 7):
        quantum = Decimal(1).scaleb(-places)
        candidate = value.quantize(quantum)
        # A fixed microscopic tolerance is intentionally used here.  A relative
        # tolerance could silently round a legitimate fractional part on large
        # monetary values (for example 1_000_000_000_000.001).  Five nanounits
        # are sufficient for the IEEE-754 tails observed in Excel cached values
        # while remaining far below the supported six-decimal business precision.
        tolerance = Decimal("5e-9")
        if candidate != value and abs(value - candidate) <= tolerance:
            return candidate, (f"BINARY_FLOAT_ARTIFACT_NORMALIZED:{value}->{candidate}",)
    return value, ()


def parse_decimal(value: Any) -> tuple[Decimal | None, tuple[str, ...]]:
    if value is None or value == "":
        return None, ()
    if isinstance(value, bool):
        return None, (Status.INVALID_NUMBER.value,)
    if isinstance(value, Decimal):
        return _normalize_excel_binary_artifact(value)
    if isinstance(value, (int, float)):
        return _normalize_excel_binary_artifact(Decimal(str(value)))
    text = str(value).strip()
    if text.startswith("#"):
        return None, (Status.EXCEL_ERROR.value, text)
    text = text.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9eE+\-.]", "", text)
    if not text:
        return None, (Status.INVALID_NUMBER.value,)
    try:
        return _normalize_excel_binary_artifact(Decimal(text))
    except InvalidOperation:
        return None, (Status.INVALID_NUMBER.value, str(value))


def _plausible_object_index(value: str) -> bool:
    """Reject obvious years while preserving leading-zero and 1xxx object codes."""
    number = int(value)
    return not 1900 <= number <= 2099


def _unique_plausible(values: list[str]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(candidate for candidate in values if _plausible_object_index(candidate))
    )


def extract_object_candidates(value: str | None) -> tuple[str, ...]:
    """Extract generic four-digit object candidates, excluding calendar years."""
    if not value:
        return ()
    return _unique_plausible(_OBJECT_RE.findall(str(value)))


def extract_filename_object_candidates(value: str | None) -> tuple[str, ...]:
    """Extract filename/path candidates using construction-document context first.

    Filenames often contain contract numbers, dates and an object code at once.  A
    context-aware pass prevents values such as ``0109`` from winning over ``0907``
    in ``31_0109_..._2026_0907 (841)_КС-6.xlsx``.
    """
    if not value:
        return ()
    text = str(value)
    strong: list[str] = []
    strong.extend(_OBJECT_LABEL_RE.findall(text))
    strong.extend(_OBJECT_BEFORE_DOCUMENT_RE.findall(text))
    basename = re.split(r"[/\\]", text)[-1]
    prefix = _OBJECT_PREFIX_RE.search(basename)
    if prefix:
        strong.append(prefix.group(1))
    strong.extend(_OBJECT_PATH_SEGMENT_RE.findall(text))
    preferred = _unique_plausible(strong)
    return preferred or extract_object_candidates(text)


_NON_DRAWING_TOKENS = {
    "м",
    "м2",
    "м3",
    "м³",
    "км",
    "см",
    "мм",
    "шт",
    "т",
    "кг",
    "компл",
    "комплект",
    "руб",
    "%",
    "пес",
    "щ",
    "щеб",
    "бет",
}


def is_plausible_drawing_code(value: str | None) -> bool:
    """Return whether a cell can safely replace the current drawing code.

    Some real КС-6/КС-6а files contain short material or unit markers in the
    physical ``Шифр чертежа`` column on detail rows (for example ``м``, ``пес``
    or ``щ``).  Those cells must not break the parent drawing-code group.
    """

    text = normalize_text(value)
    if not text or text.replace(" ", "") in _NON_DRAWING_TOKENS:
        return False
    has_digit = any(char.isdigit() for char in text)
    if has_digit:
        return True
    # A code without digits is accepted only when it has enough structure to
    # distinguish it from a unit/material abbreviation.
    return len(text) >= 8 and any(char in text for char in ".-/()")


def build_drawing_code(raw: str, mode: str = "preserve_group") -> DrawingCode:
    clean = _SPACE_RE.sub(" ", str(raw).replace("\u00a0", " ")).strip()
    components = tuple(part.strip() for part in clean.split(";") if part.strip())
    warnings: list[str] = []
    if mode == "split_confirmed" and len(components) > 1:
        group_key = " || ".join(normalize_text(part) for part in components)
    else:
        group_key = normalize_text(clean)
    if not clean:
        return DrawingCode("", "", "", (), Status.DRAWING_CODE_NOT_FOUND.value, ())
    if len(components) > 1 and mode == "preserve_group":
        warnings.append("DRAWING_CODE_GROUP_PRESERVED")
    return DrawingCode(
        raw=clean,
        normalized=normalize_text(clean),
        group_key=group_key,
        components=components or (clean,),
        status=Status.OK.value,
        warnings=tuple(warnings),
    )


def stable_id(*parts: object) -> str:
    payload = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

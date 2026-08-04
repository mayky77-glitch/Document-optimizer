"""Typed, immutable parameters extracted from an audit-preserving work term."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from .canonicalization import normalize_audit_text, normalize_semantic_text

TYPED_SLOTS_VERSION = "TypedSlots-1.0"


class SlotKind(StrEnum):
    DIAMETER = "diameter"
    PRESSURE = "pressure"
    VOLTAGE = "voltage"
    CABLE_SECTION = "cable_section"
    LENGTH = "length"
    MASS = "mass"
    COUNT = "count"
    BRAND = "brand"
    MATERIAL = "material"
    EXECUTION = "execution"
    GOST = "gost"
    TU = "tu"
    FIRE_CLASS = "fire_class"
    MODEL = "model"
    ARTICLE = "article"
    DOCUMENT_INDEX = "document_index"


class SlotImpact(StrEnum):
    CATEGORY_NEUTRAL = "category_neutral"
    FAMILY_BOUNDARY = "family_boundary"
    HARD_CONFLICT = "hard_conflict"
    DISPLAY_ONLY = "display_only"


_IMPACTS = {
    SlotKind.DIAMETER: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.PRESSURE: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.VOLTAGE: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.CABLE_SECTION: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.LENGTH: SlotImpact.CATEGORY_NEUTRAL,
    SlotKind.MASS: SlotImpact.CATEGORY_NEUTRAL,
    SlotKind.COUNT: SlotImpact.CATEGORY_NEUTRAL,
    SlotKind.BRAND: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.MATERIAL: SlotImpact.HARD_CONFLICT,
    SlotKind.EXECUTION: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.GOST: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.TU: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.FIRE_CLASS: SlotImpact.HARD_CONFLICT,
    SlotKind.MODEL: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.ARTICLE: SlotImpact.FAMILY_BOUNDARY,
    SlotKind.DOCUMENT_INDEX: SlotImpact.DISPLAY_ONLY,
}


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value.replace(",", "."))
    except (AttributeError, InvalidOperation) as error:
        raise ValueError(f"invalid decimal value: {value!r}") from error
    if not result.is_finite():
        raise ValueError("slot values must be finite Decimals")
    return result.normalize() if result else Decimal(0)


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Half-open Unicode code-point span in ``TypedSlotParse.audit_text``."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError("invalid text span")


@dataclass(frozen=True, slots=True)
class ScalarValue:
    value: Decimal
    unit: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise TypeError("ScalarValue.value must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class RangeValue:
    lower: Decimal
    upper: Decimal
    unit: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, Decimal) and value.is_finite() for value in (self.lower, self.upper)
        ):
            raise TypeError("RangeValue bounds must be finite Decimals")
        if self.lower > self.upper:
            raise ValueError("range lower bound exceeds upper bound")


@dataclass(frozen=True, slots=True)
class DiameterValue:
    mm: Decimal
    basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.mm, Decimal) or not self.mm.is_finite():
            raise TypeError("DiameterValue.mm must be a finite Decimal")


@dataclass(frozen=True, slots=True)
class CableSectionValue:
    cores: Decimal
    section_mm2: Decimal

    def __post_init__(self) -> None:
        if (
            not isinstance(self.cores, Decimal)
            or self.cores <= 0
            or not isinstance(self.section_mm2, Decimal)
            or self.section_mm2 <= 0
        ):
            raise ValueError("cable section requires positive core count and Decimal section")


@dataclass(frozen=True, slots=True)
class TextValue:
    value: str


@dataclass(frozen=True, slots=True)
class TypedSlot:
    kind: SlotKind
    impact: SlotImpact
    span: TextSpan
    audit_fragment: str
    normalized: str
    value: ScalarValue | RangeValue | DiameterValue | CableSectionValue | TextValue


@dataclass(frozen=True, slots=True)
class SlotWarning:
    code: str
    span: TextSpan


@dataclass(frozen=True, slots=True)
class SlotConflict:
    code: str
    kind: SlotKind
    slots: tuple[TypedSlot, ...]


@dataclass(frozen=True, slots=True)
class TypedSlotParse:
    audit_text: str
    slots: tuple[TypedSlot, ...]
    warnings: tuple[SlotWarning, ...]
    conflicts: tuple[SlotConflict, ...]
    requires_manual_review: bool
    version: str = TYPED_SLOTS_VERSION


@dataclass(frozen=True, slots=True)
class _Candidate:
    kind: SlotKind
    span: TextSpan
    normalized: str
    value: ScalarValue | RangeValue | DiameterValue | CableSectionValue | TextValue
    priority: int


_NUMBER = r"\d+(?:[.,]\d+)?"
_Converter = Callable[
    [re.Match[str]], ScalarValue | RangeValue | DiameterValue | CableSectionValue | TextValue
]
_CANDIDATES: tuple[tuple[SlotKind, re.Pattern[str], int, _Converter], ...] = (
    (
        SlotKind.DIAMETER,
        re.compile(rf"(?<!\w)(?:dn|ду|дн|du)\s*(?P<n>{_NUMBER})(?!\w)", re.I),
        700,
        lambda m: DiameterValue(_decimal(m["n"]), "nominal"),
    ),
    (
        SlotKind.DIAMETER,
        re.compile(rf"(?:ø|⌀)\s*(?P<n>{_NUMBER})(?:\s*мм)?(?!\w)", re.I),
        700,
        lambda m: DiameterValue(_decimal(m["n"]), "outer"),
    ),
    (
        SlotKind.DIAMETER,
        re.compile(rf"(?:диаметр)\s*(?P<n>{_NUMBER})\s*мм(?!\w)", re.I),
        700,
        lambda m: DiameterValue(_decimal(m["n"]), "unspecified"),
    ),
    (
        SlotKind.DIAMETER,
        re.compile(rf"(?<!\w)[dд]\s*(?P<n>{_NUMBER})\s*мм(?!\w)", re.I),
        700,
        lambda m: DiameterValue(_decimal(m["n"]), "unspecified"),
    ),
    (
        SlotKind.DIAMETER,
        re.compile(rf"(?<!\w)[dд]\s*(?P<n>{_NUMBER})(?!\s*мм\b)(?!\w)", re.I),
        650,
        lambda m: DiameterValue(_decimal(m["n"]), "unspecified"),
    ),
    (
        SlotKind.PRESSURE,
        re.compile(rf"(?<!\w)(?:pn|ру|ru)\s*(?P<n>{_NUMBER})(?!\w)", re.I),
        600,
        lambda m: ScalarValue(_decimal(m["n"]), "pn"),
    ),
    (
        SlotKind.PRESSURE,
        re.compile(rf"(?:давление)\s*(?P<n>{_NUMBER})\s*(?P<u>мпа|бар)(?!\w)", re.I),
        600,
        lambda m: ScalarValue(_decimal(m["n"]), m["u"].casefold()),
    ),
    (
        SlotKind.VOLTAGE,
        re.compile(rf"(?P<a>{_NUMBER})\s*[-–—]\s*(?P<b>{_NUMBER})\s*кв(?!\w)", re.I),
        500,
        lambda m: RangeValue(_decimal(m["a"]), _decimal(m["b"]), "kv"),
    ),
    (
        SlotKind.VOLTAGE,
        re.compile(rf"(?P<n>{_NUMBER})\s*кв(?!\w)", re.I),
        400,
        lambda m: ScalarValue(_decimal(m["n"]), "kv"),
    ),
    (
        SlotKind.CABLE_SECTION,
        re.compile(rf"(?<!\w)(?P<c>\d+)\s*[xх×]\s*(?P<s>{_NUMBER})\s*мм(?:2|²)(?!\w)", re.I),
        800,
        lambda m: CableSectionValue(_decimal(m["c"]), _decimal(m["s"])),
    ),
    (
        SlotKind.CABLE_SECTION,
        re.compile(rf"(?<!\w)(?P<c>\d+)\s*[xх×]\s*(?P<s>{_NUMBER})(?!\s*мм(?:2|²)\b)(?!\w)", re.I),
        750,
        lambda m: CableSectionValue(_decimal(m["c"]), _decimal(m["s"])),
    ),
    (
        SlotKind.LENGTH,
        re.compile(rf"(?P<n>{_NUMBER})\s*(?:м|метр(?:а|ов)?)\b", re.I),
        200,
        lambda m: ScalarValue(_decimal(m["n"]), "m"),
    ),
    (
        SlotKind.MASS,
        re.compile(rf"(?P<n>{_NUMBER})\s*(?P<u>кг|т|тонн(?:а|ы)?)\b", re.I),
        300,
        lambda m: ScalarValue(
            _decimal(m["n"]) * (Decimal(1000) if m["u"].casefold() != "кг" else Decimal(1)), "kg"
        ),
    ),
    (
        SlotKind.COUNT,
        re.compile(rf"(?P<n>{_NUMBER})\s*(?:шт|штук(?:а|и)?)\b", re.I),
        100,
        lambda m: ScalarValue(_decimal(m["n"]), "piece"),
    ),
    (
        SlotKind.COUNT,
        re.compile(rf"(?P<n>{_NUMBER})\s*(?:компл(?:ект)?(?:а|ов)?)\b", re.I),
        100,
        lambda m: ScalarValue(_decimal(m["n"]), "set"),
    ),
    (
        SlotKind.GOST,
        re.compile(r"(?<!\w)гост(?:\s*(?:-|№|no))?\s*[\w./-]+", re.I),
        900,
        lambda m: TextValue(_text_value(m.group(0))),
    ),
    (
        SlotKind.TU,
        re.compile(r"(?<!\w)ту(?:\s*(?:-|№|no))?\s*[\w./-]+", re.I),
        900,
        lambda m: TextValue(_text_value(m.group(0))),
    ),
    (
        SlotKind.FIRE_CLASS,
        re.compile(
            r"(?:класс\s+огнестойкости\s*:\s*)?(?<!\w)(?:нг\(?[a-zа-я0-9+\-]*\)?|e\d+|[a-z]+fr[a-z0-9-]*)(?!\w)",
            re.I,
        ),
        900,
        lambda m: TextValue(_text_value(m.group(0))),
    ),
    (
        SlotKind.BRAND,
        re.compile(r"(?:марка)\s*(?:(?::|№)\s*|no\s+|)(?P<v>[\w./-]+)", re.I),
        900,
        lambda m: TextValue(_text_value(m["v"])),
    ),
    (
        SlotKind.MATERIAL,
        re.compile(r"(?:материал)\s*(?:(?::|№)\s*|no\s+|)(?P<v>[\w -]+?)(?=\s*(?:,|;|$))", re.I),
        900,
        lambda m: TextValue(_text_value(m["v"])),
    ),
    (
        SlotKind.EXECUTION,
        re.compile(r"(?:исполнение)\s*(?:(?::|№)\s*|no\s+|)(?P<v>[\w./-]+)", re.I),
        900,
        lambda m: TextValue(_text_value(m["v"])),
    ),
    (
        SlotKind.MODEL,
        re.compile(r"(?:модель)\s*(?:(?::|№)\s*|no\s+|)(?P<v>[\w./-]+)", re.I),
        900,
        lambda m: TextValue(_text_value(m["v"])),
    ),
    (
        SlotKind.ARTICLE,
        re.compile(r"(?:артикул)\s*(?:(?::|№)\s*|no\s+|)(?P<v>[\w./-]+)", re.I),
        900,
        lambda m: TextValue(_text_value(m["v"])),
    ),
    (
        SlotKind.DOCUMENT_INDEX,
        re.compile(
            r"(?:индекс(?:\s+документа)?|документ\s*(?:№|no)?|док\.\s*(?:№|no)?)"
            r"\s*(?::|№|no)?\s*(?P<v>[\w./-]+)",
            re.I,
        ),
        1000,
        lambda m: TextValue(_text_value(m["v"])),
    ),
)


def parse_typed_slots(value: object, *, object_kind: str | None = None) -> TypedSlotParse:
    """Extract deterministic slots; bare ``NxY`` and ambiguous ``D/d`` fail closed."""
    audit_text = normalize_audit_text(value)
    candidates: list[_Candidate] = []
    for kind, pattern, priority, converter in _CANDIDATES:
        for match in pattern.finditer(audit_text):
            if (
                kind is SlotKind.CABLE_SECTION
                and "мм" not in match.group(0).casefold()
                and not _is_cable_scope(object_kind)
            ):
                continue
            if (
                kind is SlotKind.DIAMETER
                and _is_bare_diameter(match.group(0))
                and not _is_pipeline_scope(object_kind)
            ):
                continue
            try:
                converted = converter(match)
            except ValueError:
                candidates.append(
                    _Candidate(kind, TextSpan(*match.span()), "", TextValue(""), priority)
                )
                continue
            normalized = _normalized(kind, converted, match.group(0))
            if kind in {SlotKind.GOST, SlotKind.TU}:
                converted = TextValue(normalized)
            elif kind is SlotKind.FIRE_CLASS:
                converted = TextValue(_text_value(match.group(0).split(":")[-1]))
                normalized = converted.value
            candidates.append(
                _Candidate(
                    kind,
                    TextSpan(*match.span()),
                    normalized,
                    converted,
                    priority,
                )
            )
    selected: list[_Candidate] = []
    discarded: list[_Candidate] = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            -item.priority,
            -(item.span.end - item.span.start),
            item.span.start,
            item.kind.value,
            item.normalized,
        ),
    ):
        if not any(
            candidate.span.start < current.span.end and current.span.start < candidate.span.end
            for current in selected
        ):
            selected.append(candidate)
        else:
            discarded.append(candidate)
    slots = tuple(
        TypedSlot(
            item.kind,
            _IMPACTS[item.kind],
            item.span,
            audit_text[item.span.start : item.span.end],
            item.normalized,
            item.value,
        )
        for item in sorted(
            selected, key=lambda item: (item.span.start, item.span.end, item.kind.value)
        )
    )
    invalid_ranges = [
        item for item in selected if item.kind is SlotKind.VOLTAGE and not item.normalized
    ]
    slots = tuple(slot for slot in slots if slot.normalized)
    warnings = (
        _warnings(audit_text, slots, discarded, object_kind)
        + tuple(SlotWarning("invalid_range", item.span) for item in invalid_ranges)
        + _malformed_explicit_warnings(audit_text, slots, object_kind=object_kind)
    )
    conflicts = _conflicts(slots)
    warnings = tuple(sorted(set(warnings), key=lambda warning: (warning.span.start, warning.code)))
    return TypedSlotParse(audit_text, slots, warnings, conflicts, bool(warnings or conflicts))


def _warnings(
    text: str, slots: tuple[TypedSlot, ...], discarded: list[_Candidate], object_kind: str | None
) -> tuple[SlotWarning, ...]:
    warnings: list[SlotWarning] = []
    occupied = tuple(slot.span for slot in slots)
    for match in re.finditer(
        rf"(?<!\w)[dд]\s*{_NUMBER}(?!\w)|(?<!\w)\d+\s*[xх×]\s*{_NUMBER}(?!\w)", text, re.I
    ):
        span = TextSpan(*match.span())
        if not any(span.start >= item.start and span.end <= item.end for item in occupied):
            code = (
                "ambiguous_diameter"
                if match.group(0).lstrip()[0].casefold() in {"d", "д"}
                else "ambiguous_cable_section"
            )
            warnings.append(SlotWarning(code, span))
    warnings.extend(SlotWarning("overlap_discarded", candidate.span) for candidate in discarded)
    by_kind: dict[SlotKind, set[str]] = {}
    for slot in slots:
        if slot.impact is SlotImpact.FAMILY_BOUNDARY:
            by_kind.setdefault(slot.kind, set()).add(repr(slot.value))
    for kind in sorted(by_kind, key=str):
        if len(by_kind[kind]) > 1:
            warnings.append(
                SlotWarning(
                    "multiple_family_values", next(slot.span for slot in slots if slot.kind is kind)
                )
            )
    return tuple(sorted(warnings, key=lambda warning: (warning.span.start, warning.code)))


def _is_cable_scope(object_kind: str | None) -> bool:
    scope = normalize_semantic_text(object_kind) if object_kind else ""
    return "кабель" in scope or "cable" in scope


def _is_pipeline_scope(object_kind: str | None) -> bool:
    scope = normalize_semantic_text(object_kind) if object_kind else ""
    return any(marker in scope for marker in ("труб", "pipeline", "pipe"))


def _is_bare_diameter(raw: str) -> bool:
    return bool(re.fullmatch(r"[dд]\s*\d+(?:[.,]\d+)?", raw, re.I))


def _malformed_explicit_warnings(
    text: str, slots: tuple[TypedSlot, ...], *, object_kind: str | None
) -> tuple[SlotWarning, ...]:
    """Flag incomplete labelled values instead of silently treating them as prose."""
    warnings: list[SlotWarning] = []
    occupied = tuple(slot.span for slot in slots)
    numeric = re.compile(
        r"(?<!\w)(?P<marker>dn|ду|дн|du|pn|ру|ru)(?!\w)\s*(?P<value>[^\s,;]*)",
        re.I,
    )
    labelled = re.compile(
        r"(?<!\w)(?P<marker>марка|материал|исполнение|модель|артикул)"
        r"\s*(?P<delimiter>:|№|no)(?:\s*(?P<value>[^\s,;]+))?"
        r"|(?<!\w)(?P<standard>гост|ту)(?!\w)(?:\s*(?P<standard_delimiter>-|№|no))?"
        r"(?:\s*(?P<standard_value>[^\s,;]+))?",
        re.I,
    )
    for match in (*numeric.finditer(text), *labelled.finditer(text)):
        span = TextSpan(*match.span())
        if any(span.start >= item.start and span.end <= item.end for item in occupied):
            continue
        value = match.groupdict().get("value") or match.groupdict().get("standard_value") or ""
        if not value:
            code = "missing_slot_value"
        elif match.re is numeric and not re.fullmatch(_NUMBER, value):
            code = "invalid_numeric_value"
        else:
            continue
        warnings.append(SlotWarning(code, span))
    for match in re.finditer(
        rf"(?<!\w)(?P<lower>{_NUMBER})\s*-\s*(?P<upper>[^\s,;]*)\s*кв(?!\w)",
        text,
        re.I,
    ):
        span = TextSpan(*match.span())
        if any(span.start >= item.start and span.end <= item.end for item in occupied):
            continue
        if not re.fullmatch(_NUMBER, match["upper"]):
            warnings.append(SlotWarning("invalid_numeric_value", span))
    if _is_pipeline_scope(object_kind):
        for match in re.finditer(r"(?<!\w)[dд](?!\w)\s*(?P<value>[^\s,;]+)", text, re.I):
            span = TextSpan(*match.span())
            if any(span.start >= item.start and span.end <= item.end for item in occupied):
                continue
            if not re.fullmatch(_NUMBER, match["value"]):
                warnings.append(SlotWarning("invalid_numeric_value", span))
    if _is_cable_scope(object_kind):
        for match in re.finditer(
            r"(?<!\w)\d+\s*[xх×]\s*(?P<section>[^\s,;]*)\s*мм(?:2|²)(?!\w)",
            text,
            re.I,
        ):
            span = TextSpan(*match.span())
            if any(span.start >= item.start and span.end <= item.end for item in occupied):
                continue
            if not re.fullmatch(_NUMBER, match["section"]):
                warnings.append(SlotWarning("invalid_numeric_value", span))
    return tuple(warnings)


def _normalized(kind: SlotKind, value: object, raw: str) -> str:
    if isinstance(value, DiameterValue):
        return f"{value.basis}:{_decimal_text(value.mm)}:mm"
    if isinstance(value, CableSectionValue):
        return f"{_decimal_text(value.cores)}x{_decimal_text(value.section_mm2)}:mm2"
    if isinstance(value, RangeValue):
        return f"{_decimal_text(value.lower)}..{_decimal_text(value.upper)}:{value.unit}"
    if isinstance(value, ScalarValue):
        return f"{_decimal_text(value.value)}:{value.unit}"
    if kind in {SlotKind.GOST, SlotKind.TU}:
        prefix = "гост" if kind is SlotKind.GOST else "ту"
        remainder = re.sub(r"^\s*(?:гост|ту)\s*(?:(?:-|№|no)\s*)?", "", raw, flags=re.I)
        return f"{prefix}:{_text_value(remainder)}"
    if isinstance(value, TextValue):
        return value.value
    return normalize_semantic_text(raw)


def _text_value(value: str) -> str:
    text = normalize_audit_text(value).casefold().replace("ё", "е")
    text = re.sub(r"[‐‑‒–—―−]", "-", text)
    return re.sub(r"\s*([./-])\s*", r"\1", text).strip()


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize() if value else Decimal(0), "f")


def _conflicts(slots: tuple[TypedSlot, ...]) -> tuple[SlotConflict, ...]:
    grouped: dict[SlotKind, list[TypedSlot]] = {}
    for slot in slots:
        if slot.impact in {SlotImpact.FAMILY_BOUNDARY, SlotImpact.HARD_CONFLICT}:
            grouped.setdefault(slot.kind, []).append(slot)
    result: list[SlotConflict] = []
    for kind, values in sorted(grouped.items(), key=lambda item: item[0].value):
        if len({repr(slot.value) for slot in values}) < 2:
            continue
        code = (
            "conflicting_material"
            if kind is SlotKind.MATERIAL
            else "conflicting_fire_class"
            if kind is SlotKind.FIRE_CLASS
            else "conflicting_single_value"
        )
        result.append(SlotConflict(code, kind, tuple(values)))
    return tuple(result)

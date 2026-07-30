"""Sheet-name classification, independent from worksheet contents."""

from __future__ import annotations

import re

from report_processor.schema.models import SheetType, SheetTypeCandidate
from report_processor.schema.text_normalization import compact_sheet_name, normalize_sheet_name

_KS6A_RE = re.compile(r"(?:кс|ks)\s*[-_ ]?\s*6\s*[аa]", re.IGNORECASE)
_KS2_RE = re.compile(r"(?:кс|ks)\s*[-_ ]?\s*2(?!\d)", re.IGNORECASE)
_KS3_RE = re.compile(r"(?:кс|ks)\s*[-_ ]?\s*3(?!\d)", re.IGNORECASE)


def _candidate(sheet_type: SheetType, score: float, *reasons: str) -> SheetTypeCandidate:
    return SheetTypeCandidate(sheet_type, round(min(max(score, 0.0), 1.0), 4), tuple(reasons))


def classify_sheet_name(sheet_name: str) -> tuple[SheetTypeCandidate, ...]:
    normalized = normalize_sheet_name(sheet_name)
    compact = compact_sheet_name(sheet_name)
    candidates: list[SheetTypeCandidate] = []

    is_registry = "реестр" in normalized and bool(_KS2_RE.search(normalized))
    if is_registry:
        candidates.append(_candidate(SheetType.KS2_REGISTRY, 0.98, "name:реестр", "name:кс-2"))
        candidates.append(_candidate(SheetType.KS2, 0.58, "name:кс-2", "penalty:registry"))
    elif _KS2_RE.search(normalized) or compact.startswith(("кс2", "ks2")):
        candidates.append(_candidate(SheetType.KS2, 0.95, "name:кс-2"))

    if _KS3_RE.search(normalized) or compact.startswith(("кс3", "ks3")):
        candidates.append(_candidate(SheetType.KS3, 0.95, "name:кс-3"))

    if _KS6A_RE.search(normalized) or any(
        marker in compact for marker in ("кс6а", "кс6a", "ks6a", "ks6а")
    ):
        score = 0.96
        if "титул" in normalized or "облож" in normalized:
            score = 0.74
        candidates.append(_candidate(SheetType.KS6A, score, "name:кс-6а"))

    if normalized == "сввр" or "сводная ведомость выполненных работ" in normalized:
        candidates.append(_candidate(SheetType.SVVR, 0.98, "name:сввр"))
    elif "ведомость выполненных работ" in normalized:
        candidates.append(_candidate(SheetType.SVVR, 0.82, "name:ведомость выполненных работ"))
    elif normalized == "ведомость":
        candidates.append(_candidate(SheetType.SVVR, 0.42, "name:ведомость"))

    if "допотчет" in compact or any(
        marker in normalized for marker in ("дополнительный отчет", "расчет доп отчета")
    ):
        candidates.append(_candidate(SheetType.ADDITIONAL_REPORT, 0.94, "name:допотчет"))

    if "перечень подобъект" in normalized or "справочник подобъект" in normalized:
        candidates.append(_candidate(SheetType.SUBOBJECT_REFERENCE, 0.94, "name:подобъекты"))

    if "виср" in compact or "виды и стоимость работ" in normalized:
        candidates.append(_candidate(SheetType.VISR, 0.92, "name:виср"))

    if "дрдц" in compact or "дрцд" in compact:
        candidates.append(_candidate(SheetType.DRDC, 0.94, "name:дрдц"))

    if "протокол" in normalized:
        candidates.append(_candidate(SheetType.PROTOCOL, 0.9, "name:протокол"))

    if any(marker in normalized for marker in ("титул", "титульный", "обложка")):
        score = 0.88 if normalized in {"титул", "титульный", "обложка"} else 0.76
        candidates.append(_candidate(SheetType.TITLE, score, "name:title-marker"))

    if any(marker in normalized for marker in ("технический", "служебный", "проверка")):
        candidates.append(_candidate(SheetType.TECHNICAL, 0.72, "name:technical-marker"))

    by_type: dict[SheetType, SheetTypeCandidate] = {}
    for candidate in candidates:
        previous = by_type.get(candidate.sheet_type)
        if previous is None or candidate.score > previous.score:
            by_type[candidate.sheet_type] = candidate
    return tuple(sorted(by_type.values(), key=lambda item: (-item.score, item.sheet_type.value)))

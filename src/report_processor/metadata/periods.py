from __future__ import annotations

import re
import unicodedata
from pathlib import Path, PurePosixPath

from report_processor.domain.statuses import MetadataWarning, PeriodExtractionStatus
from report_processor.metadata.period_models import (
    DocumentPeriod,
    PeriodExtractionResult,
    PeriodMatch,
)
from report_processor.metadata.period_patterns import (
    FULL_DATE_RE,
    INVALID_MONTH_YEAR_RE,
    MONTH_YEAR_RE,
    MONTHS,
    NAMED_MONTH_RE,
    YEAR_MONTH_RE,
)


def extract_document_period(value: object) -> PeriodExtractionResult:
    if value is None:
        return _not_found()
    text = _normalize(str(value))
    if not text:
        return _not_found()

    matches: list[PeriodMatch] = []
    occupied: list[tuple[int, int]] = []
    for match in FULL_DATE_RE.finditer(text):
        period = _make_period(match.group("year"), match.group("month"))
        if period is not None:
            matches.append(
                PeriodMatch(
                    period=period,
                    fragment=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9,
                    warnings=(str(MetadataWarning.PERIOD_DERIVED_FROM_FULL_DATE),),
                )
            )
            occupied.append((match.start(), match.end()))

    _collect_matches(text, NAMED_MONTH_RE, matches, occupied, named=True)
    _collect_matches(text, MONTH_YEAR_RE, matches, occupied)
    _collect_matches(text, YEAR_MONTH_RE, matches, occupied)

    unique = _unique_matches(matches)
    if not unique:
        if INVALID_MONTH_YEAR_RE.search(text):
            return PeriodExtractionResult(
                value=None,
                candidates=(),
                status=PeriodExtractionStatus.INVALID_PERIOD,
                confidence=None,
                source_fragment=None,
            )
        return _not_found()
    if len(unique) > 1:
        return PeriodExtractionResult(
            value=None,
            candidates=tuple(item.period for item in unique),
            status=PeriodExtractionStatus.MULTIPLE_PERIOD_CANDIDATES,
            confidence=None,
            source_fragment=None,
            warnings=_merge_warnings(unique),
        )

    item = unique[0]
    status = (
        PeriodExtractionStatus.LOW_CONFIDENCE_PERIOD
        if item.confidence < 0.75
        else PeriodExtractionStatus.OK
    )
    return PeriodExtractionResult(
        value=item.period,
        candidates=(item.period,),
        status=status,
        confidence=item.confidence,
        source_fragment=item.fragment,
        warnings=item.warnings,
    )


def extract_period_from_filename(filename: str) -> PeriodExtractionResult:
    name = PurePosixPath(filename.replace("\\", "/")).name
    return extract_document_period(name)


def extract_period_from_path(
    path: str | Path,
    *,
    include_parent_parts: bool = True,
) -> PeriodExtractionResult:
    raw_path = str(path).replace("\\", "/")
    parsed = PurePosixPath(raw_path)
    filename_result = extract_period_from_filename(parsed.name)
    if not include_parent_parts or raw_path.startswith("/") or _looks_windows_absolute(raw_path):
        return filename_result

    parent_results = [
        extract_document_period(part)
        for part in reversed(parsed.parts[:-1])
        if part not in {"", ".", ".."}
    ]
    parent_periods = [result.value for result in parent_results if result.value is not None]
    parent_ambiguous = [
        result
        for result in parent_results
        if result.status == PeriodExtractionStatus.MULTIPLE_PERIOD_CANDIDATES
    ]

    if filename_result.value is not None:
        all_parent_candidates = [
            *parent_periods,
            *(candidate for result in parent_ambiguous for candidate in result.candidates),
        ]
        conflicts = [period for period in all_parent_candidates if period != filename_result.value]
        if conflicts:
            return _ambiguous_periods((filename_result.value, *conflicts))
        if all_parent_candidates:
            warnings = _deduplicate_strings(
                (*filename_result.warnings, MetadataWarning.PERIOD_CONFIRMED_BY_PARENT_PATH)
            )
            return PeriodExtractionResult(
                value=filename_result.value,
                candidates=filename_result.candidates,
                status=filename_result.status,
                confidence=filename_result.confidence,
                source_fragment=filename_result.source_fragment,
                warnings=warnings,
            )
        return filename_result

    candidates = [
        *parent_periods,
        *(candidate for result in parent_ambiguous for candidate in result.candidates),
    ]
    unique = tuple(dict.fromkeys(candidates))
    if len(unique) == 1:
        return PeriodExtractionResult(
            value=unique[0],
            candidates=unique,
            status=PeriodExtractionStatus.OK,
            confidence=0.85,
            source_fragment=unique[0].normalized,
        )
    if len(unique) > 1:
        return _ambiguous_periods(unique)
    return filename_result


def parse_normalized_period(value: str) -> DocumentPeriod:
    result = extract_document_period(value)
    if result.value is None or result.value.normalized != value.strip():
        raise ValueError(f"Некорректный период: {value}")
    return result.value


def _collect_matches(
    text: str,
    pattern: re.Pattern[str],
    matches: list[PeriodMatch],
    occupied: list[tuple[int, int]],
    *,
    named: bool = False,
) -> None:
    for match in pattern.finditer(text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        month_text = match.group("month")
        month = MONTHS[month_text.lower()] if named else int(month_text)
        period = _make_period(match.group("year"), month)
        if period is None:
            continue
        confidence = 0.98 if len(match.group("year")) == 4 else 0.92
        matches.append(
            PeriodMatch(
                period=period,
                fragment=match.group(0),
                start=match.start(),
                end=match.end(),
                confidence=confidence,
                warnings=(),
            )
        )
        occupied.append((match.start(), match.end()))


def _make_period(year_value: str | int, month_value: str | int) -> DocumentPeriod | None:
    try:
        month = int(month_value)
        year_text = str(year_value)
        year = _expand_two_digit_year(int(year_text)) if len(year_text) == 2 else int(year_text)
        return DocumentPeriod(year=year, month=month)
    except (ValueError, TypeError):
        return None


def _expand_two_digit_year(year: int) -> int:
    return 2000 + year if 0 <= year <= 69 else 1900 + year


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).replace("ё", "е").lower()


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in spans)


def _unique_matches(matches: list[PeriodMatch]) -> tuple[PeriodMatch, ...]:
    result: dict[DocumentPeriod, PeriodMatch] = {}
    for item in matches:
        current = result.get(item.period)
        if current is None or item.confidence > current.confidence:
            result[item.period] = item
        elif current is not None and item.warnings:
            result[item.period] = PeriodMatch(
                period=current.period,
                fragment=current.fragment,
                start=current.start,
                end=current.end,
                confidence=current.confidence,
                warnings=_deduplicate_strings((*current.warnings, *item.warnings)),
            )
    return tuple(result.values())


def _merge_warnings(matches: tuple[PeriodMatch, ...]) -> tuple[str, ...]:
    return _deduplicate_strings(tuple(w for item in matches for w in item.warnings))


def _deduplicate_strings(values: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values))


def _ambiguous_periods(periods: tuple[DocumentPeriod, ...]) -> PeriodExtractionResult:
    unique = tuple(dict.fromkeys(periods))
    return PeriodExtractionResult(
        value=None,
        candidates=unique,
        status=PeriodExtractionStatus.MULTIPLE_PERIOD_CANDIDATES,
        confidence=None,
        source_fragment=None,
    )


def _not_found() -> PeriodExtractionResult:
    return PeriodExtractionResult(
        value=None,
        candidates=(),
        status=PeriodExtractionStatus.PERIOD_NOT_FOUND,
        confidence=None,
        source_fragment=None,
    )


def _looks_windows_absolute(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z]:/", value))

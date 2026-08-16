"""Bounded, collision-safe recognition of reporting and work scopes."""

from __future__ import annotations

import re
import unicodedata

MAX_REPORTING_SCOPE_TOKENS = 24
_TOKEN = re.compile(r"\w+", flags=re.UNICODE)
_FINAL_SCOPE_TOKEN = frozenset(
    {
        "день",
        "дня",
        "дней",
        "дню",
        "днем",
        "неделя",
        "недели",
        "недель",
        "неделю",
        "неделей",
        "месяц",
        "месяца",
        "месяцев",
        "месяце",
        "месяцем",
        "квартал",
        "квартала",
        "кварталов",
        "квартале",
        "кварталом",
        "год",
        "года",
        "лет",
        "году",
        "годом",
        "работа",
        "работы",
        "работ",
        "работе",
        "работой",
        "работам",
        "работами",
        "работах",
        "смр",
        "этап",
        "этапа",
        "этапов",
        "этапе",
        "этапом",
        "этапы",
        "отчет",
        "отчета",
        "отчету",
        "отчете",
        "отчетом",
        "отчетность",
        "отчетности",
        "отчетностью",
        "дата",
        "дату",
        "даты",
        "дате",
        "датой",
        "период",
        "периода",
        "периоде",
        "периодом",
    }
)
_BARRIER_TOKENS = frozenset({"для", "без", "не", "ни", "кроме", "против"})
_CALENDAR_MONTH_TOKENS = frozenset(
    {
        "январь",
        "января",
        "февраль",
        "февраля",
        "март",
        "марта",
        "апрель",
        "апреля",
        "май",
        "мая",
        "июнь",
        "июня",
        "июль",
        "июля",
        "август",
        "августа",
        "сентябрь",
        "сентября",
        "октябрь",
        "октября",
        "ноябрь",
        "ноября",
        "декабрь",
        "декабря",
    }
)
_BARRIER_TOKENS = _BARRIER_TOKENS | frozenset({"за", "на", "от", "до", "по"})


def is_reporting_scope(value: str) -> bool:
    """Return whether a bounded phrase is wholly a reporting/work scope."""

    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    tokens = tuple(_TOKEN.findall(normalized))
    if not tokens or len(tokens) > MAX_REPORTING_SCOPE_TOKENS:
        return False
    if _BARRIER_TOKENS & set(tokens):
        return False
    return tokens[-1] in _FINAL_SCOPE_TOKEN or _is_calendar_scope(tokens)


def _is_calendar_scope(tokens: tuple[str, ...]) -> bool:
    if len(tokens) == 1:
        return tokens[0] in _CALENDAR_MONTH_TOKENS or _year(tokens[0])
    if len(tokens) == 2:
        return tokens[0] in _CALENDAR_MONTH_TOKENS and _year(tokens[1])
    if len(tokens) == 3:
        return _day(tokens[0]) and _month_number(tokens[1]) and _year(tokens[2])
    return False


def _day(token: str) -> bool:
    return token.isdecimal() and 1 <= int(token) <= 31


def _month_number(token: str) -> bool:
    return token.isdecimal() and 1 <= int(token) <= 12


def _year(token: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", token))

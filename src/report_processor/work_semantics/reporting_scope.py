"""Bounded, collision-safe recognition of reporting and work scopes."""

from __future__ import annotations

import re
import unicodedata

MAX_REPORTING_SCOPE_TOKENS = 24
REPORTING_SCOPE_VERSION = "ReportingScope-1.1"
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
        "этапу",
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
        "периоду",
        "периоде",
        "периодом",
    }
)
_BARRIER_TOKENS = frozenset({"для", "без", "не", "ни", "кроме", "против", "за", "на", "от", "до"})
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
_NUMERAL_TOKENS = frozenset(
    {
        "ноль",
        "один",
        "одна",
        "одно",
        "два",
        "две",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
        "десять",
        "одиннадцать",
        "двенадцать",
        "тринадцать",
        "четырнадцать",
        "пятнадцать",
        "шестнадцать",
        "семнадцать",
        "восемнадцать",
        "девятнадцать",
        "двадцать",
        "тридцать",
        "сорок",
        "пятьдесят",
        "шестьдесят",
        "семьдесят",
        "восемьдесят",
        "девяносто",
        "сто",
        "двести",
        "триста",
        "четыреста",
        "пятьсот",
        "шестьсот",
        "семьсот",
        "восемьсот",
        "девятьсот",
        "тысяча",
        "тысячи",
        "тысячу",
        "тысяче",
        "тысячей",
        "тысяч",
        "тысячам",
        "тысячами",
        "тысячах",
        "миллион",
        "миллиона",
        "миллионов",
        "миллиону",
        "миллионом",
        "миллионах",
        "миллиард",
        "миллиарда",
        "миллиардов",
        "миллиарду",
        "миллиардом",
        "миллиардах",
    }
)
_DETERMINER_TOKENS = frozenset({"весь", "вся", "все", "всех"})
_WORK_SCOPE_HEADS = frozenset(
    {"работа", "работы", "работ", "работе", "работой", "работам", "работами", "работах", "смр"}
)
_WORK_AGGREGATE_EVIDENCE = frozenset(
    {
        "весь",
        "вся",
        "все",
        "всех",
        "выполненный",
        "выполненная",
        "выполненное",
        "выполненные",
        "выполненных",
        "совокупный",
        "совокупная",
        "совокупное",
        "совокупные",
        "совокупных",
        "итоговый",
        "итоговая",
        "итоговое",
        "итоговые",
        "итоговых",
    }
)
_MODIFIER = re.compile(
    r"\w*(?:ый|ий|ой|ая|яя|ое|ее|ую|юю|ого|его|ому|ему|ым|им|ыми|ими|ых|их|ые|енн(?:ый|ая|ое|ые|ого|ому|ым|ыми|ых)|анн(?:ый|ая|ое|ые|ого|ому|ым|ыми|ых))"
)


def is_reporting_scope(value: str) -> bool:
    """Return whether a bounded phrase is wholly a reporting/work scope."""

    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    tokens = tuple(_TOKEN.findall(normalized))
    if not tokens or len(tokens) > MAX_REPORTING_SCOPE_TOKENS:
        return False
    if "по" in tokens:
        if tokens.count("по") != 1:
            return False
        divider = tokens.index("по")
        return _is_scope_clause(tokens[:divider]) and _is_scope_clause(tokens[divider + 1 :])
    return _is_scope_clause(tokens)


def _is_scope_clause(tokens: tuple[str, ...]) -> bool:
    if not tokens or _BARRIER_TOKENS & set(tokens):
        return False
    if _is_calendar_scope(tokens):
        return True
    if tokens[-1] not in _FINAL_SCOPE_TOKEN or not all(
        _is_numeric_token(token)
        or token in _DETERMINER_TOKENS
        or token in _FINAL_SCOPE_TOKEN
        or bool(_MODIFIER.fullmatch(token))
        for token in tokens[:-1]
    ):
        return False
    return (
        tokens[-1] not in _WORK_SCOPE_HEADS
        or len(tokens) == 1
        or bool(_WORK_AGGREGATE_EVIDENCE & set(tokens[:-1]))
    )


def _is_numeric_token(token: str) -> bool:
    return token.isdecimal() or token in _NUMERAL_TOKENS


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

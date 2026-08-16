"""Bounded, collision-safe recognition of reporting and work scopes."""

from __future__ import annotations

import re
import unicodedata

MAX_REPORTING_SCOPE_TOKENS = 24
REPORTING_SCOPE_VERSION = "ReportingScope-2.1"
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
_WORK_SCOPE_HEADS = frozenset(
    {"работа", "работы", "работ", "работе", "работой", "работам", "работами", "работах", "смр"}
)
_TIME_SCOPE_HEADS = _FINAL_SCOPE_TOKEN & frozenset(
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
    }
)
_STAGE_SCOPE_HEADS = _FINAL_SCOPE_TOKEN & frozenset(
    {"этап", "этапа", "этапу", "этапов", "этапе", "этапом", "этапы"}
)
_REPORT_SCOPE_HEADS = (
    _FINAL_SCOPE_TOKEN - _TIME_SCOPE_HEADS - _STAGE_SCOPE_HEADS - _WORK_SCOPE_HEADS
)
_EXPLICIT_SCOPE_MARKER = re.compile(
    r"(?:весь|вся|все|всех|выполненн\w*|совокупн\w*|итогов\w*|"
    r"текущ\w*|отчетн\w*|историч\w*|документальн\w*|накопленн\w*)"
)
_DATE_MARKER_TOKENS = frozenset({"дата", "дату", "даты", "дате", "датой"})
_ORDINAL_NUMERAL = re.compile(
    r"(?:перв|втор|трет|четверт|пят|шест|седьм|восьм|девят|десят|"
    r"одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|шестнадцат|"
    r"семнадцат|восемнадцат|девятнадцат|двадцат|тридцат|сороков|"
    r"пятидесят|шестидесят|семидесят|восьмидесят|девяност|сот|тысячн|"
    r"миллионн|миллиардн)(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|"
    r"ым|им|ей|ую|юю|ых|их|ыми|ими)"
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
    head, prefix = tokens[-1], tokens[:-1]
    if head in _TIME_SCOPE_HEADS:
        return not prefix or _is_numeral_phrase(prefix) or _has_explicit_marker(prefix)
    if head in _STAGE_SCOPE_HEADS:
        return not prefix or _is_numeral_phrase(prefix) or _has_explicit_marker(prefix)
    if head in _WORK_SCOPE_HEADS or head in _REPORT_SCOPE_HEADS:
        return not prefix or _has_explicit_marker(prefix)
    return False


def _is_numeric_token(token: str) -> bool:
    return token.isdecimal() or token in _NUMERAL_TOKENS or bool(_ORDINAL_NUMERAL.fullmatch(token))


def _is_numeral_phrase(tokens: tuple[str, ...]) -> bool:
    return bool(tokens) and all(_is_numeric_token(token) for token in tokens)


def _has_explicit_marker(tokens: tuple[str, ...]) -> bool:
    return any(
        token in _DATE_MARKER_TOKENS or _EXPLICIT_SCOPE_MARKER.fullmatch(token) for token in tokens
    )


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

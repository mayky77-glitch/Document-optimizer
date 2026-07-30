from __future__ import annotations

import re

MONTHS = {
    "январь": 1,
    "января": 1,
    "февраль": 2,
    "февраля": 2,
    "март": 3,
    "марта": 3,
    "апрель": 4,
    "апреля": 4,
    "май": 5,
    "мая": 5,
    "июнь": 6,
    "июня": 6,
    "июль": 7,
    "июля": 7,
    "август": 8,
    "августа": 8,
    "сентябрь": 9,
    "сентября": 9,
    "октябрь": 10,
    "октября": 10,
    "ноябрь": 11,
    "ноября": 11,
    "декабрь": 12,
    "декабря": 12,
}
MONTH_NAMES = "|".join(sorted(MONTHS, key=len, reverse=True))
FULL_DATE_RE = re.compile(
    r"(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])[.\-_/]"
    r"(?P<month>0?[1-9]|1[0-2])[.\-_/](?P<year>\d{2}|\d{4})(?!\d)"
)
NAMED_MONTH_RE = re.compile(
    rf"(?<![а-яa-z])(?P<month>{MONTH_NAMES})(?![а-яa-z])"
    r"(?P<middle>(?:[\s_\-]+[а-яa-z]+){0,2}[\s_\-]*)"
    r"(?P<year>\d{2}|\d{4})(?!\d)",
    re.IGNORECASE,
)
MONTH_YEAR_RE = re.compile(r"(?<![\d.])(?P<month>0?[1-9]|1[0-2])[.\-_](?P<year>\d{2}|\d{4})(?!\d)")
YEAR_MONTH_RE = re.compile(r"(?<!\d)(?P<year>\d{4})[.\-_](?P<month>0?[1-9]|1[0-2])(?!\d)")
INVALID_MONTH_YEAR_RE = re.compile(
    r"(?<!\d)(?:(?P<month1>1[3-9]|[2-9]\d)[.\-_](?P<year1>\d{4})|"
    r"(?P<year2>\d{4})[.\-_](?P<month2>1[3-9]|[2-9]\d))(?!\d)"
)

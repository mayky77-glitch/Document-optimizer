from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_SIGN_RE = re.compile(r"(?:\b(?:no\.?|n°)|№)\s*", re.IGNORECASE)

_UNIT_ALIASES: dict[str, str] = {
    "м": "м",
    "м.": "м",
    "пм": "м",
    "п.м": "м",
    "п.м.": "м",
    "пог м": "м",
    "пог. м": "м",
    "м2": "м²",
    "м^2": "м²",
    "м²": "м²",
    "кв м": "м²",
    "кв. м": "м²",
    "м3": "м³",
    "м^3": "м³",
    "м³": "м³",
    "куб м": "м³",
    "куб. м": "м³",
    "шт": "шт",
    "шт.": "шт",
    "штука": "шт",
    "штук": "шт",
    "кг": "кг",
    "кг.": "кг",
    "т": "т",
    "т.": "т",
    "тонна": "т",
    "тонн": "т",
    "л": "л",
    "л.": "л",
    "компл": "компл.",
    "компл.": "компл.",
    "комплект": "компл.",
    "ед": "ед.",
    "ед.": "ед.",
    "%": "%",
}


def normalize_text(value: str | None, *, casefold: bool = True) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).replace("\u00a0", " ")
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return None
    return text.casefold() if casefold else text


def normalize_code(value: str | None) -> str | None:
    text = normalize_text(value, casefold=False)
    if text is None:
        return None
    text = _NUMBER_SIGN_RE.sub("№ ", text)
    return text.strip(" ;,") or None


def normalize_unit(value: str | None) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    compact = text.replace("²", "2").replace("³", "3")
    compact = _WHITESPACE_RE.sub(" ", compact).strip()
    return _UNIT_ALIASES.get(text, _UNIT_ALIASES.get(compact, text))

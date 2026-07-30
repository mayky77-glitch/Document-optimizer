from __future__ import annotations

import re
from collections.abc import Mapping

from report_processor.training_data.normalization import (
    normalize_code as _normalize_code,
)
from report_processor.training_data.normalization import (
    normalize_text as _normalize_text,
)
from report_processor.training_data.normalization import (
    normalize_unit as _normalize_unit,
)

from .models import TypoDictionaries

_TOKEN_RE = re.compile(r"[\w²³]+", re.UNICODE)


def _replace_exact(value: str | None, dictionary: Mapping[str, str]) -> str | None:
    if value is None:
        return None
    return dictionary.get(value, value)


def normalize_code(value: str | None, dictionaries: TypoDictionaries) -> str | None:
    return _replace_exact(_normalize_code(value), dictionaries.codes)


def normalize_name(value: str | None, dictionaries: TypoDictionaries) -> str | None:
    return _replace_exact(_normalize_text(value), dictionaries.names)


def normalize_unit(value: str | None, dictionaries: TypoDictionaries) -> str | None:
    return _replace_exact(_normalize_unit(value), dictionaries.units)


def stable_tokens(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(_TOKEN_RE.findall(value))

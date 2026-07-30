from __future__ import annotations

import re
import unicodedata

from .models import ParsedTextValue
from .statuses import TextValueStatus


def parse_text_value(value: object) -> ParsedTextValue:
    if value is None:
        return ParsedTextValue(value, None, TextValueStatus.EMPTY.value, ())
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return ParsedTextValue(
            value,
            None,
            TextValueStatus.UNSUPPORTED_VALUE_TYPE.value,
            (f"UNSUPPORTED_TEXT_TYPE:{type(value).__name__}",),
        )
    raw_text = str(value)
    number_sign_token = "\ue000"
    text = unicodedata.normalize("NFKC", raw_text.replace("№", number_sign_token))
    text = text.replace(number_sign_token, "№")
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ParsedTextValue(value, None, TextValueStatus.EMPTY.value, ())
    return ParsedTextValue(value, text, TextValueStatus.OK.value, ())

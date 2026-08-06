"""Exact dot-segment position parsing; no prefix matching is permitted."""

from __future__ import annotations

import re
from decimal import Decimal

from .models import PositionCode

_SEGMENT = re.compile(r"^\d+[a-zа-яё]*$", re.IGNORECASE)


def parse_position_code(value: object) -> PositionCode | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    if isinstance(value, Decimal) and value != value.to_integral_value():
        return None
    raw = str(value).strip().replace(" ", "")
    if not raw or raw.endswith("."):
        return None
    segments = tuple(raw.split("."))
    if not all(_SEGMENT.fullmatch(segment) for segment in segments):
        return None
    return PositionCode(raw=raw, segments=segments)


def is_ancestor_position(parent: PositionCode | str, child: PositionCode | str) -> bool:
    parsed_parent = parent if isinstance(parent, PositionCode) else parse_position_code(parent)
    parsed_child = child if isinstance(child, PositionCode) else parse_position_code(child)
    return bool(
        parsed_parent
        and parsed_child
        and len(parsed_parent.segments) < len(parsed_child.segments)
        and parsed_child.segments[: len(parsed_parent.segments)] == parsed_parent.segments
    )

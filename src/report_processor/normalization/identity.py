from __future__ import annotations

import hashlib

from .models import NormalizedBusinessKey


def _frame(value: str | None) -> bytes:
    payload = (value or "").encode("utf-8")
    return len(payload).to_bytes(4, "big") + payload


def make_line_id(business_key: NormalizedBusinessKey) -> str:
    """Build a stable business identifier without physical provenance fields."""
    digest = hashlib.sha256()
    for value in business_key.values():
        digest.update(_frame(value))
    return digest.hexdigest()

from __future__ import annotations

import pytest

from report_processor.work_semantics import (
    TERM_CANONICALIZATION_VERSION,
    canonicalize_term,
    normalize_audit_text,
    normalize_semantic_text,
)


@pytest.mark.parametrize(
    ("source", "audit", "semantic"),
    [
        ('  МОНТАЖ\u00a0Ёлки — "КС"  ', 'МОНТАЖ Ёлки — "КС"', "монтаж елки - кс"),
        ("ＤＮ５０×２", "DN50×2", "dn50x2"),
        ("Монтаж\r\nкабеля", "Монтаж кабеля", "монтаж кабеля"),
    ],
)
def test_typographic_normalization_has_golden_audit_and_semantic_identities(
    source: str, audit: str, semantic: str
) -> None:
    term = canonicalize_term(source)

    assert normalize_audit_text(source) == audit
    assert normalize_semantic_text(source) == semantic
    assert term.audit_text == audit
    assert term.semantic_text == semantic
    assert term.version == TERM_CANONICALIZATION_VERSION


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("ДН 50", "dn 50"),
        ("DN 50", "dn 50"),
        ("РN 16", "pn 16"),
        ("PN 16", "pn 16"),
        ("ДН50", "dn50"),
        ("DN50", "dn50"),
        ("РN16", "pn16"),
        ("PN16", "pn16"),
    ],
)
def test_cyrillic_and_latin_technical_homographs_normalize_identically(
    source: str, expected: str
) -> None:
    assert normalize_semantic_text(source) == expected


def test_canonicalization_keeps_audit_spelling_separate_from_semantic_identity() -> None:
    term = canonicalize_term("Ёлка—Кабель")

    assert term.audit_text == "Ёлка—Кабель"
    assert term.semantic_text == "елка - кабель"
    assert term.audit_text != term.semantic_text

"""Static contract for verification versus report-composition user flows."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_main_page_submits_explicit_verification_operation_and_explains_artifact() -> None:
    page = (ASSETS / "index.html").read_text(encoding="utf-8")
    script = (ASSETS / "admin.js").read_text(encoding="utf-8")

    assert '<input name="operation" type="hidden" value="verify">' in page
    assert "Проверить документы" in page
    assert "красными строками" in page
    assert 'data.append("operation", operation?.value || "verify")' in script
    assert 'payload.operation === "verify"' in script
    assert "Все документы проверены. Ошибок не найдено." in script
    assert "Скачать отчёт с красными строками" in script
    assert "Отчёт не требуется" in script
    assert "reviewPanel.hidden = !(technicalFailure && hasSourceIssues)" in script


def test_report_composition_keeps_route_and_explains_built_in_auto_reconciliation() -> None:
    page = (ASSETS / "drawing-card.html").read_text(encoding="utf-8")
    help_page = (ASSETS / "help.html").read_text(encoding="utf-8")

    assert 'href="/drawing-card" aria-current="page">Составление отчёта</a>' in page
    assert "Отчёт с автоматической сверкой" in page
    assert "Составьте отчёт об остатках" in page
    assert "если всё однозначно" in page
    assert "Автосверка встроена" in help_page


def test_every_admin_page_uses_the_two_primary_function_names() -> None:
    for name in ("index.html", "drawing-card.html", "package-reconciliation.html", "help.html"):
        page = (ASSETS / name).read_text(encoding="utf-8")
        assert "Проверка документов" in page
        assert "Составление отчёта" in page

"""Static browser contract for the local Excel/PDF package reconciliation UI."""

from pathlib import Path

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_package_page_uses_folder_selection_and_the_fixed_local_api() -> None:
    page = (ASSETS / "package-reconciliation.html").read_text(encoding="utf-8")
    script = (ASSETS / "package-reconciliation.js").read_text(encoding="utf-8")

    assert 'id="package-files"' in page
    assert "webkitdirectory" in page
    assert 'src="/static/package-reconciliation.js" defer' in page
    assert 'src="/static/theme.js" defer' in page
    assert 'const API = "/api/package-reconciliation/jobs";' in script
    assert 'data.append("files", file, file.webkitRelativePath || file.name)' in script
    assert "MAX_PACKAGE_FILES = 128" in script
    assert 'new Set([".xlsx", ".xlsm", ".ods"])' in script
    assert 'ALLOWED_EXTENSIONS = new Set([...WORKBOOK_EXTENSIONS, ".pdf"])' in script
    assert "Добавьте хотя бы один PDF АОСР." not in script
    assert "`${API}/${encodeURIComponent(jobId)}`" in script
    assert "`${API}/${encodeURIComponent(jobId)}/result`" in script
    assert 'method: "POST", body: data' in script


def test_package_page_renders_only_safe_evidence_text_and_keeps_accessible_states() -> None:
    page = (ASSETS / "package-reconciliation.html").read_text(encoding="utf-8")
    script = (ASSETS / "package-reconciliation.js").read_text(encoding="utf-8")
    styles = (ASSETS / "package-reconciliation.css").read_text(encoding="utf-8")

    for item in ('role="status"', 'aria-live="polite"', 'aria-live="assertive"', 'tabindex="0"'):
        assert item in page
    assert "textContent" in script
    assert "innerHTML" not in script
    assert "POLL_DELAY_MS" in script
    assert 'STATUS_PROCESSING = "processing"' in script
    assert 'STATUS_READY = "ready"' in script and 'STATUS_FAILED = "failed"' in script
    assert "REASON_LABELS" in script and "workbook_quantity" in script and "pdf_quantity" in script
    assert '@import url("/static/admin.css")' in styles
    assert ".evidence-wrap { overflow-x: auto;" in styles
    assert "@media (max-width: 720px)" in styles


def test_help_covers_all_workflows_statuses_privacy_and_recovery() -> None:
    page = (ASSETS / "help.html").read_text(encoding="utf-8")
    styles = (ASSETS / "help.css").read_text(encoding="utf-8")

    for copy in (
        "Проверка документов",
        "Составление отчёта",
        "Сравнение Excel с PDF-отчётами",
        "LibreOffice Calc",
        "MATCH",
        "MISMATCH",
        "AMBIGUOUS",
        "NO_EVIDENCE",
        "NEEDS_REVIEW",
        "Все операции выполняются на этом компьютере",
        "Панель не отвечает",
        "Poppler",
        "Tesseract",
        "сверка Excel всё равно выполняется",
        "красные строки появляются только в отдельной копии",
        "Автосверка встроена",
    ):
        assert copy in page
    assert 'src="/static/theme.js" defer' in page
    assert '@import url("/static/package-reconciliation.css")' in styles
    assert "@media (max-width: 720px)" in styles

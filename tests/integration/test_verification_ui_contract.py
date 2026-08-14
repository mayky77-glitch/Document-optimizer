"""Static contract for verification versus report-composition user flows."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_main_page_uses_explicit_operation_control_and_explains_artifact() -> None:
    page = (ASSETS / "index.html").read_text(encoding="utf-8")
    script = (ASSETS / "admin.js").read_text(encoding="utf-8")

    assert '<select id="operation" name="operation">' in page
    assert '<option value="verify" selected>Проверить документы</option>' in page
    assert '<option value="reconcile">Сверить документы</option>' in page
    assert '<input name="operation" type="hidden" value="verify">' not in page
    assert "Проверить документы" in page
    assert "красными строками" in page
    assert 'data.append("operation", operation.value)' in script
    assert 'payload.operation === "verify"' in script
    assert 'typeof payload.verification_status === "string"' not in script
    assert "Все документы проверены. Ошибок не найдено." in script
    assert "Скачать отчёт с красными строками" in script
    assert "Отчёт не требуется" in script
    assert "reviewPanel.hidden = !(technicalFailure && hasSourceIssues)" in script


def test_reporting_period_is_native_and_only_sent_for_reconciliation() -> None:
    page = (ASSETS / "index.html").read_text(encoding="utf-8")
    script = (ASSETS / "admin.js").read_text(encoding="utf-8")

    assert 'id="reporting-period-field" class="file-field" for="reporting-period" hidden' in page
    assert 'id="reporting-period" name="reporting_period" type="month" disabled' in page
    assert 'id="reporting-period-help"' in page
    assert 'const isReconciliation = operation?.value === "reconcile";' in script
    assert "reportingPeriodField.hidden = !isReconciliation;" in script
    assert "reportingPeriod.disabled = !isReconciliation;" in script
    assert 'if (!isReconciliation) reportingPeriod.value = "";' in script
    assert 'if (operation.value === "reconcile" && reportingPeriod.value) {' in script
    assert 'data.append("reporting_period", reportingPeriod.value);' in script


def test_stage_retry_keeps_exact_server_labels_and_upload_state() -> None:
    script = (ASSETS / "admin.js").read_text(encoding="utf-8")
    stage_options_body = script.split("const stageOptions", 1)[1].split(
        "const showStageSelection", 1
    )[0]

    assert 'payload.stage_options.filter((value) => typeof value === "string")' in script
    assert "new Set(payload.stage_options" not in script
    assert "value.trim()" not in stage_options_body
    assert 'data.append("stage", stage.value)' in script
    assert '[...sourceFiles.files].forEach((file) => data.append("sources", file));' in script
    assert 'data.append("target", targetFile.files[0]);' in script


def test_report_composition_keeps_route_and_explains_built_in_auto_reconciliation() -> None:
    page = (ASSETS / "drawing-card.html").read_text(encoding="utf-8")
    help_page = (ASSETS / "help.html").read_text(encoding="utf-8")

    assert 'href="/drawing-card" aria-current="page">Составление отчёта</a>' in page
    assert "Отчёт с автоматической сверкой" in page
    assert "Отчёт (карточка остатков)" in page
    assert "если всё однозначно" in page
    assert "Автосверка встроена" in help_page


def test_every_admin_page_uses_the_two_primary_function_names() -> None:
    for name in ("index.html", "drawing-card.html", "package-reconciliation.html", "help.html"):
        page = (ASSETS / name).read_text(encoding="utf-8")
        assert "Проверка документов" in page
        assert "Составление отчёта" in page

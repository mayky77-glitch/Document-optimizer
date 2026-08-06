"""Static browser-contract regression checks for the drawing-card review UI."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_theme_toggle_is_direct_accessible_and_persistent() -> None:
    page = (ASSETS / "drawing-card.html").read_text()
    main_page = (ASSETS / "index.html").read_text()
    script = (ASSETS / "theme.js").read_text()

    assert 'id="theme-toggle"' in page
    assert 'type="button"' in page
    assert 'aria-pressed="false"' in page
    assert 'src="/static/theme.js"' in page
    assert 'id="theme-toggle"' in main_page
    assert 'src="/static/theme.js"' in main_page
    assert 'STORAGE_KEY = "report-processor.theme.v1"' in script
    assert "localStorage.getItem(STORAGE_KEY)" in script
    assert "localStorage.setItem(STORAGE_KEY" in script
    assert 'toggle.setAttribute("aria-pressed", String(isDark))' in script
    assert 'toggle?.addEventListener("click"' in script


def test_file_uploads_use_aligned_labels_and_native_gazprom_buttons() -> None:
    main_styles = (ASSETS / "admin.css").read_text()
    drawing_styles = (ASSETS / "drawing-card.css").read_text()

    assert (
        ".file-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); "
        "align-items: start;"
    ) in main_styles
    for styles in (main_styles, drawing_styles):
        assert ".file-field { min-width: 0; align-content: start; }" in styles
        assert 'input[type="file"] { min-width: 0; min-height: 56px; padding: 6px 10px;' in styles
        assert 'input[type="file"]::file-selector-button {' in styles
        assert "height: 40px; margin-inline-end: 10px;" in styles
        assert (
            "border: 1px solid var(--input-border); border-radius: 2px; "
            "background: var(--soft-blue);"
        ) in styles
        assert "color: var(--gazprom-dark);" in styles
        assert 'input[type="file"]:hover::file-selector-button {' in styles
        assert 'input[type="file"]:focus-visible {' in styles
        assert "@media (max-width: 390px)" in styles
        assert (
            'input[type="file"]::file-selector-button { margin-inline-end: 8px; '
            "padding-inline: 8px; font-size: .88rem; }"
        ) in styles


def test_unresolved_cluster_has_one_action_row_without_legacy_duplicate_buttons() -> None:
    script = (ASSETS / "drawing-card-review.js").read_text()

    assert script.count('class="review-decision-actions"') == 1
    assert 'class="apply-cluster-action approve-action">Применить</button>' in script
    assert 'class="reject-cluster-action danger-action">Отклонить</button>' in script
    assert 'addAction("Одобрить", "approve", "approve-action")' not in script
    assert 'addAction("Отклонить", "reject", "danger-action")' not in script


def test_review_decision_layout_wraps_long_modes_and_moves_actions_to_a_second_row() -> None:
    styles = (ASSETS / "drawing-card.css").read_text()

    assert (
        ".review-decision { display: grid; grid-template-columns: minmax(220px, 280px) "
        "minmax(0, 390px) max-content;"
    ) in styles
    assert (
        ".review-decision-actions { grid-template-columns: repeat(2, max-content); gap: 8px; }"
        in styles
    )
    assert ".review-decision-actions button { min-width: 112px; min-height: 48px;" in styles
    assert ".segmented-control button { min-width: 0;" in styles
    assert "overflow-wrap: anywhere; white-space: normal;" in styles
    assert "@container (max-width: 860px)" in styles
    assert ".review-decision-actions { grid-column: 1 / -1; }" in styles
    assert "@container (max-width: 620px)" in styles
    assert (
        ".review-decision-actions { grid-column: auto; "
        "grid-template-columns: repeat(2, minmax(0, 1fr)); }" in styles
    )


def test_review_action_mapping_preserves_api_contract() -> None:
    script = (ASSETS / "drawing-card-review.js").read_text()

    assert 'mode === "cost_only"\n            ? "cost_only"' in script
    assert 'category.value === state.proposed ? "approve" : "change_category"' in script
    assert 'this.save(article, state.id, state.version, "reject")' in script
    assert "const payload = { action, version };" in script
    assert "if (category) payload.category = category;" in script


def test_processing_funnel_and_schema_audit_are_visible_and_path_free() -> None:
    page = (ASSETS / "drawing-card.html").read_text()
    script = (ASSETS / "drawing-card.js").read_text()
    styles = (ASSETS / "drawing-card.css").read_text()

    for element_id in (
        "processing-audit",
        "funnel-summary",
        "schema-audit-items",
        "exclusion-audit-items",
    ):
        assert f'id="{element_id}"' in page
    assert "renderProcessingAudit(payload)" in script
    assert 'new Intl.NumberFormat("ru-RU")' in script
    assert "schema?.filename" in script
    assert "absolute" not in script.casefold()
    assert ".funnel-summary" in styles
    assert ".warnings li.is-blocking" in styles


def test_background_progress_is_recoverable_cancellable_and_polled_within_five_seconds() -> None:
    page = (ASSETS / "drawing-card.html").read_text()
    script = (ASSETS / "drawing-card.js").read_text()
    styles = (ASSETS / "drawing-card.css").read_text()

    for element_id in (
        "job-progress",
        "job-phase",
        "job-progress-bar",
        "job-files-progress",
        "job-rows-progress",
        "cancel-job",
        "retry-job",
    ):
        assert f'id="{element_id}"' in page
    assert "JOB_POLL_INTERVAL_MS = 2000" in script
    assert "sessionStorage" in script
    assert "idempotencyKey" in script
    assert 'headers: { "Idempotency-Key": idempotencyKey }' in script
    assert "/cancel`" in script
    assert "/retry`" in script
    assert "schedulePolling(currentJobStatus)" in script
    assert "partial" not in page.casefold()
    assert ".job-progress" in styles
    assert ".job-progress-details" in styles


def test_idempotency_key_resets_for_request_changes_and_terminal_jobs() -> None:
    script = (ASSETS / "drawing-card.js").read_text()

    assert 'TERMINAL_JOB_STATUSES = new Set(["ready", "blocked", "failed", "cancelled"])' in script
    assert "if (resetIdempotency && changed) idempotencyKey = null;" in script
    assert "setOperation(button.dataset.operation, true)" in script
    assert 'sourceFiles.addEventListener("change", () => {\n    idempotencyKey = null;' in script
    assert 'existingCard.addEventListener("change", () => {\n    idempotencyKey = null;' in script
    assert 'period.addEventListener("change", () => {\n    idempotencyKey = null;' in script
    assert "if (TERMINAL_JOB_STATUSES.has(payload.status)) idempotencyKey = null;" in script
    assert "idempotencyKey ||= newIdempotencyKey();" in script


def test_packet_review_uses_server_categories_filters_and_per_job_session_state() -> None:
    page = (ASSETS / "drawing-card.html").read_text()
    script = (ASSETS / "drawing-card-review.js").read_text()

    for element_id in (
        "review-filters",
        "review-filter-reason",
        "review-filter-category",
        "review-filter-filename",
        "review-filter-confidence",
        "review-filter-only-unresolved",
    ):
        assert f'id="{element_id}"' in page
    assert "const categoriesFrom = (payload) => Array.isArray(payload?.review_categories)" in script
    assert "const CATEGORIES" not in script
    assert 'query.set("only_unresolved", String(this.filters.onlyUnresolved));' in script
    assert '["reason", this.filters.reason]' in script
    assert '["category", this.filters.category]' in script
    assert '["safe_filename", this.filters.filename]' in script
    assert '["confidence", this.filters.confidence]' in script
    assert 'SESSION_KEY_PREFIX = "report-processor.drawing-card.review.v2"' in script
    assert "expandedMembers" in script


def test_packet_members_show_safe_context_override_warning_and_mobile_next_action() -> None:
    page = (ASSETS / "drawing-card.html").read_text()
    script = (ASSETS / "drawing-card-review.js").read_text()
    styles = (ASSETS / "drawing-card.css").read_text()

    assert 'id="review-mobile-bar"' in page
    assert 'id="review-mobile-next"' in page
    for label in ("Файл", "Лист", "Строка", "Позиция", "Шифр", "Наименование"):
        assert f'"{label}"' in script
    assert "confidence_explanation" in script
    assert "reason_label" in script
    assert "member-override-warning" in script
    assert "Исключить из пакета" in script
    assert 'reviewId, member.version, "exclude"' in script
    assert "this.itemEndpoint(reviewId)" in script
    assert "await this.loadNextUnresolved();" in script
    assert "@media (max-width: 390px)" in styles
    assert ".review-mobile-bar { position: sticky;" in styles
    assert ".cluster-members-table-wrap { overflow-x: auto;" in styles
    assert "summary:focus-visible" in styles
    assert "approve-all" not in script.casefold()

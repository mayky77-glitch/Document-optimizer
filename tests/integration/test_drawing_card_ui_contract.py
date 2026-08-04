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
    assert (
        ".review-decision-actions { grid-column: 1 / -1; "
        "}" in styles
    )
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

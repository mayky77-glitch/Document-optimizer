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


def test_unresolved_cluster_has_one_action_row_without_legacy_duplicate_buttons() -> None:
    script = (ASSETS / "drawing-card-review.js").read_text()

    assert script.count('class="review-decision-actions"') == 1
    assert 'class="apply-cluster-action approve-action">Применить</button>' in script
    assert 'class="reject-cluster-action danger-action">Отклонить</button>' in script
    assert 'addAction("Одобрить", "approve", "approve-action")' not in script
    assert 'addAction("Отклонить", "reject", "danger-action")' not in script


def test_review_action_mapping_preserves_api_contract() -> None:
    script = (ASSETS / "drawing-card-review.js").read_text()

    assert 'mode === "cost_only"\n            ? "cost_only"' in script
    assert 'category.value === state.proposed ? "approve" : "change_category"' in script
    assert 'this.save(article, state.id, state.version, "reject")' in script
    assert "const payload = { action, version };" in script
    assert "if (category) payload.category = category;" in script

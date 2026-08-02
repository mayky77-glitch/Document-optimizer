"""Static browser-contract checks for the reconciliation package review UI."""

from pathlib import Path

from report_processor.admin_panel.view import static_asset

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_package_review_assets_are_published_and_registered_by_the_main_screen() -> None:
    page = (ASSETS / "index.html").read_text(encoding="utf-8")

    assert 'src="/static/reconciliation-batches.js" defer' in page
    assert 'src="/static/reconciliation-batch-filters.js" defer' in page
    for asset_name in ("reconciliation-batches.js", "reconciliation-batch-filters.js"):
        media_type, content = static_asset(asset_name)
        assert media_type == "text/javascript; charset=utf-8"
        assert content == (ASSETS / asset_name).read_bytes()


def test_package_review_uses_only_the_frozen_public_payload_and_routes() -> None:
    script = (ASSETS / "reconciliation-batches.js").read_text(encoding="utf-8")

    for field in (
        "review_packages",
        "review_summary",
        "review_categories",
        "review_can_apply",
        "review_last_action",
        "package_id",
        "family_id",
        "group_id",
        "row_id",
        "version",
    ):
        assert field in script
    for route in (
        "/review/packages/${encodeURIComponent(item.package_id)}",
        "/review/families/${encodeURIComponent(family.family_id)}",
        "/review/groups/${encodeURIComponent(group.group_id)}",
        "/review/items/${encodeURIComponent(member.row_id)}",
        "/review/packages/accept-safe",
        "/review/undo",
    ):
        assert route in script
    assert "package_id: item.package_id, version: item.version" in script
    assert "http://" not in script and "https://" not in script


def test_package_review_keeps_direct_accessible_controls_and_mobile_rules() -> None:
    script = (ASSETS / "reconciliation-batches.js").read_text(encoding="utf-8")
    styles = (ASSETS / "admin.css").read_text(encoding="utf-8")

    assert 'input.type = "radio"' in script
    assert '"Количество + стоимость"' in script and '"Только стоимость"' in script
    assert "Принять пакет" in script
    assert "Принять все безопасные" in script and "Применить ${safe.length}" in script
    for shortcut in ("A</kbd>", "R</kbd>", "J</kbd>", "U</kbd>"):
        assert shortcut in script
    assert 'document.createElement("details")' in script
    assert "minimumFractionDigits: 2" in script and "maximumFractionDigits: 2" in script
    assert ".batch-mode-options { grid-template-columns: 1fr; }" in styles
    mobile_grid = (
        ".batch-summary, .batch-totals, .batch-family-actions, .batch-scope-actions, "
        ".batch-row-actions > div { grid-template-columns: 1fr; }"
    )
    assert mobile_grid in styles
    assert "@media (max-width: 390px)" in styles


def test_canonical_primary_and_compact_secondary_filters_have_fail_soft_defaults() -> None:
    filters = (ASSETS / "reconciliation-batch-filters.js").read_text(encoding="utf-8")

    for label in (
        "Можно принять пакетом",
        "Есть расхождения",
        "Новые формулировки",
        "Уже знакомые",
        "Только стоимость",
        "Подозрительные значения",
    ):
        assert label in filters
    for field in (
        "category",
        "mode",
        "unitFamily",
        "size",
        "exceptions",
        "readyForMass",
        "manuallyChanged",
    ):
        assert field in filters
    assert '["safe", "clarify", "new"].includes(item?.queue)' in filters
    assert "window.ReconciliationBatchFilters" in filters

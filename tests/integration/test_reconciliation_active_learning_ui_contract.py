"""Static browser contract for the closed active-learning web DTO."""

from pathlib import Path

from report_processor.admin_panel.view import static_asset

ASSETS = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"


def test_active_learning_asset_is_published_and_additive_to_package_review() -> None:
    page = (ASSETS / "index.html").read_text(encoding="utf-8")
    admin = (ASSETS / "admin.js").read_text(encoding="utf-8")

    assert 'src="/static/reconciliation-active-learning.js" defer' in page
    media_type, content = static_asset("reconciliation-active-learning.js")
    assert media_type == "text/javascript; charset=utf-8"
    assert content == (ASSETS / "reconciliation-active-learning.js").read_bytes()
    assert "window.ReconciliationActiveLearning?.supports(payload)" in admin
    assert "reviewFocusRestored = activeLearningReview.render(payload) === true" in admin
    assert "if (!reviewFocusRestored) reviewPanel.focus({ preventScroll: true });" in admin
    assert 'payload?.code === "stale_state"' in admin
    assert "error.code = controlledCode" in admin


def test_active_learning_accepts_only_the_closed_web_queue_and_request_shapes() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")

    assert 'const WEB_QUEUE_VERSION = "ActiveLearningWebQueue-1.0"' in script
    assert 'const SHADOW_REQUEST_VERSION = "ActiveLearningShadowRequest-1.0"' in script
    for field in (
        '"expected_autosave_fingerprint"',
        "expected_autosave_fingerprint: this.queue.expectedAutosaveFingerprint",
        "version: SHADOW_REQUEST_VERSION",
        'split_member_refs: action === "split" ? item.proposedSplit : []',
    ):
        assert field in script
    assert "exactKeys(value, QUEUE_KEYS)" in script
    assert "exactKeys(value, ITEM_KEYS)" in script
    assert "Number.isSafeInteger(value)" in script
    assert "MAX_QUEUE_ITEMS = 512" in script
    assert "value.items.length > MAX_QUEUE_ITEMS" in script
    assert "if (value.length < 2) return null;" in script
    assert ".sort(" not in script


def test_active_learning_localizes_only_closed_codes_and_keeps_opaque_ids_out_of_dom() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")

    for closed_map in ("KIND_LABELS", "MODE_LABELS", "ACTION_LABELS", "CODE_LABELS"):
        assert f"const {closed_map}" in script
    for forbidden in (
        "value.title",
        "category_label",
        "value.reason",
        "slots",
        "differences",
        "examples",
        "dataset.itemId",
        "data-item-id",
    ):
        assert forbidden not in script
    assert "cardsById = new Map()" in script
    assert "this.cardsById.get(this.focusItemId)" in script
    assert "textContent" in script and "innerHTML" not in script


def test_active_learning_keeps_native_accessibility_and_existing_small_screen_rules() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")
    styles = (ASSETS / "admin.css").read_text(encoding="utf-8")

    assert 'document.createElement("button")' in script
    assert 'document.createElement("details")' in script
    assert 'aria-live", "polite"' in script
    assert "return this.restoreFocus();" in script
    assert ".active-learning-card" in styles
    assert ".active-learning-action:focus-visible" in styles
    assert "@media (max-width: 390px)" in styles

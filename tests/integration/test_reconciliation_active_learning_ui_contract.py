"""Static browser contract for the optional active-learning review queue."""

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
    assert "activeLearningReview.render(payload)" in admin
    assert "activeLearningReview?.clear()" in admin


def test_active_learning_consumes_only_its_optional_controlled_projection() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")

    assert "active_learning_queue" in script
    for state in ("loading", "empty", "ready", "saving", "saved", "stale", "unavailable"):
        assert f'"{state}"' in script
    for action in ("Принять шаблон", "Оставить только для этого случая", "Разделить", "Отклонить"):
        assert action in script
    for forbidden in ("digest", "provenance", "evidence", "confidence", "similarity", "model"):
        assert forbidden not in script
    assert "innerHTML" not in script
    assert "textContent" in script
    assert ".sort(" not in script
    assert "dataset.itemId" not in script and "data-item-id" not in script
    assert "dataset.focusKey" in script
    assert "normalized.length <= 200" in script
    assert ".slice(0, 50)" in script


def test_active_learning_keeps_native_accessible_controls_and_small_screen_rules() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")
    styles = (ASSETS / "admin.css").read_text(encoding="utf-8")

    assert 'document.createElement("button")' in script
    assert 'document.createElement("details")' in script
    assert 'aria-live", "polite"' in script
    assert "focus({ preventScroll: true })" in script
    assert ".active-learning-card" in styles
    assert ".active-learning-action:focus-visible" in styles
    assert "@media (max-width: 390px)" in styles
    assert "prefers-reduced-motion: reduce" in styles


def test_active_learning_submits_only_server_offered_shadow_actions() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")
    admin = (ASSETS / "admin.js").read_text(encoding="utf-8")

    assert "ACTIONS.has(action)" in script
    assert 'action !== "split" || item.splitMemberRefs.length > 1' in script
    assert 'split_member_refs: action === "split" ? item.splitMemberRefs : []' in script
    assert "/review/active-learning/items/${encodeURIComponent(itemId)}/shadow" in admin
    assert "accept-safe" not in script


def test_active_learning_uses_exact_intent_staleness_tokens_and_nested_split_groups() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")

    assert "Number.isSafeInteger(value)" in script
    assert "Number(value)" not in script
    assert "active-learning-queue-[0-9a-f]{64}" in script
    assert "active-learning-item-[0-9a-f]{64}" in script
    assert "sha256:[0-9a-f]{64}" in script
    for field in (
        "queue_id: this.queue.queueId",
        "expected_queue_fingerprint: this.queue.expectedQueueFingerprint",
        "item_id: item.itemId",
        "expected_item_fingerprint: item.expectedItemFingerprint",
        "version: INTENT_VERSION",
    ):
        assert field in script
    assert 'const INTENT_VERSION = "ActiveLearningIntent-1.0"' in script
    assert 'split_member_refs: action === "split" ? item.splitMemberRefs : []' in script
    assert "if (!Array.isArray(group)" in script
    assert "normalized.flat()" in script
    assert "split group" not in script
    assert "splitMemberRefs.length > 1" in script
    assert "dataset.itemId" not in script and "data-item-id" not in script


def test_active_learning_sends_the_exact_parser_shape_with_bounded_unique_actions() -> None:
    script = (ASSETS / "reconciliation-active-learning.js").read_text(encoding="utf-8")

    assert "MAX_INTEGER_AGGREGATE = 2147483647" in script
    assert "value <= MAX_INTEGER_AGGREGATE" in script
    assert 'split_member_refs: action === "split" ? item.splitMemberRefs : []' in script
    assert "const uniqueActions" in script
    assert "!unique.includes(action)" in script

"""Synthetic integration checks for the inert active-learning adapter/store boundary."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import replace

import pytest

from report_processor.admin_panel.reconciliation_active_learning_adapter import (
    project_active_learning_queue,
)
from report_processor.admin_panel.reconciliation_active_learning_api import (
    parse_active_learning_intent,
)
from report_processor.admin_panel.reconciliation_active_learning_store import (
    ActiveLearningShadowStore,
    ActiveLearningStoreConflict,
    ActiveLearningStoreError,
    ActiveLearningUndoUnavailable,
)
from report_processor.reconciliation_patterns.active_learning import (
    INTENT_VERSION,
    ActiveLearningContractError,
    ActiveLearningMode,
    ActiveLearningPresentation,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
)


def _ref(token: str) -> str:
    return "sha256:" + token * 64


def _item(token: str = "1", **changes: object) -> ActiveLearningQueueItem:
    values: dict[str, object] = {
        "kind": QueueItemKind.PATTERN,
        "pattern_ref": _ref(token),
        "package_ref": None,
        "source_head_ref": _ref("2"),
        "item_version_ref": _ref("3"),
        "source_fingerprint_refs": (_ref("4"),),
        "category_ref": _ref("5"),
        "mode": ActiveLearningMode.QUANTITY_COST,
        "member_refs": (_ref("6"), _ref("7")),
        "coverage_family_count": 1,
        "coverage_group_count": 2,
        "affected_row_count": 3,
        "affected_cost_minor_units": 4,
        "hard_negative_proximity": 5,
        "uncertainty_signal_count": 6,
        "novelty_signal_count": 7,
        "document_frequency_count": 8,
        "expected_action_reduction": 9,
        "row_override_count": 0,
        "presentation": ActiveLearningPresentation(
            summary_codes=(PresentationCode.PATTERN_CANDIDATE,),
            difference_codes=(PresentationCode.CATEGORY_DIFFERENCE,),
        ),
        "allowed_actions": tuple(ShadowAction),
    }
    values.update(changes)
    return ActiveLearningQueueItem(**values)  # type: ignore[arg-type]


def _queue(item: ActiveLearningQueueItem | None = None) -> ActiveLearningQueue:
    return project_active_learning_queue(
        queue_ref=_ref("8"),
        source_fingerprint_refs=(_ref("9"),),
        items=(item or _item(),),
    )


def _intent(queue: ActiveLearningQueue, item: ActiveLearningQueueItem):
    return parse_active_learning_intent(
        {
            "version": INTENT_VERSION,
            "queue_id": queue.queue_id,
            "expected_queue_fingerprint": queue.fingerprint,
            "item_id": item.item_id,
            "expected_item_fingerprint": item.fingerprint,
            "action": ShadowAction.REJECT.value,
            "split_member_refs": [],
        }
    )


def test_projection_is_pure_deterministic_and_accepts_validated_items_only() -> None:
    first = _item("1", expected_action_reduction=1)
    second = _item("a", expected_action_reduction=2)

    projected = project_active_learning_queue(
        queue_ref=_ref("8"),
        source_fingerprint_refs=(_ref("9"),),
        items=(first, second),
    )
    permuted = project_active_learning_queue(
        queue_ref=_ref("8"),
        source_fingerprint_refs=(_ref("9"),),
        items=(second, first),
    )

    assert projected == permuted
    assert projected.items == (second, first)
    with pytest.raises(ActiveLearningContractError):
        project_active_learning_queue(
            queue_ref=_ref("8"),
            source_fingerprint_refs=(_ref("9"),),
            items=({"raw_text": "forbidden"},),  # type: ignore[arg-type]
        )
    with pytest.raises(ActiveLearningContractError):
        _item(affected_cost_minor_units=True)


def test_store_atomic_roundtrip_is_private_and_contains_only_shadow_fields(
    tmp_path, monkeypatch
) -> None:
    item = _item()
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "job" / "shadow.json")
    initial = store.load(queue)
    replacements: list[tuple[os.PathLike[str] | str, os.PathLike[str] | str]] = []
    real_replace = os.replace

    def tracked_replace(source, destination):
        replacements.append((source, destination))
        assert os.fspath(os.path.dirname(source)) == os.fspath(store.path.parent)
        assert stat.S_IMODE(os.stat(source).st_mode) == 0o600
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", tracked_replace)
    saved = store.apply(
        queue,
        _intent(queue, item),
        expected_autosave_fingerprint=initial.fingerprint,
    )

    payload = json.loads(store.path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, sort_keys=True)
    assert saved.intents[0].item_id == item.item_id
    assert replacements and os.fspath(replacements[0][1]) == os.fspath(store.path)
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert set(payload) == {"version", "current", "previous"}
    assert not {
        "raw_text",
        "path",
        "presentation",
        "category",
        "confidence",
        "coordinate",
        "vector",
    } & set(serialized.lower().split('"'))


def test_stale_queue_item_or_autosave_never_mutates_the_file(tmp_path) -> None:
    item = _item()
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    initial = store.load(queue)
    saved = store.apply(
        queue,
        _intent(queue, item),
        expected_autosave_fingerprint=initial.fingerprint,
    )
    before = store.path.read_bytes()
    stale_item = replace(_intent(queue, item), expected_item_fingerprint=_ref("a"))

    for stale_queue, intent, expected in (
        (queue, _intent(queue, item), initial.fingerprint),
        (queue, stale_item, saved.fingerprint),
        (
            replace(queue, source_fingerprint_refs=(_ref("a"),)),
            _intent(queue, item),
            saved.fingerprint,
        ),
    ):
        with pytest.raises(ActiveLearningStoreConflict):
            store.apply(
                stale_queue,
                intent,
                expected_autosave_fingerprint=expected,
            )
        assert store.path.read_bytes() == before


def test_row_overrides_block_before_first_write(tmp_path) -> None:
    item = _item(row_override_count=1)
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    initial = store.load(queue)

    with pytest.raises(ActiveLearningStoreConflict):
        store.apply(
            queue,
            _intent(queue, item),
            expected_autosave_fingerprint=initial.fingerprint,
        )

    assert not store.path.exists()


def test_store_supports_exactly_one_step_of_undo(tmp_path) -> None:
    item = _item()
    queue = _queue(item)
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    initial = store.load(queue)
    saved = store.apply(
        queue,
        _intent(queue, item),
        expected_autosave_fingerprint=initial.fingerprint,
    )
    undone = store.undo(queue, expected_autosave_fingerprint=saved.fingerprint)
    before = store.path.read_bytes()

    assert undone == initial
    with pytest.raises(ActiveLearningUndoUnavailable):
        store.undo(queue, expected_autosave_fingerprint=undone.fingerprint)
    assert store.path.read_bytes() == before


def test_malformed_foreign_or_public_file_fails_closed_without_rewrite(tmp_path) -> None:
    queue = _queue()
    path = tmp_path / "shadow.json"
    cases = (
        b"not-json",
        b'{"version":"ActiveLearningShadowStore-1.1","current":null,"previous":null}',
    )
    for content in cases:
        path.write_bytes(content)
        path.chmod(0o600)
        before = path.read_bytes()
        with pytest.raises(ActiveLearningStoreError):
            ActiveLearningShadowStore(path).load(queue)
        assert path.read_bytes() == before

    path.write_text("{}", encoding="utf-8")
    path.chmod(0o644)
    before = path.read_bytes()
    with pytest.raises(ActiveLearningStoreError):
        ActiveLearningShadowStore(path).load(queue)
    assert path.read_bytes() == before

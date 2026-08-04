"""Synthetic integration checks for the inert active-learning adapter/store boundary."""

from __future__ import annotations

import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import replace
from threading import Barrier, BrokenBarrierError

import pytest

from report_processor.admin_panel.reconciliation_active_learning_adapter import (
    project_active_learning_queue,
)
from report_processor.admin_panel.reconciliation_active_learning_api import (
    parse_active_learning_intent,
)
from report_processor.admin_panel.reconciliation_active_learning_store import (
    STORE_VERSION,
    ActiveLearningShadowStore,
    ActiveLearningStoreConflict,
    ActiveLearningStoreError,
    ActiveLearningStoreStaleConflict,
    ActiveLearningUndoUnavailable,
)
from report_processor.reconciliation_patterns.active_learning import (
    AUTOSAVE_VERSION,
    INTENT_VERSION,
    ActiveLearningContractError,
    ActiveLearningIntent,
    ActiveLearningMode,
    ActiveLearningPresentation,
    ActiveLearningQueue,
    ActiveLearningQueueItem,
    ActiveLearningShadowAutosave,
    PresentationCode,
    QueueItemKind,
    ShadowAction,
    canonical_json_bytes,
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


def _persisted_bytes(
    current: ActiveLearningShadowAutosave,
    previous: ActiveLearningShadowAutosave | None = None,
) -> bytes:
    def intent_payload(intent: ActiveLearningIntent) -> dict[str, object]:
        return {
            "version": intent.version,
            "queue_id": intent.queue_id,
            "expected_queue_fingerprint": intent.expected_queue_fingerprint,
            "item_id": intent.item_id,
            "expected_item_fingerprint": intent.expected_item_fingerprint,
            "action": intent.action.value,
            "split_member_refs": intent.split_member_refs,
        }

    def autosave_payload(autosave: ActiveLearningShadowAutosave) -> dict[str, object]:
        return {
            "version": AUTOSAVE_VERSION,
            "queue_id": autosave.queue_id,
            "queue_fingerprint": autosave.queue_fingerprint,
            "intents": tuple(intent_payload(intent) for intent in autosave.intents),
        }

    return canonical_json_bytes(
        {
            "version": STORE_VERSION,
            "current": autosave_payload(current),
            "previous": None if previous is None else autosave_payload(previous),
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
    assert stat.S_ISREG(store.lock_path.stat().st_mode)
    assert stat.S_IMODE(store.lock_path.stat().st_mode) == 0o600
    assert store.lock_path.read_bytes() == b""
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


def test_same_fingerprint_concurrency_has_one_success_and_one_stale(tmp_path, monkeypatch) -> None:
    item = _item()
    queue = _queue(item)
    path = tmp_path / "shadow.json"
    stores = (ActiveLearningShadowStore(path), ActiveLearningShadowStore(path))
    initial = stores[0].load(queue)
    callers_ready = Barrier(2)
    rendezvous = Barrier(2)
    original_load = ActiveLearningShadowStore._load_envelope

    def synchronized_load(store, supplied_queue):
        loaded = original_load(store, supplied_queue)
        with suppress(BrokenBarrierError):
            rendezvous.wait(timeout=0.25)
        return loaded

    monkeypatch.setattr(ActiveLearningShadowStore, "_load_envelope", synchronized_load)

    def apply(store: ActiveLearningShadowStore) -> str:
        callers_ready.wait(timeout=2)
        try:
            store.apply(
                queue,
                _intent(queue, item),
                expected_autosave_fingerprint=initial.fingerprint,
            )
        except ActiveLearningStoreStaleConflict:
            return "stale"
        return "success"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(apply, stores))

    assert sorted(outcomes) == ["stale", "success"]
    assert stores[0].load(queue).intents == (_intent(queue, item),)


def test_lock_rejects_symlink_or_nonregular_and_never_contains_data(tmp_path) -> None:
    queue = _queue()
    store = ActiveLearningShadowStore(tmp_path / "shadow.json")
    target = tmp_path / "target.lock"
    target.write_bytes(b"")
    target.chmod(0o600)
    store.lock_path.symlink_to(target)

    with pytest.raises(ActiveLearningStoreError):
        store.load(queue)
    assert target.read_bytes() == b""

    store.lock_path.unlink()
    store.lock_path.mkdir()
    with pytest.raises(ActiveLearningStoreError):
        store.load(queue)


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


def test_load_rebinds_every_current_and_previous_intent_to_the_exact_queue(tmp_path) -> None:
    cases: list[tuple[ActiveLearningQueue, ActiveLearningIntent]] = []

    ordinary = _item()
    ordinary_queue = _queue(ordinary)
    cases.append(
        (
            ordinary_queue,
            replace(
                _intent(ordinary_queue, ordinary),
                expected_item_fingerprint=_ref("a"),
            ),
        )
    )

    restricted = _item(allowed_actions=(ShadowAction.REJECT,))
    restricted_queue = _queue(restricted)
    cases.append(
        (
            restricted_queue,
            ActiveLearningIntent(
                restricted_queue.queue_id,
                restricted_queue.fingerprint,
                restricted.item_id,
                restricted.fingerprint,
                ShadowAction.ACCEPT_PATTERN,
            ),
        )
    )

    overridden = _item(row_override_count=1)
    overridden_queue = _queue(overridden)
    cases.append((overridden_queue, _intent(overridden_queue, overridden)))

    split_item = _item(member_refs=(_ref("6"), _ref("7"), _ref("a")))
    split_queue = _queue(split_item)
    cases.append(
        (
            split_queue,
            ActiveLearningIntent(
                split_queue.queue_id,
                split_queue.fingerprint,
                split_item.item_id,
                split_item.fingerprint,
                ShadowAction.SPLIT,
                ((_ref("6"),), (_ref("7"),)),
            ),
        )
    )

    for case_number, (queue, invalid_intent) in enumerate(cases):
        invalid = ActiveLearningShadowAutosave(
            queue.queue_id,
            queue.fingerprint,
            (invalid_intent,),
        )
        empty = ActiveLearningShadowAutosave(queue.queue_id, queue.fingerprint)
        for slot, current, previous in (
            ("current", invalid, None),
            ("previous", empty, invalid),
        ):
            path = tmp_path / f"{case_number}-{slot}.json"
            path.write_bytes(_persisted_bytes(current, previous))
            path.chmod(0o600)
            before = path.read_bytes()

            with pytest.raises(ActiveLearningStoreConflict):
                ActiveLearningShadowStore(path).load(queue)

            assert path.read_bytes() == before

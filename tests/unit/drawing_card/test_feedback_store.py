from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from report_processor.drawing_card.review.feedback import (
    FeedbackContext,
    FeedbackEntry,
    FeedbackStore,
)


def _context(**changes: object) -> FeedbackContext:
    work = str(changes.pop("normalized_work", "Монтаж кабеля"))
    values: dict[str, object] = {
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "normalized_work": work,
        "work_fingerprint": sha256(work.lower().encode()).hexdigest(),
        "proposed_category": "cable",
        "contract_position": "position-1",
        "match_mode": "exact",
        "source_unit": "м",
        "unit_policy": "quantity_cost",
        "input_hashes": ("a" * 64, "b" * 64),
        "model_version": "model-1",
        "rules_version": "rules-1",
        "subject_type": "row",
        "member_ids": ("member-1",),
    }
    values.update(changes)
    return FeedbackContext(**values)  # type: ignore[arg-type]


def _entry(context: FeedbackContext | None = None, **changes: object) -> FeedbackEntry:
    values: dict[str, object] = {
        "context": context or _context(),
        "selected_category": "cable",
        "action": "confirm",
        "author": "reviewer",
        "created_at": "2026-08-06T01:02:03Z",
    }
    values.update(changes)
    return FeedbackEntry(**values)  # type: ignore[arg-type]


def test_append_page_is_atomic_when_duplicate_conflicts(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    store = FeedbackStore(path)
    first = _entry()
    store.append_page((first,))
    conflicting = replace(first, selected_category="other")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        store.append_page((_entry(created_at="2026-08-06T01:02:04Z"), conflicting))
    assert store.lookup_exact(first.context) == first
    assert path.read_text(encoding="utf-8").count("\n") == 1


def test_lookup_is_tenant_and_project_scoped(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    context = _context()
    entry = _entry(context)
    store.append_page((entry,))
    assert store.lookup_exact(replace(context, tenant_id="tenant-b")) is None
    assert store.lookup_exact(replace(context, project_id="project-b")) is None
    assert store.lookup_exact(context) == entry


@pytest.mark.parametrize(
    "field,value",
    [
        ("normalized_work", "Монтаж другого кабеля"),
        ("proposed_category", "pipe"),
        ("contract_position", "position-2"),
        ("match_mode", "semantic"),
        ("source_unit", "шт"),
        ("unit_policy", "cost_only"),
        ("input_hashes", ("c" * 64,)),
        ("model_version", "model-2"),
        ("rules_version", "rules-2"),
        ("subject_type", "packet"),
        ("member_ids", ("member-2",)),
    ],
)
def test_every_context_dimension_must_match_exactly(
    tmp_path: Path, field: str, value: object
) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    context = _context()
    store.append_page((_entry(context),))
    if field == "normalized_work":
        changed = _context(normalized_work=value)
    else:
        changed = replace(context, **{field: value})
    assert store.lookup_exact(changed) is None


def test_schema_versions_and_work_fingerprint_are_fixed(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    store = FeedbackStore(path)
    entry = _entry()
    store.append_page((entry,))
    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    payload["schema_version"] = "DrawingCardFeedback-1.0"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema version"):
        store.lookup_exact(entry.context)
    with pytest.raises(ValueError, match="work_fingerprint"):
        _context(work_fingerprint="0" * 64)


def test_invalidation_retains_audit_history_and_makes_lookup_miss(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    store = FeedbackStore(path)
    earlier = _entry(created_at="2026-08-06T01:02:02Z")
    entry = _entry()
    store.append_page((earlier, entry))
    invalid = store.invalidate(
        entry.event_id, "auditor", datetime(2026, 8, 6, tzinfo=UTC), "bad source"
    )
    assert not invalid.valid
    assert invalid.supersedes_event_id == entry.event_id
    assert store.lookup_exact(entry.context) is None
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [event["event_id"] for event in events] == [
        earlier.event_id,
        entry.event_id,
        invalid.event_id,
    ]


def test_invalidation_retains_explicit_review_resolutions(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    entry = _entry(
        _context(unit_policy="review_review"),
        selected_quantity_resolution="include",
        selected_cost_resolution="exclude",
    )
    store.append_page((entry,))

    invalid = store.invalidate(entry.event_id, "auditor", "2026-08-06T01:03:00Z", "superseded")

    assert invalid.selected_quantity_resolution == "include"
    assert invalid.selected_cost_resolution == "exclude"
    assert not invalid.valid


def test_hazards_never_replay_and_similar_text_never_hits(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    hazardous = _entry(hazards=("formula-risk",))
    store.append_page((hazardous,))
    assert store.lookup_exact(hazardous.context) is None
    assert store.lookup_exact(_context(normalized_work="Монтаж кабеля усиленный")) is None


def test_conflicting_duplicate_ids_fail_whole_initial_page(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    entry = _entry(event_id="event-1")
    with pytest.raises(ValueError, match="conflicting duplicate"):
        store.append_page((entry, replace(entry, action="exclude", selected_category=None)))
    assert not (tmp_path / "feedback.jsonl").exists()


def test_permissions_are_private(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    FeedbackStore(path).append_page((_entry(),))
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_concurrent_store_instances_do_not_lose_pages(tmp_path: Path) -> None:
    path = tmp_path / "feedback.jsonl"
    entries = tuple(_entry(created_at=f"2026-08-06T01:02:0{second}Z") for second in (3, 4))

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda entry: FeedbackStore(path).append_page((entry,)), entries))

    assert {entry.event_id for entry in FeedbackStore(path)._read()} == {
        entry.event_id for entry in entries
    }

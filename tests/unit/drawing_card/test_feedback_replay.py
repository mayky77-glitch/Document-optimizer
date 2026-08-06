from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.drawing_card.audit.funnel import disposition_for_decision, funnel_summary
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
    WorkflowRequest,
)
from report_processor.drawing_card.review.context import (
    build_feedback_context,
    replay_exact_feedback,
)
from report_processor.drawing_card.review.feedback import FeedbackEntry, FeedbackStore
from report_processor.drawing_card.sources.manifest import scan_directory, scan_file
from report_processor.drawing_card.sources.normalization import stable_id
from report_processor.drawing_card.workflow import _validate_request


def _row(**changes: object) -> DrawingSourceRow:
    values: dict[str, object] = {
        "row_id": "row-1",
        "location": DrawingSourceLocation("file-1", "book.xlsx", "Sheet", 4, ("A4",)),
        "object_index_raw": "1001",
        "drawing_code_raw": "D-1",
        "work_name_raw": "Монтаж кабеля",
        "unit_raw": "м",
        "remaining_quantity": Decimal("2"),
        "remaining_total_cost": Decimal("10"),
        "formula_values": (),
        "cached_values": (),
        "source_document_type": "ks6a",
        "source_period": "2026-08",
        "source_revision": None,
        "status": "OK",
        "warnings": (),
        "position_code_raw": "1.2",
    }
    values.update(changes)
    return DrawingSourceRow(**values)  # type: ignore[arg-type]


def _decision(**changes: object) -> MatchDecision:
    values: dict[str, object] = {
        "row_id": "row-1",
        "category": TargetWorkCategory.POWER_CABLE,
        "quantity_decision": "include",
        "cost_decision": "include",
        "quantity_rule_id": None,
        "cost_rule_id": None,
        "quantity_confidence": None,
        "cost_confidence": None,
        "matching_strategy": "tiny_model_suggestion",
        "evidence_ids": (),
        "reason": "manual candidate",
        "requires_manual_review": True,
        "status": "UNCONFIRMED_CLASSIFICATION",
        "warnings": (),
    }
    values.update(changes)
    return MatchDecision(**values)  # type: ignore[arg-type]


def _context(row: DrawingSourceRow, decision: MatchDecision, **changes: object):
    values: dict[str, object] = {
        "tenant_id": "local",
        "project_id": "project-1",
        "input_hashes": ("a" * 64,),
        "model_version": "DrawingCardMatcher-1.0",
        "rules_version": "rules-1",
    }
    values.update(changes)
    return build_feedback_context(row, decision, **values)  # type: ignore[arg-type]


def _entry(context, **changes: object) -> FeedbackEntry:
    values: dict[str, object] = {
        "context": context,
        "selected_category": TargetWorkCategory.LOW_CURRENT_CABLE.value,
        "action": "reclassify",
        "author": "reviewer",
        "created_at": "2026-08-06T01:02:03Z",
    }
    values.update(changes)
    return FeedbackEntry(**values)  # type: ignore[arg-type]


def _replay(
    store: FeedbackStore,
    row: DrawingSourceRow,
    decision: MatchDecision,
    **changes: object,
):
    values: dict[str, object] = {
        "tenant_id": "local",
        "project_id": "project-1",
        "input_hashes": ("a" * 64,),
        "model_version": "DrawingCardMatcher-1.0",
        "rules_version": "rules-1",
    }
    values.update(changes)
    return replay_exact_feedback(row, decision, store=store, **values)  # type: ignore[arg-type]


def test_exact_replay_reclassifies_and_preserves_disposition_accounting(tmp_path: Path) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    entry = _entry(context)
    store.append_page((entry,))

    replayed = _replay(store, row, decision)

    assert replayed is not None
    assert replayed.category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert replayed.matching_strategy == "exact_feedback_replay"
    assert replayed.evidence_ids == (entry.event_id,)
    assert not replayed.requires_manual_review
    summary = funnel_summary([disposition_for_decision(row, replayed)], extracted_row_count=1)
    assert summary["disposition_counts"]["MATCHED"] == 1
    assert summary["disposition_counts"]["MANUAL_REVIEW"] == 0


def test_exact_replay_survives_independent_private_job_directories(tmp_path: Path) -> None:
    first_job = tmp_path / "private-job-a" / "sources"
    second_job = tmp_path / "private-job-b" / "sources"
    first_job.mkdir(parents=True)
    second_job.mkdir(parents=True)
    for directory in (first_job, second_job):
        (directory / "nested").mkdir()
        (directory / "nested" / "book.xlsx").write_bytes(b"same workbook bytes")

    [first_entry] = scan_directory(first_job)
    [second_entry] = scan_directory(second_job)
    first_row = _row(
        row_id=stable_id(first_entry.file_id, "Sheet", 4),
        location=DrawingSourceLocation(first_entry.file_id, "book.xlsx", "Sheet", 4, ("A4",)),
    )
    second_row = _row(
        row_id=stable_id(second_entry.file_id, "Sheet", 4),
        location=DrawingSourceLocation(second_entry.file_id, "book.xlsx", "Sheet", 4, ("A4",)),
    )
    decision = _decision()
    first_context = _context(first_row, decision)
    second_context = _context(second_row, decision)

    assert first_entry.file_id == second_entry.file_id
    assert first_context == second_context
    assert first_context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    entry = _entry(first_context)
    store.append_page((entry,))

    replayed = _replay(store, second_row, decision)

    assert replayed is not None
    assert replayed.evidence_ids == (entry.event_id,)


def test_exact_replay_survives_reversed_direct_file_upload_order(tmp_path: Path) -> None:
    first_job = tmp_path / "private-job-a"
    second_job = tmp_path / "private-job-b"
    first_job.mkdir()
    second_job.mkdir()
    first_paths = (
        first_job / "01-drawing-a.xlsx",
        first_job / "02-drawing-b.xlsx",
    )
    second_paths = (
        second_job / "01-drawing-b.xlsx",
        second_job / "02-drawing-a.xlsx",
    )
    for path, content in zip(first_paths, (b"drawing a", b"drawing b"), strict=True):
        path.write_bytes(content)
    for path, content in zip(second_paths, (b"drawing b", b"drawing a"), strict=True):
        path.write_bytes(content)

    first_entries = [scan_file(path)[0] for path in first_paths]
    second_entries = [scan_file(path)[0] for path in second_paths]
    first_rows = [
        _row(
            row_id=stable_id(entry.file_id, "Sheet", 4),
            location=DrawingSourceLocation(entry.file_id, entry.filename, "Sheet", 4, ("A4",)),
        )
        for entry in first_entries
    ]
    second_rows = [
        _row(
            row_id=stable_id(entry.file_id, "Sheet", 4),
            location=DrawingSourceLocation(entry.file_id, entry.filename, "Sheet", 4, ("A4",)),
        )
        for entry in second_entries
    ]
    decision = _decision()
    first_contexts = [_context(row, decision) for row in first_rows]
    second_contexts = [_context(row, decision) for row in second_rows]

    assert first_entries[0].file_id == second_entries[1].file_id
    assert first_entries[1].file_id == second_entries[0].file_id
    assert first_contexts[0] == second_contexts[1]
    assert first_contexts[1] == second_contexts[0]
    assert all(context is not None for context in first_contexts)
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page(tuple(_entry(context) for context in first_contexts if context is not None))

    replayed = [_replay(store, row, decision) for row in second_rows]

    assert all(item is not None for item in replayed)


@pytest.mark.parametrize(
    "change",
    [
        {"tenant_id": "other"},
        {"project_id": "other"},
        {"input_hashes": ("b" * 64,)},
        {"model_version": "model-2"},
        {"rules_version": "rules-2"},
    ],
)
def test_scope_supplied_contract_hash_and_version_changes_do_not_replay(
    tmp_path: Path, change: dict[str, object]
) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page((_entry(context),))
    assert _replay(store, row, decision, **change) is None


def test_workflow_accepts_only_complete_supplied_replay_hashes() -> None:
    request = WorkflowRequest(
        inputs=(Path(__file__),),
        dry_run=True,
        feedback_input_hashes=("a" * 64, "b" * 64),
    )
    _validate_request(request)
    with pytest.raises(ValueError, match="feedback_input_hashes"):
        _validate_request(
            WorkflowRequest(
                inputs=(Path(__file__),),
                dry_run=True,
                feedback_input_hashes=("contract-workbook",),
            )
        )


@pytest.mark.parametrize(
    "row_change,decision_change",
    [
        ({"work_name_raw": "Монтаж другого кабеля"}, {}),
        ({"position_code_raw": "2.1"}, {}),
        ({"object_index_raw": "1002"}, {}),
        ({"drawing_code_raw": "D-2"}, {}),
        ({"cost_type_code_raw": "material"}, {}),
        ({"unit_raw": "шт"}, {}),
        ({}, {"matching_strategy": "semantic_suggestion"}),
        ({}, {"category": TargetWorkCategory.CONCRETE_WORKS}),
        ({}, {"quantity_decision": "exclude", "cost_decision": "include"}),
        ({"row_id": "row-2"}, {"row_id": "row-2"}),
    ],
)
def test_every_row_context_dimension_is_exact(
    tmp_path: Path, row_change: dict[str, object], decision_change: dict[str, object]
) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page((_entry(context),))
    assert _replay(store, _row(**row_change), _decision(**decision_change)) is None


def test_formula_or_excel_hazards_remain_in_manual_review(tmp_path: Path) -> None:
    row = _row(warnings=("FORMULA_WITHOUT_CACHED_VALUE",))
    decision = _decision()
    clean_context = _context(_row(), decision)
    assert clean_context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page((_entry(clean_context),))

    assert _replay(store, row, decision) is None
    assert disposition_for_decision(row, decision).disposition == "MANUAL_REVIEW"


def test_categoryless_and_missing_position_candidates_can_match_exactly(tmp_path: Path) -> None:
    row = _row(position_code_raw=None)
    decision = _decision(category=None)
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page((_entry(context),))

    replayed = _replay(store, row, decision)

    assert replayed is not None
    assert replayed.category is TargetWorkCategory.LOW_CURRENT_CABLE


def test_explicit_review_resolution_replays_exactly(tmp_path: Path) -> None:
    row = _row()
    ambiguous = _decision(quantity_decision="review", cost_decision="review")
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    context = _context(row, ambiguous, allow_review=True)
    assert context is not None
    store.append_page(
        (
            _entry(
                context,
                selected_quantity_resolution="include",
                selected_cost_resolution="exclude",
            ),
        )
    )

    replayed = _replay(store, row, ambiguous)

    assert replayed is not None
    assert replayed.quantity_decision == "include"
    assert replayed.cost_decision == "exclude"
    assert not replayed.requires_manual_review


def test_similar_text_and_exclusion_replay_are_not_approximate(tmp_path: Path) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    store.append_page((_entry(context, action="exclude", selected_category=None),))

    assert _replay(store, _row(work_name_raw="Монтаж кабеля усиленный"), decision) is None
    replayed = _replay(store, row, decision)
    assert replayed is not None
    assert replayed.category is None
    assert replayed.quantity_decision == replayed.cost_decision == "exclude"


def test_replay_uses_newer_decision_after_an_older_event_is_invalidated(tmp_path: Path) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    older = _entry(context, selected_category=TargetWorkCategory.POWER_CABLE.value)
    newer = _entry(
        context,
        selected_category=TargetWorkCategory.LOW_CURRENT_CABLE.value,
        created_at="2026-08-06T01:02:04Z",
    )
    store.append_page((older, newer))
    store.invalidate(older.event_id, "auditor", "2026-08-06T01:03:00Z", "old source")

    replayed = _replay(store, row, decision)

    assert replayed is not None
    assert replayed.category is TargetWorkCategory.LOW_CURRENT_CABLE


def test_replay_misses_when_the_current_decision_is_invalidated(tmp_path: Path) -> None:
    row = _row()
    decision = _decision()
    context = _context(row, decision)
    assert context is not None
    store = FeedbackStore(tmp_path / "feedback.jsonl")
    entry = _entry(context)
    store.append_page((entry,))
    store.invalidate(entry.event_id, "auditor", "2026-08-06T01:03:00Z", "current source")

    assert _replay(store, row, decision) is None

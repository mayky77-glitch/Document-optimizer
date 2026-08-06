"""Lifecycle hooks are deterministic and keep cancellation fail-closed."""

from __future__ import annotations

from pathlib import Path
from shutil import copyfile

import pytest

from report_processor.drawing_card.lifecycle import (
    DrawingCardLifecycle,
    DrawingCardLifecyclePhase,
    DrawingCardWorkflowCancelled,
)
from report_processor.drawing_card.models import WorkflowRequest, WorkflowResult
from report_processor.drawing_card.statuses import Status
from report_processor.drawing_card.workflow import (
    _check_cancelled,
    _is_publishable_result,
    run_workflow,
)


def test_lifecycle_emits_immutable_bounded_utc_progress() -> None:
    received = []
    lifecycle = DrawingCardLifecycle(received.append)

    progress = lifecycle.emit(
        DrawingCardLifecyclePhase.EXTRACTION,
        processed_files=2,
        total_files=3,
        processed_rows=5,
    )

    assert received == [progress]
    assert progress.phase is DrawingCardLifecyclePhase.EXTRACTION
    assert progress.started_at.endswith("Z")
    assert progress.updated_at.endswith("Z")
    assert progress.total_rows is None
    assert lifecycle.last == progress


def test_lifecycle_rejects_unbounded_counter_values() -> None:
    lifecycle = DrawingCardLifecycle()

    with pytest.raises(ValueError, match="bounded"):
        lifecycle.emit(DrawingCardLifecyclePhase.MATCHING, processed_rows=3, total_rows=2)


def test_cancelled_request_stops_before_request_validation(tmp_path: Path) -> None:
    events = []
    previous_output = tmp_path / "previous-result.xlsx"
    previous_output.write_bytes(b"previous")
    request = WorkflowRequest(
        inputs=(tmp_path / "missing.xlsx",),
        output=previous_output,
        work_dir=tmp_path / "work",
        cancel_requested=lambda: True,
        progress_callback=events.append,
    )

    with pytest.raises(DrawingCardWorkflowCancelled):
        run_workflow(request)

    assert [event.phase for event in events] == [DrawingCardLifecyclePhase.UPLOAD]
    assert previous_output.read_bytes() == b"previous"


def test_cancellation_removes_output_before_it_can_be_published(tmp_path: Path) -> None:
    output = tmp_path / "partial.xlsx"
    output.write_bytes(b"partial")
    request = WorkflowRequest(cancel_requested=lambda: True)

    with pytest.raises(DrawingCardWorkflowCancelled):
        _check_cancelled(request, output)

    assert not output.exists()


def test_request_defaults_preserve_synchronous_callers() -> None:
    request = WorkflowRequest()

    assert request.progress_callback is None
    assert request.cancel_requested is None


def test_validated_partially_ready_output_is_publishable() -> None:
    result = WorkflowResult(
        run_id="run-1",
        status=Status.PARTIALLY_READY,
        work_dir=Path("work/run-1"),
        output_path=Path("output.xlsx"),
    )

    assert _is_publishable_result(result, {"status": Status.OK}, inputs_unchanged=True)
    assert not _is_publishable_result(result, {"status": Status.OK}, inputs_unchanged=False)


def test_multi_file_lifecycle_is_monotonic_and_blocked_result_is_not_ready(
    tmp_path: Path,
) -> None:
    fixture_dir = Path(__file__).parents[2] / "fixtures" / "drawing_card"
    first_source = tmp_path / "first.xlsx"
    second_source = tmp_path / "second.xlsx"
    copyfile(fixture_dir / "demo_source.xlsx", first_source)
    copyfile(fixture_dir / "demo_source.xlsx", second_source)
    events = []

    result = run_workflow(
        WorkflowRequest(
            inputs=(first_source, second_source),
            template=fixture_dir / "default_template.xlsx",
            output=tmp_path / "output.xlsx",
            strict=False,
            work_dir=tmp_path / "work",
            progress_callback=events.append,
        )
    )

    phase_order = tuple(DrawingCardLifecyclePhase)
    phase_indexes = [phase_order.index(event.phase) for event in events]
    assert phase_indexes == sorted(phase_indexes)
    assert result.status == "BLOCKED"
    assert DrawingCardLifecyclePhase.READY not in [event.phase for event in events]
    assert events[-1].phase is DrawingCardLifecyclePhase.REVIEW_PREPARATION
    assert events[-1].terminal_cause == "BLOCKED"

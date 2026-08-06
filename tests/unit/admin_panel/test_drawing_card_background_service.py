"""Lifecycle contracts for the background drawing-card service mode."""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
from report_processor.drawing_card.models import WorkflowResult
from report_processor.drawing_card.review.inline import review_approval
from report_processor.drawing_card.statuses import Status


def _fixture() -> bytes:
    path = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    return path.read_bytes()


def _wait_for(service: DrawingCardService, job_id: str, *statuses: str) -> object:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = service.get_job(job_id)
        if job.status in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {statuses}")


def test_background_create_is_idempotent_and_persists_validated_attempt(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def runner(request):
        nonlocal calls
        calls += 1
        started.set()
        release.wait(2)
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult(
            run_id="done",
            status=Status.OK,
            work_dir=run_dir,
            output_path=request.output,
            extracted_row_count=3,
        )

    service = DrawingCardService(tmp_path / "private", runner=runner, background=True)
    first = service.create_job(
        sources=[("source.xlsx", _fixture())], idempotency_key="request-key-0001"
    )
    assert first.status in {"queued", "processing"}
    assert started.wait(1)
    duplicate = service.create_job(
        sources=[("source.xlsx", _fixture())], background=True, idempotency_key="request-key-0001"
    )
    assert duplicate is first
    assert calls == 1
    release.set()
    finished = _wait_for(service, first.job_id, "ready")
    assert finished.attempt == 1
    assert finished.result is not None
    assert finished.result.relative_to(finished.directory).as_posix().startswith("attempts/0001/")

    recovered = DrawingCardService(tmp_path / "private", runner=runner, background=True)
    restored = recovered.get_job(first.job_id)
    assert restored.status == "ready"
    assert restored.result_available
    assert restored.summary["extracted_rows"] == 3

    with pytest.raises(ValueError, match="idempotency key conflicts"):
        recovered.create_job(
            sources=[("source.xlsx", _fixture() + b"different")],
            idempotency_key="request-key-0001",
        )


def test_cancelled_background_job_removes_current_partial_output(tmp_path: Path) -> None:
    began = threading.Event()

    def runner(request):
        assert request.output is not None
        request.output.write_bytes(b"partial")
        began.set()
        while not request.cancel_requested():
            time.sleep(0.01)
        from report_processor.drawing_card.lifecycle import DrawingCardWorkflowCancelled

        raise DrawingCardWorkflowCancelled()

    service = DrawingCardService(tmp_path / "private", runner=runner, background=True)
    job = service.create_job(sources=[("source.xlsx", _fixture())])
    assert began.wait(1)
    service.cancel_job(job.job_id)
    cancelled = _wait_for(service, job.job_id, "cancelled")
    assert cancelled.terminal_cause == "cancelled"
    assert not (cancelled.directory / "attempts" / "0001" / "drawing-card.xlsx").exists()


def test_restart_restores_accepted_inline_decisions_without_row_values(tmp_path: Path) -> None:
    workspace = tmp_path / "private"
    service = DrawingCardService(workspace)
    directory = workspace / "review-state"
    source = directory / "sources" / "01-source.xlsx"
    source.parent.mkdir(parents=True)
    source.write_bytes(_fixture())
    job = DrawingCardJob(
        job_id="review-state",
        directory=directory,
        sources=(source,),
        source_hashes=(hashlib.sha256(source.read_bytes()).hexdigest(),),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        started_at="2026-08-06T00:00:00Z",
        updated_at="2026-08-06T00:00:00Z",
        review_items={"row-1": {"review_id": "row-1"}},
    )
    service._jobs[job.job_id] = job
    service.put_review_item(
        job_id=job.job_id,
        review_id="row-1",
        action="approve",
        category="power_cable",
    )

    recovered = DrawingCardService(workspace)
    restored = recovered.get_job(job.job_id)
    assert restored.inline_approvals == {
        "row-1": review_approval("row-1", "approve", "power_cable")
    }
    manifest = (directory / "job-manifest.json").read_text(encoding="utf-8")
    assert "source.xlsx" in manifest
    assert "row-1" in manifest
    assert "наименование" not in manifest


def test_review_state_is_rebuilt_after_background_restart(tmp_path: Path) -> None:
    def runner(request):
        run_dir = request.work_dir / "review"
        run_dir.mkdir(parents=True)
        (run_dir / "manual_review.xlsx").write_bytes(b"PK\x03\x04review")
        from report_processor.drawing_card.models import (
            DrawingSourceLocation,
            DrawingSourceRow,
            MatchDecision,
            TargetWorkCategory,
        )

        row = DrawingSourceRow(
            row_id="stable-row",
            location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 1, ("A1",)),
            object_index_raw="1",
            drawing_code_raw="A",
            work_name_raw="Монтаж кабеля",
            unit_raw="м",
            remaining_quantity=None,
            remaining_total_cost=None,
            formula_values=(),
            cached_values=(),
            source_document_type="ks6a",
            source_period=None,
            source_revision=None,
            status=Status.OK,
            warnings=(),
        )
        decision = MatchDecision(
            "stable-row",
            TargetWorkCategory.POWER_CABLE,
            "review",
            "review",
            None,
            None,
            0.5,
            0.5,
            "manual",
            (),
            "review",
            True,
            Status.OK,
            (),
        )
        return WorkflowResult(
            run_id="review",
            status="BLOCKED",
            work_dir=run_dir,
            source_rows=[row],
            decisions=[decision],
            category_units={"power_cable": ("м",)},
            manual_review_count=1,
        )

    workspace = tmp_path / "private"
    original = DrawingCardService(workspace, runner=runner)
    job = original.create_job(sources=[("source.xlsx", _fixture())])
    assert job.status == "review_required"
    original.put_review_item(
        job_id=job.job_id, review_id="stable-row", action="approve", category="power_cable"
    )
    recovered = DrawingCardService(workspace, runner=runner, background=True)
    restored = _wait_for(recovered, job.job_id, "review_required")
    assert set(restored.review_items) == {"stable-row"}
    assert set(restored.inline_approvals) == {"stable-row"}
    assert recovered.list_review_clusters(job_id=job.job_id)["total_clusters"] == 1


def test_review_mutation_rolls_back_if_manifest_write_fails(tmp_path: Path, monkeypatch) -> None:
    service = DrawingCardService(tmp_path / "private")
    directory = service.workspace_root / "atomic-review"
    directory.mkdir()
    job = DrawingCardJob(
        job_id="atomic-review",
        directory=directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        review_items={"row": {"review_id": "row"}},
    )
    service._jobs[job.job_id] = job
    monkeypatch.setattr(
        service._store, "save", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    with pytest.raises(Exception, match="state was not saved"):
        service.put_review_item(job_id=job.job_id, review_id="row", action="reject")
    assert job.inline_approvals == {}


def test_retry_uses_a_new_isolated_attempt_directory(tmp_path: Path) -> None:
    attempts: list[Path] = []

    def runner(request):
        attempts.append(request.work_dir.parent)
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        if len(attempts) == 1:
            return WorkflowResult(run_id="failed", status="FAILED", work_dir=run_dir)
        assert request.review_decisions is not None
        assert request.review_decisions.is_file()
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        return WorkflowResult(
            run_id="ready", status=Status.OK, work_dir=run_dir, output_path=request.output
        )

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = service.create_job(sources=[("source.xlsx", _fixture())])
    assert job.status == "failed"
    job.inline_approvals = {"stable-row": review_approval("stable-row", "reject", None)}
    retried = service.retry_job(job.job_id)
    assert retried.status == "ready"
    assert [path.name for path in attempts] == ["0001", "0002"]
    assert all(path.is_dir() for path in attempts)


@pytest.mark.parametrize(("terminal", "expected"), [("BLOCKED", "blocked"), (Status.OK, "ok")])
def test_progress_terminal_cause_is_retained_for_a_ready_job(
    tmp_path: Path, terminal: object, expected: str
) -> None:
    def runner(request):
        from report_processor.drawing_card.lifecycle import (
            DrawingCardLifecyclePhase,
            DrawingCardProgress,
        )

        assert request.progress_callback is not None
        request.progress_callback(
            DrawingCardProgress(
                phase=DrawingCardLifecyclePhase.READY,
                terminal_cause=terminal,
                started_at="2026-08-06T00:00:00Z",
                updated_at="2026-08-06T00:00:01Z",
            )
        )
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult(
            run_id="done", status=Status.OK, work_dir=run_dir, output_path=request.output
        )

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = service.create_job(sources=[("source.xlsx", _fixture())])
    assert job.status == "ready"
    assert job.terminal_cause == expected
    assert job.phase == "ready"

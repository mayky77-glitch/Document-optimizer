from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from threading import Event

import pytest

from report_processor.admin_panel.drawing_card_service import (
    DrawingCardJob,
    DrawingCardPersistenceError,
    DrawingCardService,
)
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
    WorkflowResult,
)
from report_processor.drawing_card.review.inline import review_approval
from report_processor.drawing_card.statuses import Status


def _review_job(service: DrawingCardService) -> DrawingCardJob:
    directory = service.workspace_root / "review-job"
    directory.mkdir()
    row = DrawingSourceRow(
        row_id="review-row",
        location=DrawingSourceLocation("source", "safe.xlsx", "Лист1", 7, ("A7",)),
        object_index_raw="1001",
        drawing_code_raw="D-1",
        work_name_raw="Монтаж кабеля",
        unit_raw="м",
        remaining_quantity=Decimal("2"),
        remaining_total_cost=Decimal("10"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )
    decision = MatchDecision(
        row_id=row.row_id,
        category=TargetWorkCategory.POWER_CABLE,
        quantity_decision="review",
        cost_decision="review",
        quantity_rule_id=None,
        cost_rule_id=None,
        quantity_confidence=0.5,
        cost_confidence=0.5,
        matching_strategy="manual_review",
        evidence_ids=(),
        reason="manual",
        requires_manual_review=True,
        status=Status.OK,
        warnings=(),
    )
    job = DrawingCardJob(
        job_id="review-job",
        directory=directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        feedback_project_id="project",
        feedback_rules_version="rules",
        feedback_input_hashes=("a" * 64,),
        review_items={row.row_id: {"review_id": row.row_id}},
        review_rows={row.row_id: row},
        review_decisions={row.row_id: decision},
        inline_approvals={
            row.row_id: review_approval(row.row_id, "approve", TargetWorkCategory.POWER_CABLE.value)
        },
    )
    service._jobs[job.job_id] = job
    return job


def test_feedback_ledger_failure_does_not_schedule_rerun(tmp_path: Path) -> None:
    calls = []

    def runner(request):
        calls.append(request)
        raise AssertionError("runner must not be called after feedback failure")

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = _review_job(service)
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")
    (service.workspace_root / "review-feedback-v2.jsonl").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        service.apply_inline_review(job_id=job.job_id)

    assert calls == []
    assert job.inline_approvals


def test_concurrent_page_apply_runs_the_review_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DrawingCardService(tmp_path / "private")
    job = _review_job(service)
    entered = Event()
    release = Event()
    calls: list[Path | None] = []

    def fake_run(
        current: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ) -> DrawingCardJob:
        assert strict is True
        calls.append(review_decisions)
        entered.set()
        assert release.wait(2)
        current.status = "ready"
        return current

    monkeypatch.setattr(service, "_run", fake_run)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(service.apply_inline_review, job_id=job.job_id)
        assert entered.wait(2)
        second = executor.submit(service.apply_inline_review, job_id=job.job_id)
        release.set()

        assert first.result(timeout=2).status == "ready"
        with pytest.raises(ValueError, match="unresolved review items"):
            second.result(timeout=2)

    assert len(calls) == 1
    assert (service.workspace_root / "review-feedback-v2.jsonl").read_text(encoding="utf-8").count(
        "\n"
    ) == 1


def test_workbook_and_inline_apply_share_one_review_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DrawingCardService(tmp_path / "private")
    job = _review_job(service)
    entered = Event()
    release = Event()
    calls: list[Path | None] = []

    def fake_run(
        current: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ) -> DrawingCardJob:
        assert strict is True
        calls.append(review_decisions)
        entered.set()
        assert release.wait(2)
        current.status = "ready"
        return current

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(
        "report_processor.admin_panel.drawing_card_service._validate_review", lambda *_args: None
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.drawing_card_service.import_review_approvals",
        lambda _path: (),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        inline = executor.submit(service.apply_inline_review, job_id=job.job_id)
        assert entered.wait(2)
        workbook = executor.submit(
            service.apply_review,
            job_id=job.job_id,
            review_name="completed_review.xlsx",
            review_content=b"workbook review",
        )
        release.set()

        assert inline.result(timeout=2).status == "ready"
        with pytest.raises(ValueError, match="does not await manual review"):
            workbook.result(timeout=2)

    assert len(calls) == 1


@pytest.mark.parametrize("first_apply", ("inline", "workbook"))
def test_queued_apply_cannot_consume_the_next_review_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_apply: str
) -> None:
    service = DrawingCardService(tmp_path / "private")
    job = _review_job(service)
    entered = Event()
    release = Event()
    calls: list[Path | None] = []

    def fake_run(
        current: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ) -> DrawingCardJob:
        assert strict is True
        calls.append(review_decisions)
        entered.set()
        assert release.wait(2)
        # The first rerun produces a new review page.  Keep the old choices in
        # memory to prove the queued caller is rejected by its old claim, not
        # merely by unresolved-item validation.
        current.status = "review_required"
        current.review_generation = "next-generation"
        return current

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(
        "report_processor.admin_panel.drawing_card_service._validate_review", lambda *_args: None
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.drawing_card_service.import_review_approvals",
        lambda _path: (),
    )

    def apply_inline() -> DrawingCardJob:
        return service.apply_inline_review(job_id=job.job_id)

    def apply_workbook() -> DrawingCardJob:
        return service.apply_review(
            job_id=job.job_id,
            review_name="completed_review.xlsx",
            review_content=b"workbook review",
        )

    first, second = (
        (apply_inline, apply_workbook)
        if first_apply == "inline"
        else (apply_workbook, apply_inline)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(first)
        assert entered.wait(2)
        second_future = executor.submit(second)
        release.set()

        assert first_future.result(timeout=2).status == "review_required"
        with pytest.raises(ValueError, match="review generation was already applied"):
            second_future.result(timeout=2)

    assert len(calls) == 1


def test_failed_initial_rerun_manifest_save_restores_retryable_review_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def runner(request) -> WorkflowResult:
        calls.append(request)
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "ready"
        run_dir.mkdir(parents=True)
        return WorkflowResult("ready", Status.OK, run_dir, output_path=request.output)

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = _review_job(service)
    persist = service._persist_job
    save_count = 0

    def fail_second_save(current: DrawingCardJob) -> None:
        nonlocal save_count
        save_count += 1
        if save_count == 2:
            raise DrawingCardPersistenceError("initial rerun state unavailable")
        persist(current)

    monkeypatch.setattr(service, "_persist_job", fail_second_save)

    with pytest.raises(DrawingCardPersistenceError, match="initial rerun state unavailable"):
        service.apply_inline_review(job_id=job.job_id)

    assert calls == []
    assert job.status == "review_required"
    assert job.run_count == 0
    assert job.attempt == 0
    assert set(job.inline_approvals) == {"review-row"}
    assert (service.workspace_root / "review-feedback-v2.jsonl").read_text(encoding="utf-8").count(
        "\n"
    ) == 1

    monkeypatch.setattr(service, "_persist_job", persist)
    assert service.apply_inline_review(job_id=job.job_id).status == "ready"
    assert len(calls) == 1


def test_confirmed_page_remains_saved_when_manifest_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def runner(request: object) -> None:
        calls.append(request)

    service = DrawingCardService(tmp_path / "private", runner=runner)
    job = _review_job(service)

    def fail_manifest(_job: DrawingCardJob) -> None:
        raise DrawingCardPersistenceError("manifest unavailable")

    monkeypatch.setattr(service, "_persist_job", fail_manifest)

    with pytest.raises(DrawingCardPersistenceError, match="manifest unavailable"):
        service.apply_inline_review(job_id=job.job_id)

    assert calls == []
    assert set(job.inline_approvals) == {"review-row"}
    assert (service.workspace_root / "review-feedback-v2.jsonl").read_text(encoding="utf-8").count(
        "\n"
    ) == 1


def test_stale_membership_version_and_context_bounds_are_rejected(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private")
    job = _review_job(service)

    with pytest.raises(ValueError, match="stale membership"):
        service.put_review_item(
            job_id=job.job_id,
            review_id="review-row",
            action="approve",
            category=TargetWorkCategory.POWER_CABLE.value,
            version="obsolete",
        )
    with pytest.raises(ValueError, match="between 1 and 5"):
        service.get_review_context(job_id=job.job_id, review_id="review-row", radius=0)


def test_restart_rebuilds_selected_packet_without_publishing_before_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DrawingCardService(tmp_path / "private", background=True)
    job = _review_job(service)
    row = replace(job.review_rows["review-row"], row_id="review-row-2")
    decision = replace(job.review_decisions["review-row"], row_id=row.row_id)
    job.review_rows[row.row_id] = row
    job.review_decisions[row.row_id] = decision
    job.review_items[row.row_id] = {"review_id": row.row_id}
    job.inline_approvals[row.row_id] = review_approval(
        row.row_id, "approve", TargetWorkCategory.POWER_CABLE.value
    )
    cluster = service._current_clusters(job)[0]
    job.cluster_actions = {cluster.cluster_id: dict(job.inline_approvals)}
    completed = Event()
    seen: list[Path | None] = []

    def fake_run(
        current: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ):
        seen.append(review_decisions)
        current.status = "review_required"
        current.inline_approvals = {}
        current.cluster_actions = {}
        completed.set()
        return current

    monkeypatch.setattr(service, "_run", fake_run)
    service._schedule_review_recovery(job)

    assert completed.wait(2)
    assert seen == [None]
    assert job.status == "review_required"
    assert set(job.inline_approvals) == {"review-row", "review-row-2"}
    assert job.cluster_actions == {cluster.cluster_id: dict(job.inline_approvals)}
    assert not (service.workspace_root / "review-feedback-v2.jsonl").exists()

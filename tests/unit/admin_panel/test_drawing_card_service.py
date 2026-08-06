"""Regression checks for the drawing-card service beside the existing admin service."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import pytest

import report_processor.admin_panel.drawing_card_service as drawing_card_service
from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
    WorkflowResult,
)
from report_processor.drawing_card.review.inline import review_approval
from report_processor.drawing_card.statuses import Status
from report_processor.drawing_card.workflow import run_workflow


@pytest.mark.parametrize(
    "workflow_status", (Status.COMPLETED_WITH_WARNINGS, Status.PARTIALLY_READY)
)
def test_validated_warning_output_is_available_after_review(
    tmp_path: Path, workflow_status: Status
) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request):
        run_dir = request.work_dir / "warning-output"
        run_dir.mkdir(parents=True)
        assert request.output is not None
        request.output.write_bytes(b"validated output")
        return WorkflowResult(
            run_id="warning-output",
            status=workflow_status,
            work_dir=run_dir,
            output_path=request.output,
        )

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])

    assert job.status == "ready"
    assert job.result_available is True


@pytest.mark.parametrize(
    "hostile_path",
    ("sources/01-source.xlsx", "attempts/0000/drawing-card.xlsx"),
)
def test_restore_rejects_ready_manifest_that_points_to_source_or_old_attempt(
    tmp_path: Path,
    hostile_path: str,
) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request):
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult("done", Status.OK, run_dir, output_path=request.output)

    workspace = tmp_path / "private-workspaces"
    service = DrawingCardService(workspace, runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    candidate = job.directory / hostile_path
    if not candidate.exists():
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(b"PK\x03\x04old-result")
    manifest = service._manifest_for(job)
    manifest["result_path"] = hostile_path
    manifest["result_hash"] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    service._store.save(job.job_id, manifest)

    restored = DrawingCardService(workspace, runner=runner)
    with pytest.raises(KeyError):
        restored.get_job(job.job_id)


def test_restore_rejects_symlinked_attempt_component_for_ready_result(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request):
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult("done", Status.OK, run_dir, output_path=request.output)

    workspace = tmp_path / "private-workspaces"
    service = DrawingCardService(workspace, runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    attempts = job.directory / "attempts"
    relocated = job.directory / "relocated-attempts"
    attempts.rename(relocated)
    attempts.symlink_to(relocated, target_is_directory=True)

    restored = DrawingCardService(workspace, runner=runner)
    with pytest.raises(KeyError):
        restored.get_job(job.job_id)


def test_canonical_result_accepts_macos_var_alias(tmp_path: Path) -> None:
    if not str(tmp_path).startswith("/private/var/"):
        pytest.skip("macOS /var alias is unavailable")
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request):
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult("done", Status.OK, run_dir, output_path=request.output)

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    assert job.result is not None
    alias = Path(str(job.result).replace("/private/var/", "/var/", 1))

    assert drawing_card_service._is_canonical_attempt_result(alias, job)


def test_restore_rejects_review_manifest_that_points_to_a_source(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request):
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        (run_dir / "manual_review.xlsx").write_bytes(b"PK\x03\x04review")
        return WorkflowResult("done", "BLOCKED", run_dir, manual_review_count=1)

    workspace = tmp_path / "private-workspaces"
    service = DrawingCardService(workspace, runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    assert job.status == "review_required"
    manifest = service._manifest_for(job)
    manifest["review_path"] = "sources/01-source.xlsx"
    service._store.save(job.job_id, manifest)

    restored = DrawingCardService(workspace, runner=runner)
    with pytest.raises(KeyError):
        restored.get_job(job.job_id)


def test_update_existing_card_tampering_fails_before_publication(tmp_path: Path) -> None:
    fixture_dir = Path(__file__).parents[2] / "fixtures" / "drawing_card"

    def runner(request):
        assert request.existing_card is not None
        request.existing_card.write_bytes(b"PK\x03\x04tampered")
        assert request.output is not None
        request.output.write_bytes(b"PK\x03\x04result")
        run_dir = request.work_dir / "done"
        run_dir.mkdir(parents=True)
        return WorkflowResult("done", Status.OK, run_dir, output_path=request.output)

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(
        sources=[("source.xlsx", (fixture_dir / "demo_source.xlsx").read_bytes())],
        mode="update",
        existing_name="existing.xlsx",
        existing_content=(fixture_dir / "default_template.xlsx").read_bytes(),
    )

    assert job.status == "failed"
    assert job.errors == ("EXISTING_CARD_HASH_CHANGED",)
    assert job.result is None


def test_unknown_drawing_card_job_is_not_resolved_as_a_workspace_path(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")

    with pytest.raises(KeyError):
        service.get_job("../../private-workspaces")
    with pytest.raises(KeyError):
        service.get_result("../../private-workspaces")
    with pytest.raises(KeyError):
        service.get_review("../../private-workspaces")


@pytest.mark.parametrize(
    ("period", "expected_period"),
    (("июль 2026", "2026-07"), ("2026-07", "2026-07")),
)
def test_injected_runner_preserves_source_basename_with_semantic_rag(
    tmp_path: Path, period: str, expected_period: str
) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    seen = []

    def runner(request):
        seen.append(request)
        return run_workflow(request)

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(
        sources=[("0906_demo_input.xlsx", fixture.read_bytes())], period=period
    )

    assert len(seen) == 1
    assert seen[0].rag_mode == "semantic"
    assert seen[0].inputs[0].name == "01-0906_demo_input.xlsx"
    assert seen[0].inputs[0].read_bytes() == fixture.read_bytes()
    assert seen[0].inputs[0].resolve() != fixture.resolve()
    assert job.period == expected_period
    assert seen[0].period == expected_period
    assert str(tmp_path) not in str(drawing_card_job_payload(job))


def test_category_change_updates_the_review_target_unit_from_the_selected_category(
    tmp_path: Path,
) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    job_directory = service.workspace_root / "review-job"
    job_directory.mkdir()
    job = DrawingCardJob(
        job_id="review-job",
        directory=job_directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        category_units={
            "low_current_cable": ("м",),
            "concrete_works": ("м3", "м³"),
        },
        review_items={
            "row-1": {
                "review_id": "row-1",
                "предлагаемая_категория": "low_current_cable",
                "предлагаемая_категория_id": "low_current_cable",
                "source_unit": "м",
                "target_unit": "м",
            }
        },
    )
    service._jobs[job.job_id] = job

    service.put_review_item(
        job_id=job.job_id,
        review_id="row-1",
        action="change_category",
        category="concrete_works",
    )
    page = service.list_review_items(job_id=job.job_id)

    assert page["items"] == [
        {
            "review_id": "row-1",
            "предлагаемая_категория": "low_current_cable",
            "предлагаемая_категория_id": "low_current_cable",
            "source_unit": "м",
            "target_unit": "м3",
            "решение": {"action": "change_category", "category": "concrete_works"},
        }
    ]


def test_cluster_fanout_undo_and_stale_identity_are_all_or_nothing(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    directory = service.workspace_root / "cluster-job"
    directory.mkdir()
    rows = {
        row_id: DrawingSourceRow(
            row_id=row_id,
            location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
            object_index_raw="1006",
            drawing_code_raw="А-001",
            work_name_raw="Монтаж кабеля",
            unit_raw="м",
            remaining_quantity=Decimal("1"),
            remaining_total_cost=Decimal("2"),
            formula_values=(),
            cached_values=(),
            source_document_type="ks6a",
            source_period=None,
            source_revision=None,
            status=Status.OK,
            warnings=(),
        )
        for row_id in ("row-a", "row-b")
    }
    decisions = {
        row_id: MatchDecision(
            row_id,
            TargetWorkCategory.LOW_CURRENT_CABLE,
            "review",
            "review",
            None,
            None,
            0.7,
            0.7,
            "manual_review",
            (),
            "review",
            True,
            Status.OK,
            (),
        )
        for row_id in rows
    }
    job = DrawingCardJob(
        job_id="cluster-job",
        directory=directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        category_units={"low_current_cable": ("м",)},
        review_items={row_id: {"review_id": row_id} for row_id in rows},
        review_rows=rows,
        review_decisions=decisions,
    )
    service._jobs[job.job_id] = job
    cluster = service.list_review_clusters(job_id=job.job_id)["items"][0]

    assert cluster["aggregate_total_cost"] == "4"
    assert cluster["members"] == [
        {
            "review_id": "row-a",
            "work_name": "Монтаж кабеля",
            "source_unit": "м",
            "quantity": "1",
            "total_cost": "2",
        },
        {
            "review_id": "row-b",
            "work_name": "Монтаж кабеля",
            "source_unit": "м",
            "quantity": "1",
            "total_cost": "2",
        },
    ]
    service.put_review_cluster(
        job_id=job.job_id,
        cluster_id=cluster["cluster_id"],
        version=cluster["version"],
        action="approve",
        category="low_current_cable",
    )
    assert set(job.inline_approvals) == {"row-a", "row-b"}
    with pytest.raises(ValueError, match="stale cluster identity"):
        service.put_review_cluster(
            job_id=job.job_id,
            cluster_id=cluster["cluster_id"],
            version="obsolete",
            action="reject",
        )
    assert set(job.inline_approvals) == {"row-a", "row-b"}

    service.undo_review_cluster(
        job_id=job.job_id, cluster_id=cluster["cluster_id"], version=cluster["version"]
    )
    assert job.inline_approvals == {}


def test_cluster_payload_uses_null_aggregate_when_every_member_cost_is_absent(
    tmp_path: Path,
) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    directory = service.workspace_root / "empty-cost-cluster-job"
    directory.mkdir()
    rows = {
        row_id: DrawingSourceRow(
            row_id=row_id,
            location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
            object_index_raw="1006",
            drawing_code_raw="А-001",
            work_name_raw="Монтаж кабеля",
            unit_raw="м",
            remaining_quantity=Decimal("1"),
            remaining_total_cost=None,
            formula_values=(),
            cached_values=(),
            source_document_type="ks6a",
            source_period=None,
            source_revision=None,
            status=Status.OK,
            warnings=(),
        )
        for row_id in ("row-a", "row-b")
    }
    decisions = {
        row_id: MatchDecision(
            row_id,
            TargetWorkCategory.LOW_CURRENT_CABLE,
            "review",
            "review",
            None,
            None,
            0.7,
            0.7,
            "manual_review",
            (),
            "review",
            True,
            Status.OK,
            (),
        )
        for row_id in rows
    }
    job = DrawingCardJob(
        job_id="empty-cost-cluster-job",
        directory=directory,
        sources=(),
        source_hashes=(),
        mode="create",
        period=None,
        existing_card=None,
        status="review_required",
        category_units={"low_current_cable": ("м",)},
        review_items={row_id: {"review_id": row_id} for row_id in rows},
        review_rows=rows,
        review_decisions=decisions,
    )
    service._jobs[job.job_id] = job

    cluster = service.list_review_clusters(job_id=job.job_id)["items"][0]

    assert cluster["aggregate_total_cost"] is None


def test_machine_consensus_uses_only_the_canonical_regular_private_file(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    canonical = service.workspace_root / "machine-consensus.jsonl"

    assert service._machine_consensus_path() is None
    canonical.write_text("{}", encoding="utf-8")
    assert service._machine_consensus_path() == canonical
    canonical.unlink()
    outside = tmp_path / "outside.jsonl"
    outside.write_text("{}", encoding="utf-8")
    canonical.symlink_to(outside)

    assert service._machine_consensus_path() is None


def test_initial_run_and_approved_inline_review_rerun_are_both_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    calls: list[tuple[Path | None, bool]] = []

    def fake_run(
        job: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ) -> DrawingCardJob:
        calls.append((review_decisions, strict))
        job.status = "ready"
        return job

    monkeypatch.setattr(service, "_run", fake_run)
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    job.status = "review_required"
    job.review_items = {"row-1": {"review_id": "row-1"}}
    from report_processor.drawing_card.review.inline import review_approval

    job.inline_approvals = {"row-1": review_approval("row-1", "approve", "power_cable")}

    service.apply_inline_review(job_id=job.job_id)

    assert calls[0] == (None, True)
    assert calls[1][0] == job.directory / "attempts" / "0001" / "inline_review_decisions.json"
    assert calls[1][1] is True


@pytest.mark.parametrize("rerun_status", ("ready", "failed", "blocked"))
def test_inline_review_feedback_uses_initial_snapshot_only_after_ready_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rerun_status: str
) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    original_row = DrawingSourceRow(
        row_id="initial-row",
        location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
        object_index_raw="1006",
        drawing_code_raw="А-001",
        work_name_raw="Исходное решение",
        unit_raw="м",
        remaining_quantity=Decimal("1"),
        remaining_total_cost=Decimal("2"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )
    replacement_row = DrawingSourceRow(
        row_id="rerun-row",
        location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 11, ("A11",)),
        object_index_raw="1006",
        drawing_code_raw="А-001",
        work_name_raw="Перезаписанное состояние",
        unit_raw="шт",
        remaining_quantity=Decimal("3"),
        remaining_total_cost=Decimal("4"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )
    feedback_calls: list[tuple[dict[str, DrawingSourceRow], dict[str, object]]] = []

    def fake_run(
        job: DrawingCardJob, *, review_decisions: Path | None = None, strict: bool = True
    ) -> DrawingCardJob:
        if review_decisions is None:
            job.status = "review_required"
            return job
        assert strict is True
        job.review_rows = {replacement_row.row_id: replacement_row}
        job.inline_approvals = {}
        job.status = rerun_status
        return job

    def capture_feedback(_path, rows, approvals) -> None:
        feedback_calls.append((dict(rows), dict(approvals)))

    monkeypatch.setattr(service, "_run", fake_run)
    monkeypatch.setattr(
        "report_processor.admin_panel.drawing_card_service.append_feedback", capture_feedback
    )
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    job.review_items = {original_row.row_id: {"review_id": original_row.row_id}}
    job.review_rows = {original_row.row_id: original_row}
    from report_processor.drawing_card.review.inline import review_approval

    job.inline_approvals = {
        original_row.row_id: review_approval(original_row.row_id, "approve", "low_current_cable")
    }

    service.apply_inline_review(job_id=job.job_id)

    if rerun_status == "ready":
        assert len(feedback_calls) == 1
        assert feedback_calls[0][0] == {original_row.row_id: original_row}
        assert set(feedback_calls[0][1]) == {original_row.row_id}
    else:
        assert feedback_calls == []


def test_rerun_clears_inline_approvals_for_a_new_review_state(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    row = DrawingSourceRow(
        row_id="same-row-id",
        location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
        object_index_raw="1006",
        drawing_code_raw="А-001",
        work_name_raw="Повторная проверка",
        unit_raw="м",
        remaining_quantity=Decimal("1"),
        remaining_total_cost=Decimal("2"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )
    decision = MatchDecision(
        row.row_id,
        TargetWorkCategory.LOW_CURRENT_CABLE,
        "review",
        "review",
        None,
        None,
        0.7,
        0.7,
        "manual_review",
        (),
        "review",
        True,
        Status.OK,
        (),
    )
    run_number = 0

    def runner(request) -> WorkflowResult:
        nonlocal run_number
        run_number += 1
        run_dir = request.work_dir / f"review-{run_number}"
        run_dir.mkdir(parents=True)
        (run_dir / "manual_review.xlsx").write_bytes(b"PK\x03\x04review")
        return WorkflowResult(
            run_id=f"review-{run_number}",
            status=Status.BLOCKED,
            work_dir=run_dir,
            source_rows=[row],
            decisions=[decision],
            category_units={"low_current_cable": ("м",)},
            manual_review_count=1,
            warnings=["MANUAL_REVIEW_REQUIRED:1"],
            blockers=["MANUAL_REVIEW_REQUIRED"],
            blocker_counts={"MANUAL_REVIEW_REQUIRED": 1},
        )

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    job.inline_approvals[row.row_id] = review_approval(row.row_id, "approve", "low_current_cable")

    service._run(job, review_decisions=job.directory / "decisions.json", strict=True)

    assert job.status == "review_required"
    assert job.inline_approvals == {}


def test_manual_review_blocker_count_uses_review_row_count(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request) -> WorkflowResult:
        run_dir = request.work_dir / "review"
        run_dir.mkdir(parents=True)
        (run_dir / "manual_review.xlsx").write_bytes(b"PK\x03\x04review")
        return WorkflowResult(
            run_id="review",
            status=Status.BLOCKED,
            work_dir=run_dir,
            manual_review_count=7,
            warnings=["MANUAL_REVIEW_REQUIRED:7"],
            blockers=["MANUAL_REVIEW_REQUIRED"],
            blocker_counts={"MANUAL_REVIEW_REQUIRED": 1},
        )

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    payload = drawing_card_job_payload(job)

    assert job.blocker_counts["MANUAL_REVIEW_REQUIRED"] == 7
    assert payload["issues"] == [
        {
            "code": "MANUAL_REVIEW_REQUIRED",
            "message": "Есть строки, для которых нужно решение пользователя.",
            "action": "Откройте шаг проверки и примените решение к каждой группе.",
            "count": 7,
            "blocking": True,
        }
    ]


@pytest.mark.parametrize("terminal_cause", ("NO_CARD_ROWS", "OUTPUT_BASE_MISSING"))
def test_terminal_workflow_cause_is_exposed_as_a_blocking_reason(
    tmp_path: Path, terminal_cause: str
) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"

    def runner(request) -> WorkflowResult:
        run_dir = request.work_dir / "blocked"
        run_dir.mkdir(parents=True)
        return WorkflowResult(
            run_id="blocked",
            status=Status.BLOCKED,
            work_dir=run_dir,
            warnings=[terminal_cause],
        )

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("source.xlsx", fixture.read_bytes())])
    reasons = drawing_card_job_payload(job)["blocking_reasons"]

    assert job.errors == (terminal_cause, "WORKFLOW_BLOCKED")
    assert job.terminal_cause == "workflow_blocked"
    assert [reason["code"] for reason in reasons] == [terminal_cause, "WORKFLOW_BLOCKED"]

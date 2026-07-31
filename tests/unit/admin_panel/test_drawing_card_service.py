"""Regression checks for the drawing-card service beside the existing admin service."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
)
from report_processor.drawing_card.statuses import Status
from report_processor.drawing_card.workflow import run_workflow


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

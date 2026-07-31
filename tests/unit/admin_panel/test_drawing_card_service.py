"""Regression checks for the drawing-card service beside the existing admin service."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
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

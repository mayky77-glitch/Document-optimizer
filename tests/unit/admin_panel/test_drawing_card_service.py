"""Regression checks for the drawing-card service beside the existing admin service."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import DrawingCardService
from report_processor.drawing_card.workflow import run_workflow


def test_unknown_drawing_card_job_is_not_resolved_as_a_workspace_path(tmp_path: Path) -> None:
    service = DrawingCardService(tmp_path / "private-workspaces")

    with pytest.raises(KeyError):
        service.get_job("../../private-workspaces")
    with pytest.raises(KeyError):
        service.get_result("../../private-workspaces")
    with pytest.raises(KeyError):
        service.get_review("../../private-workspaces")


def test_injected_runner_preserves_source_basename_with_rag_disabled(tmp_path: Path) -> None:
    fixture = Path(__file__).parents[2] / "fixtures" / "drawing_card" / "demo_source.xlsx"
    seen = []

    def runner(request):
        seen.append(request)
        return run_workflow(request)

    service = DrawingCardService(tmp_path / "private-workspaces", runner=runner)
    job = service.create_job(sources=[("0906_demo_input.xlsx", fixture.read_bytes())])

    assert len(seen) == 1
    assert seen[0].rag_mode == "off"
    assert seen[0].inputs[0].name == "01-0906_demo_input.xlsx"
    assert seen[0].inputs[0].read_bytes() == fixture.read_bytes()
    assert seen[0].inputs[0].resolve() != fixture.resolve()
    assert str(tmp_path) not in str(drawing_card_job_payload(job))

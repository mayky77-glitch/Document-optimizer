"""HTTP lifecycle checks for recoverable background drawing-card jobs."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.drawing_card_service import DrawingCardService
from report_processor.drawing_card.lifecycle import DrawingCardWorkflowCancelled
from report_processor.drawing_card.models import WorkflowResult
from report_processor.drawing_card.statuses import Status

FIXTURE = Path(__file__).parents[1] / "fixtures" / "drawing_card" / "demo_source.xlsx"


def _files() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        (
            "sources",
            (
                "source.xlsx",
                FIXTURE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
    ]


def _wait_payload(client: TestClient, job_id: str, status: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        payload = client.get(f"/api/drawing-card/jobs/{job_id}").json()
        if payload["status"] == status:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not reach {status}")


def test_upload_returns_fast_and_cancel_retry_never_publishes_partial_xlsx(
    tmp_path: Path,
) -> None:
    first_started = threading.Event()
    calls = 0

    def runner(request):
        nonlocal calls
        calls += 1
        run_dir = request.work_dir / f"run-{calls}"
        run_dir.mkdir(parents=True)
        assert request.output is not None
        if calls == 1:
            request.output.write_bytes(b"partial")
            first_started.set()
            while request.cancel_requested is not None and not request.cancel_requested():
                time.sleep(0.005)
            raise DrawingCardWorkflowCancelled()
        request.output.write_bytes(b"PK\x03\x04validated")
        return WorkflowResult(
            run_id=f"run-{calls}",
            status=Status.OK,
            work_dir=run_dir,
            output_path=request.output,
        )

    service = DrawingCardService(tmp_path / "drawing-card", runner=runner, background=True)
    app = create_app(
        drawing_card_service=service,
        workspace_root=tmp_path / "private-workspaces",
    )
    headers = {"Idempotency-Key": "browser-request-0001"}
    with TestClient(app) as client:
        started = time.monotonic()
        created = client.post("/api/drawing-card/jobs", files=_files(), headers=headers)
        elapsed = time.monotonic() - started
        assert created.status_code == 201
        assert elapsed < 1
        payload = created.json()
        assert payload["status"] in {"queued", "processing"}
        assert payload["phase"] == "upload"
        assert payload["progress"]["total_files"] == 1
        assert payload["can_cancel"] is True
        assert first_started.wait(1)

        duplicate = client.post("/api/drawing-card/jobs", files=_files(), headers=headers)
        assert duplicate.json()["job_id"] == payload["job_id"]
        assert calls == 1

        cancelled = client.post(f"/api/drawing-card/jobs/{payload['job_id']}/cancel")
        assert cancelled.status_code == 202
        terminal = _wait_payload(client, payload["job_id"], "cancelled")
        assert terminal["terminal_cause"] == "cancelled"
        assert terminal["can_retry"] is True
        assert client.get(f"/api/drawing-card/jobs/{payload['job_id']}/result").status_code == 404

        retried = client.post(f"/api/drawing-card/jobs/{payload['job_id']}/retry")
        assert retried.status_code == 202
        ready = _wait_payload(client, payload["job_id"], "ready")
        assert ready["attempt"] == 2
        assert ready["result_url"]
        assert client.get(str(ready["result_url"])).status_code == 200


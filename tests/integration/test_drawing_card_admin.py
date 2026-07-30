"""Black-box HTTP contract for drawing-card admin routes."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "drawing_card"


class FakeDrawingCardService:
    def __init__(self, private_root: Path) -> None:
        self.private_root = private_root
        self.calls: list[dict[str, object]] = []
        self.job = SimpleNamespace(
            job_id="opaque-job",
            status="review_required",
            summary={"source_files": 1, "extracted_rows": 7, "card_rows": 32, "manual_review": 1},
            warnings=[],
        )

    def create_job(self, **payload: object) -> object:
        self.calls.append(dict(payload))
        return self.job

    def get_job(self, job_id: str) -> object:
        if job_id != "opaque-job":
            raise KeyError(job_id)
        return self.job

    def get_result(self, job_id: str) -> tuple[str, bytes]:
        if job_id != "opaque-job":
            raise KeyError(job_id)
        raise KeyError(job_id)

    def get_review(self, job_id: str) -> tuple[str, bytes]:
        if job_id != "opaque-job":
            raise KeyError(job_id)
        return "manual-review.xlsx", b"PK\x03\x04review"

    def apply_review(self, *, job_id: str, review_name: str, review_content: bytes) -> object:
        if job_id != "opaque-job" or not review_content.startswith(b"PK"):
            raise ValueError("invalid review")
        self.job = SimpleNamespace(
            job_id=job_id,
            status="ready",
            summary={"source_files": 1, "extracted_rows": 7, "card_rows": 32, "manual_review": 0},
            warnings=[],
        )
        return self.job


@pytest.fixture
def client(tmp_path: Path):
    service = FakeDrawingCardService(tmp_path / "private-workspaces")
    app = create_app(drawing_card_service=service, workspace_root=tmp_path / "private-workspaces")
    with TestClient(app) as test_client:
        yield test_client, service, tmp_path


def _files(name: str = "source.xlsx", content: bytes | None = None):
    return [
        (
            "sources",
            (
                name,
                content or (FIXTURES / "demo_source.xlsx").read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )
    ]


def test_create_and_read_job_hide_private_paths_from_path_header_and_json(client) -> None:
    test_client, service, private_root = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    fetched = test_client.get("/api/drawing-card/jobs/opaque-job")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert service.calls and service.calls[0]["sources"]
    for response in (created, fetched):
        assert str(private_root) not in response.text
        assert str(private_root) not in " ".join(
            f"{key}:{value}" for key, value in response.headers.items()
        )


@pytest.mark.parametrize("name", ("archive.zip", "../private.xlsx"))
def test_create_rejects_archive_and_path_like_uploads(client, name: str) -> None:
    response = client[0].post("/api/drawing-card/jobs", files=_files(name=name))

    assert response.status_code == 400


def test_review_download_upload_and_rerun_use_the_review_field(client) -> None:
    test_client, _, _ = client
    downloaded = test_client.get("/api/drawing-card/jobs/opaque-job/review")
    rerun = test_client.post(
        "/api/drawing-card/jobs/opaque-job/review",
        files={
            "review": (
                "manual-review.xlsx",
                downloaded.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert downloaded.status_code == 200
    assert "manual-review.xlsx" in downloaded.headers["content-disposition"]
    assert rerun.status_code == 200
    assert rerun.json()["status"] == "ready"

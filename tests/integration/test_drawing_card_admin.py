"""Black-box HTTP contract for drawing-card admin routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "drawing_card"


class FakeDrawingCardService(DrawingCardService):
    def __init__(self, private_root: Path) -> None:
        super().__init__(private_root)
        self.calls: list[dict[str, object]] = []
        self.created_job_ids: list[str] = []

    def create_job(self, **payload: object) -> DrawingCardJob:
        self.calls.append(dict(payload))
        job = super().create_job(**payload)
        self.created_job_ids.append(job.job_id)
        return job

    def _run(self, job: DrawingCardJob, *, review_decisions: Path | None = None) -> DrawingCardJob:
        del review_decisions
        job.status = "review_required"
        job.summary = {
            "source_files": len(job.sources),
            "extracted_rows": 7,
            "card_rows": 32,
            "manual_review": 1,
        }
        job.warnings = []
        job.review = job.directory / "private-manual-review.xlsx"
        job.review.write_bytes(b"PK\x03\x04review")
        job.review.chmod(0o600)
        return job

    def apply_review(
        self, *, job_id: str, review_name: str, review_content: bytes
    ) -> DrawingCardJob:
        job = self.get_job(job_id)
        if not review_name.endswith(".xlsx") or not review_content.startswith(b"PK"):
            raise ValueError("invalid review")
        job.status = "ready"
        job.summary["manual_review"] = 0
        job.review = None
        return job


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
    job_id = created.json()["job_id"]
    fetched = test_client.get(f"/api/drawing-card/jobs/{job_id}")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert service.calls and service.calls[0]["sources"]
    for response in (created, fetched):
        assert str(private_root) not in response.text
        assert str(private_root) not in " ".join(
            f"{key}:{value}" for key, value in response.headers.items()
        )


@pytest.mark.parametrize(
    ("name", "expected_error"),
    (
        (
            "super-secret-archive.zip",
            "Неподдерживаемый тип файла. Загрузите Excel-файл (.xlsx, .xlsm или .xlsb)",
        ),
        ("../private-source.xlsx", "Недопустимое имя загружаемого файла"),
    ),
)
def test_create_rejects_unsupported_and_path_like_uploads(
    client, name: str, expected_error: str
) -> None:
    test_client, service, _ = client
    response = test_client.post("/api/drawing-card/jobs", files=_files(name=name))

    assert response.status_code == 400
    assert response.json() == {"error": expected_error}
    assert name not in response.text
    assert service.created_job_ids == []


def test_create_rejects_invalid_workbook_content_without_leaking_upload_data(client) -> None:
    test_client, service, _ = client
    filename = "private-source.xlsx"
    content = b"not-an-excel-workbook-private-content"

    response = test_client.post(
        "/api/drawing-card/jobs", files=_files(name=filename, content=content)
    )

    assert response.status_code == 400
    assert response.json() == {"error": "Файл не является корректной Excel-книгой"}
    assert filename not in response.text
    assert content.decode() not in response.text
    assert service.created_job_ids == []


def test_create_masks_unknown_validation_error(client, monkeypatch: pytest.MonkeyPatch) -> None:
    test_client, service, private_root = client
    private_detail = f"{private_root}/confidential-source.xlsx"

    def fail_with_private_detail(**payload: object) -> DrawingCardJob:
        del payload
        raise ValueError(private_detail)

    monkeypatch.setattr(service, "create_job", fail_with_private_detail)
    response = test_client.post("/api/drawing-card/jobs", files=_files())

    assert response.status_code == 400
    assert response.json() == {"error": "Проверьте исходные Excel-файлы и выбранную операцию"}
    assert private_detail not in response.text


def test_drawing_card_asset_publishes_local_workbook_preflight(client) -> None:
    test_client, _, _ = client

    response = test_client.get("/static/drawing-card.js")

    assert response.status_code == 200
    assert "workbookPreflightError" in response.text
    assert "selectedWorkbooksPreflightError" in response.text
    assert "~$" in response.text
    assert "arrayBuffer()" in response.text
    assert "Файл «${name}» не является корректной Excel-книгой" in response.text
    assert "existingCard.files[0]" in response.text


def test_review_download_upload_and_rerun_use_the_review_field(client) -> None:
    test_client, _, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job_id = created.json()["job_id"]
    downloaded = test_client.get(f"/api/drawing-card/jobs/{job_id}/review")
    rerun = test_client.post(
        f"/api/drawing-card/jobs/{job_id}/review",
        files={
            "review": (
                "manual-review.xlsx",
                downloaded.content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert downloaded.status_code == 200
    assert "manual_review.xlsx" in downloaded.headers["content-disposition"]
    assert rerun.status_code == 200
    assert rerun.json()["status"] == "ready"

"""HTTP contract for the additive drawing-card packet review API."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService

FIXTURES = Path(__file__).parents[1] / "fixtures" / "drawing_card"


class ReviewApiStub(DrawingCardService):
    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.cluster_calls: list[dict[str, object]] = []
        self.member_versions: list[str | None] = []

    def _run(self, job: DrawingCardJob, *, review_decisions: Path | None = None) -> DrawingCardJob:
        del review_decisions
        job.status = "review_required"
        job.summary = {"source_files": len(job.sources)}
        return job

    def list_review_clusters(self, **kwargs: object) -> dict[str, object]:
        self.cluster_calls.append(kwargs)
        return {
            "items": [
                {
                    "cluster_id": "packet-1",
                    "version": "packet-v1",
                    "work_name": "Монтаж кабеля",
                    "absolute_path": "/private/workspace/packet.json",
                    "members": [
                        {
                            "review_id": "row-1",
                            "version": "row-v1",
                            "safe_filename": "C:\\private\\source.xlsx",
                            "sheet_name": "Лист1",
                            "row_number": 7,
                            "work_name": "Монтаж кабеля",
                            "reason_label": "Требуется проверка.",
                        }
                    ],
                }
            ],
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "total_clusters": 1,
            "unresolved_clusters": 1,
            "total_rows": 1,
            "unresolved_rows": 1,
            "review_categories": [
                {"id": "power_cable", "label": "Силовой кабель", "units": ("м",)}
            ],
            "review_metrics": {
                "packets": 1,
                "private_path": "/private/workspace/metrics.json",
                "negative": -1,
                "nan": float("nan"),
                "enabled": True,
            },
        }

    def get_review_context(self, **kwargs: object) -> dict[str, object]:
        if kwargs["review_id"] != "row-1":
            raise KeyError(kwargs["review_id"])
        return {
            "items": [
                {
                    "review_id": "row-1",
                    "safe_filename": "/private/workspace/source.xlsx",
                    "sheet_name": "Лист1",
                    "row_number": 7,
                    "workspace_path": "/private/workspace",
                }
            ],
            "workspace_path": "/private/workspace",
            "absolute_path": "/private/workspace/context.json",
        }

    def put_review_item(self, **kwargs: object) -> DrawingCardJob:
        version = kwargs.get("version")
        self.member_versions.append(version if isinstance(version, str) else None)
        if version == "stale":
            raise ValueError("stale member")
        return self.get_job(str(kwargs["job_id"]))


@pytest.fixture
def client(tmp_path: Path):
    service = ReviewApiStub(tmp_path / "private-workspaces")
    app = create_app(drawing_card_service=service, workspace_root=tmp_path)
    with TestClient(app) as test_client:
        yield test_client, service


def _job_id(client: TestClient) -> str:
    response = client.post(
        "/api/drawing-card/jobs",
        files=[
            (
                "sources",
                (
                    "source.xlsx",
                    (FIXTURES / "demo_source.xlsx").read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
        ],
    )
    assert response.status_code == 201
    return response.json()["job_id"]


def test_packet_filters_categories_metrics_and_safe_members(client) -> None:
    test_client, service = client
    job_id = _job_id(test_client)
    response = test_client.get(
        f"/api/drawing-card/jobs/{job_id}/review/clusters",
        params={
            "reason": "unit_mismatch",
            "category": "power_cable",
            "safe_filename": "source.xlsx",
            "confidence": "0.75",
            "only_unresolved": "false",
        },
    )

    assert response.status_code == 200
    assert service.cluster_calls[-1] == {
        "job_id": job_id,
        "page": 1,
        "page_size": 50,
        "reason": "unit_mismatch",
        "category": "power_cable",
        "safe_filename": "source.xlsx",
        "confidence": pytest.approx(0.75),
        "only_unresolved": False,
    }
    payload = response.json()
    assert payload["packets"] == payload["clusters"] == payload["items"]
    assert payload["review_categories"] == [
        {"id": "power_cable", "label": "Силовой кабель", "units": ["м"]}
    ]
    assert payload["review_metrics"] == {"packets": 1}
    assert payload["items"][0]["members"][0]["safe_filename"] == "source.xlsx"
    assert "private" not in response.text
    assert "absolute_path" not in payload["items"][0]


@pytest.mark.parametrize(
    "query",
    [
        {"confidence": "1.1"},
        {"confidence": "not-a-number"},
        {"safe_filename": "../source.xlsx"},
        {"only_unresolved": "yes"},
    ],
)
def test_packet_filter_validation(client, query: dict[str, str]) -> None:
    test_client, _service = client
    response = test_client.get(
        f"/api/drawing-card/jobs/{_job_id(test_client)}/review/clusters", params=query
    )
    assert response.status_code == 400


def test_context_is_bounded_and_never_discloses_paths(client) -> None:
    test_client, _service = client
    job_id = _job_id(test_client)
    response = test_client.get(
        f"/api/drawing-card/jobs/{job_id}/review/items/row-1/context?radius=3"
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "review_id": "row-1",
            "safe_filename": "source.xlsx",
            "sheet_name": "Лист1",
            "row_number": 7,
        }
    ]
    assert "private" not in response.text
    assert "absolute_path" not in response.json()
    assert (
        test_client.get(
            f"/api/drawing-card/jobs/{job_id}/review/items/row-1/context?radius=6"
        ).status_code
        == 400
    )


def test_member_version_is_optional_and_stale_version_is_rejected(client) -> None:
    test_client, service = client
    job_id = _job_id(test_client)
    endpoint = f"/api/drawing-card/jobs/{job_id}/review/items/row-1"

    assert test_client.put(endpoint, json={"action": "exclude"}).status_code == 200
    assert (
        test_client.put(endpoint, json={"action": "exclude", "version": "row-v1"}).status_code
        == 200
    )
    assert (
        test_client.put(endpoint, json={"action": "exclude", "version": "stale"}).status_code == 400
    )
    assert service.member_versions == [None, "row-v1", "stale"]

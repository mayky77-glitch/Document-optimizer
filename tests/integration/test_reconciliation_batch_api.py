from decimal import Decimal
from io import BytesIO
from pathlib import Path
from threading import Event, Thread

from openpyxl import Workbook
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.reconciliation_execution import ReconciliationReviewResult
from report_processor.admin_panel.reconciliation_state import ReconciliationReviewState
from report_processor.admin_panel.service import AdminPanelService
from report_processor.reconciliation_grouping import (
    PackageVersionContext,
    build_reconciliation_packages,
)
from report_processor.reconciliation_review import ReviewRow, build_review_groups


def _result() -> ReconciliationReviewResult:
    rows = {
        row_id: ReviewRow(
            row_id, "Монтаж силового кабеля", "м", Decimal("1"), Decimal("2"), "target-1"
        )
        for row_id in ("row-a", "row-b")
    }
    groups = build_review_groups(rows.values())
    grouping = build_reconciliation_packages(
        rows.values(),
        groups,
        version_context=PackageVersionContext(("source",), "target", "catalog"),
    )
    return ReconciliationReviewResult(
        ReconciliationReviewState(
            rows=rows,
            groups={group.group_id: group for group in groups},
            categories={
                "target-1": "Целевая категория",
                "target-2": "Другая категория",
            },
            source_digests=("source",),
            target_digest="target",
            grouping=grouping,
        ),
        None,
    )


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def _target_workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet["B1"] = "1234"
    sheet["C1"] = "Этап 13.1"
    sheet["D1"] = "1"
    sheet["E1"] = "Целевая работа"
    sheet["F1"] = "шт"
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_package_routes_mass_accept_undo_and_private_payload(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path, execute=lambda _job: _result())
    app = create_app(service=service, workspace_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": ("source.xlsx", _workbook_bytes(), "application/vnd.ms-excel"),
                "target": ("target.xlsx", _target_workbook_bytes(), "application/vnd.ms-excel"),
            },
        )
        payload = created.json()
        package = payload["review_packages"][0]
        accepted = client.post(
            f"/api/jobs/{payload['job_id']}/review/packages/accept-safe",
            json={
                "packages": [{"package_id": package["package_id"], "version": package["version"]}]
            },
        )
        undone = client.post(f"/api/jobs/{payload['job_id']}/review/undo")

    assert created.status_code == 201
    assert accepted.status_code == undone.status_code == 200
    assert accepted.json()["review_can_apply"] is True
    assert undone.json()["review_can_apply"] is False
    assert "Последнее решение отменено" in undone.json()["review_last_action"]["message"]
    serialized = repr(accepted.json())
    assert all(
        value not in serialized for value in ("digest", "path", "sheet", "formula", "warning")
    )


def test_package_route_accepts_an_explicit_alternative_category(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path, execute=lambda _job: _result())
    app = create_app(service=service, workspace_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": ("source.xlsx", _workbook_bytes(), "application/vnd.ms-excel"),
                "target": ("target.xlsx", _target_workbook_bytes(), "application/vnd.ms-excel"),
            },
        ).json()
        package = created["review_packages"][0]
        response = client.put(
            f"/api/jobs/{created['job_id']}/review/packages/{package['package_id']}",
            json={
                "version": package["version"],
                "action": "accept",
                "category_id": "target-2",
                "mode": "cost_only",
            },
        )

    assert response.status_code == 200
    changed = response.json()["review_packages"][0]
    assert changed["action"] == "accept"
    assert changed["selected_category_id"] == "target-2"
    assert changed["mode"] == "cost_only"
    assert response.json()["review_can_apply"] is True


def test_package_and_family_routes_require_versions_without_mutation(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path, execute=lambda _job: _result())
    app = create_app(service=service, workspace_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": ("source.xlsx", _workbook_bytes(), "application/vnd.ms-excel"),
                "target": ("target.xlsx", _target_workbook_bytes(), "application/vnd.ms-excel"),
            },
        ).json()
        package = created["review_packages"][0]
        family = package["families"][0]
        package_response = client.put(
            f"/api/jobs/{created['job_id']}/review/packages/{package['package_id']}",
            json={"action": "reject"},
        )
        family_response = client.put(
            f"/api/jobs/{created['job_id']}/review/families/{family['family_id']}",
            json={"action": "reject"},
        )
        unchanged = client.get(f"/api/jobs/{created['job_id']}").json()

    assert package_response.status_code == family_response.status_code == 409
    unchanged_package = unchanged["review_packages"][0]
    assert unchanged_package["action"] is None
    assert unchanged_package["families"][0]["action"] is None


def test_http_mutation_cannot_cross_apply_lock_boundary(tmp_path: Path, monkeypatch) -> None:
    """Every HTTP decision route must share the service apply lock."""
    service = AdminPanelService(tmp_path, execute=lambda _job: _result())
    app = create_app(service=service, workspace_root=tmp_path)
    entered = Event()
    release = Event()

    original = service._mutate_reconciliation

    def paused_mutation(job_id, method, *args):
        entered.set()
        assert release.wait(5)
        return original(job_id, method, *args)

    monkeypatch.setattr(service, "_mutate_reconciliation", paused_mutation)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": ("source.xlsx", _workbook_bytes(), "application/vnd.ms-excel"),
                "target": ("target.xlsx", _target_workbook_bytes(), "application/vnd.ms-excel"),
            },
        ).json()
        package = created["review_packages"][0]
        response = []
        worker = Thread(
            target=lambda: response.append(
                client.put(
                    f"/api/jobs/{created['job_id']}/review/packages/{package['package_id']}",
                    json={
                        "version": package["version"],
                        "action": "accept",
                        "category_id": "target-1",
                        "mode": "quantity_cost",
                    },
                )
            )
        )
        worker.start()
        assert entered.wait(5)

        # Simulate apply having crossed the status boundary while the HTTP
        # mutation is paused before the service-owned lock/status check.
        service.get_job(created["job_id"]).status = "running"
        release.set()
        worker.join(5)

    assert len(response) == 1 and response[0].status_code == 409
    assert service.get_job(created["job_id"]).review_state.package_decisions == {}

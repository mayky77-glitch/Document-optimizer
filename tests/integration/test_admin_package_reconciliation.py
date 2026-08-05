from __future__ import annotations

from decimal import Decimal
from pathlib import Path, PurePosixPath

from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.package_reconciliation_service import PackageReconciliationService
from report_processor.package_reconciliation.matcher import RowReconciliation
from report_processor.package_reconciliation.report import ReconciliationReport


def _runner(_root: Path) -> ReconciliationReport:
    return ReconciliationReport(
        (
            RowReconciliation(
                status="NO_EVIDENCE",
                workbook_path=PurePosixPath("nested/act.xlsx"),
                sheet_name="Лист1",
                row_number=4,
                work_code="1.1",
                pdf_path=None,
                confidence=None,
                reason_codes=("no_exact_work_code_candidate",),
                quantity_comparison="NOT_COMPARABLE",
                workbook_quantity=Decimal("2"),
                workbook_unit="шт",
                pdf_quantity=None,
                pdf_unit=None,
            ),
        )
    )


def test_folder_upload_runs_injected_runner_and_downloads_safe_json(tmp_path: Path) -> None:
    service = PackageReconciliationService(tmp_path / "private", runner=_runner)
    app = create_app(workspace_root=tmp_path / "jobs", package_reconciliation_service=service)
    with TestClient(app) as client:
        response = client.post(
            "/api/package-reconciliation/jobs",
            files=[
                ("files", ("nested/act.xlsx", b"workbook", "application/octet-stream")),
            ],
        )
        payload = response.json()
        downloaded = client.get(payload["download_url"])

    assert response.status_code == 201
    assert downloaded.status_code == 200
    assert payload["status"] == "ready"
    assert payload["summary"] == {"NO_EVIDENCE": 1}
    assert payload["results"][0]["workbook_path"] == "nested/act.xlsx"
    assert downloaded.headers["content-type"].startswith("application/json")
    assert str(tmp_path) not in downloaded.text


def test_folder_upload_rejects_path_traversal_before_running_runner(tmp_path: Path) -> None:
    service = PackageReconciliationService(tmp_path / "private", runner=_runner)
    app = create_app(workspace_root=tmp_path / "jobs", package_reconciliation_service=service)
    with TestClient(app) as client:
        response = client.post(
            "/api/package-reconciliation/jobs",
            files={"files": ("../act.xlsx", b"workbook", "application/octet-stream")},
        )

    assert response.status_code == 400
    assert service._jobs == {}


def test_package_static_assets_are_explicitly_published(tmp_path: Path) -> None:
    service = PackageReconciliationService(tmp_path / "private", runner=_runner)
    app = create_app(workspace_root=tmp_path / "jobs", package_reconciliation_service=service)
    with TestClient(app) as client:
        package_css = client.get("/static/package-reconciliation.css")
        package_script = client.get("/static/package-reconciliation.js")
        help_css = client.get("/static/help.css")
        unknown = client.get("/static/not-published.css")

    assert package_css.status_code == package_script.status_code == help_css.status_code == 200
    assert package_css.headers["content-type"].startswith("text/css")
    assert package_script.headers["content-type"].startswith("text/javascript")
    assert help_css.headers["content-type"].startswith("text/css")
    assert unknown.status_code == 404

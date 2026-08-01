from decimal import Decimal
from pathlib import Path

from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.reconciliation_execution import ReconciliationReviewResult
from report_processor.admin_panel.reconciliation_state import ReconciliationReviewState
from report_processor.admin_panel.service import AdminPanelService
from report_processor.reconciliation_review import ReviewRow, build_review_groups


def _review_result() -> ReconciliationReviewResult:
    rows = {
        row_id: ReviewRow(row_id, "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
        for row_id in ("source-a:1", "source-b:1")
    }
    (group,) = build_review_groups(rows.values())
    return ReconciliationReviewResult(
        ReconciliationReviewState(
            rows=rows,
            groups={group.group_id: group},
            categories={"target-1": "Целевой этап"},
            source_digests=("source-a", "source-b"),
            target_digest="target",
        )
    )


def test_authoritative_review_payload_and_local_responsive_controls(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path, execute=lambda _job: _review_result())
    app = create_app(service=service, workspace_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": (
                    "source-a.xlsx",
                    b"PK\x03\x04a",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                "target": (
                    "target.xlsx",
                    b"PK\x03\x04t",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )
        javascript = client.get("/static/admin.js").text
        css = client.get("/static/admin.css").text

    payload = created.json()
    assert created.status_code == 201
    assert payload["unresolved_review_count"] == 2 and payload["review_can_apply"] is False
    assert {"review_groups", "review_categories", "download_url"} <= set(payload)
    serialized = repr(payload)
    assert all(
        token not in serialized
        for token in (
            "paths",
            "sheets",
            "coordinates",
            "provenance",
            "warnings",
            "review_journal_only",
        )
    )
    assert "/review/groups/" in javascript and "/review/items/" in javascript
    assert "mode-switch" in javascript and "@container" in css
    assert "http://" not in javascript + css and "https://" not in javascript + css

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
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
    sheet["B1"], sheet["C1"], sheet["D1"], sheet["E1"], sheet["F1"] = (
        "Индекс документа",
        "Номер этапа",
        "Номер п/п",
        "Наименование работ",
        "Единица измерения",
    )
    sheet["B3"], sheet["C3"], sheet["D3"], sheet["E3"], sheet["F3"] = (
        "1234",
        "Этап 13.1",
        "1",
        "Целевая работа",
        "шт",
    )
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()


def test_authoritative_review_payload_and_local_responsive_controls(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path, execute=lambda _job: _review_result())
    app = create_app(service=service, workspace_root=tmp_path)
    with TestClient(app) as client:
        created = client.post(
            "/api/jobs",
            files={
                "sources": (
                    "source-a.xlsx",
                    _workbook_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                "target": (
                    "target.xlsx",
                    _target_workbook_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )
        javascript = client.get("/static/admin.js").text
        css = client.get("/static/admin.css").text

    payload = created.json()
    assert created.status_code == 201
    assert payload["unresolved_review_count"] == 1 and payload["review_can_apply"] is False
    assert {"review_groups", "review_categories", "download_url"} <= set(payload)
    assert len(payload["review_groups"]) == 1
    assert [member["row_id"] for member in payload["review_groups"][0]["members"]] == [
        "source-a:1",
        "source-b:1",
    ]
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
    assert 'input.type = "radio"' in javascript
    assert (
        '[["quantity_cost", "Количество + стоимость"], ["cost_only", "Только стоимость"]]'
        in javascript
    )
    assert 'document.createElement("details")' in javascript
    assert "member-override" in javascript and "renderMemberRow" in javascript
    assert "showStageSelection" in javascript
    assert "stageSelection.hidden" in javascript
    assert "stage.focus({ preventScroll: true })" in javascript
    assert "http://" not in javascript + css and "https://" not in javascript + css


def test_main_review_hands_package_payloads_to_the_dedicated_batch_module() -> None:
    asset = Path(__file__).parents[2] / "src" / "report_processor" / "admin_panel" / "assets"
    javascript = (asset / "admin.js").read_text()

    assert "window.ReconciliationBatchReview?.supports(payload)" in javascript
    assert "restoredJobId" in javascript
    assert "batchReview.render(payload)" in javascript
    assert "applyArea.hidden = payload.review_can_apply !== true" in javascript
    assert 'applyButton.textContent = "Сформировать результат"' in javascript

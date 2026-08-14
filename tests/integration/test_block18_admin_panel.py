"""Black-box contract tests for the local-only Block 18 admin panel."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.service import AdminPanelService, TargetStageSelectionError


class FakeAdminService:
    """Injectable in-memory service with a private result path."""

    def __init__(self, result_path: Path) -> None:
        self.result_path = result_path
        self.create_calls: list[dict[str, object]] = []
        self.decision_calls: list[dict[str, str]] = []
        self.manual_decision_calls: list[dict[str, object]] = []
        self.stage_error: TargetStageSelectionError | None = None
        self.jobs = {
            "job-001": {
                "job_id": "job-001",
                "stage": "13.1",
                "status": "review_required",
                "summary": {"processed": 2},
                "discrepancies": [
                    {"category": "unit_conflict", "color": "red"},
                    {"category": "unchanged_value", "color": "yellow"},
                    {"category": "cost_threshold", "color": "orange"},
                    {
                        "discrepancy_id": "manual-001",
                        "code": "AMBIGUOUS",
                        "category": "manual_review",
                        "severity": "manual_review",
                        "message": "Связь требует ручной проверки",
                    },
                ],
                "suggestions": [
                    {
                        "suggestion_id": "suggestion-001",
                        "candidate_label": "Предложенный этап",
                        "target_label": "Целевой этап",
                        "score": 0.91,
                        "requires_manual_review": True,
                    }
                ],
                "decisions": [],
                "download_url": None,
            }
        }

    def create_job(
        self,
        *,
        source_name: str | None = None,
        source_content: bytes | None = None,
        sources: list[tuple[str, bytes]] | None = None,
        target_name: str,
        target_content: bytes,
        stage: str | None,
        mode: str,
        operation: str = "reconcile",
        reporting_period: str | None = None,
        validate_target_stage: bool = False,
    ) -> Mapping[str, object]:
        self.create_calls.append(
            {
                "source_name": source_name,
                "source_content": source_content,
                "sources": sources,
                "target_name": target_name,
                "target_content": target_content,
                "stage": stage,
                "mode": mode,
                "operation": operation,
                "reporting_period": reporting_period,
                "validate_target_stage": validate_target_stage,
            }
        )
        if self.stage_error is not None:
            raise self.stage_error
        return self.jobs["job-001"]

    def get_job(self, job_id: str) -> Mapping[str, object]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

    def record_decision(
        self, *, job_id: str, suggestion_id: str, decision: str
    ) -> Mapping[str, object]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        if suggestion_id != "suggestion-001" or decision not in {"fit", "not_fit"}:
            raise ValueError("invalid controlled review input")
        self.decision_calls.append(
            {"job_id": job_id, "suggestion_id": suggestion_id, "decision": decision}
        )
        job = dict(self.jobs[job_id])
        job["decisions"] = [{"suggestion_id": suggestion_id, "decision": decision}]
        job.update(status="ready", download_url=f"/api/jobs/{job_id}/result")
        self.jobs[job_id] = job
        return job

    def record_manual_discrepancy_decision(
        self, *, job_id: str, group_id: str, discrepancy_ids: list[str], decision: str
    ) -> Mapping[str, object]:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        expected = {
            "group_id": "manual-group",
            "discrepancy_ids": ["manual-001"],
            "decision": "approve",
        }
        received = {"group_id": group_id, "discrepancy_ids": discrepancy_ids, "decision": decision}
        if received != expected:
            raise ValueError("invalid controlled manual decision")
        self.manual_decision_calls.append(received)
        return self.jobs[job_id]

    def get_result(self, job_id: str) -> tuple[Path, str]:
        if job_id not in self.jobs or self.jobs[job_id]["status"] != "ready":
            raise KeyError(job_id)
        return self.result_path, "optimized-report.xlsx"


@pytest.fixture
def client(tmp_path: Path):
    result = tmp_path / "private-result.bin"
    result.write_bytes(b"controlled-result")
    service = FakeAdminService(result)
    app = create_app(service=service, workspace_root=tmp_path / "private-workspaces")
    with TestClient(app) as test_client:
        yield test_client, service, tmp_path


def _files(*, source_name: str = "source.xlsx", target_name: str = "target.xlsx"):
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return {
        "source": (source_name, b"PK\x03\x04source", content_type),
        "target": (target_name, b"PK\x03\x04target", content_type),
    }


def test_upload_requires_two_xlsx_files_and_keeps_bytes_in_injected_service(client) -> None:
    test_client, service, _ = client
    missing = test_client.post("/api/jobs", files={"source": _files()["source"]})
    invalid = test_client.post("/api/jobs", files=_files(source_name="source.txt"))

    assert missing.status_code == 400
    assert invalid.status_code == 400
    assert service.create_calls == []

    created = test_client.post("/api/jobs", files=_files())
    assert created.status_code == 201
    assert service.create_calls[0]["source_content"] == b"PK\x03\x04source"
    assert service.create_calls[0]["target_content"] == b"PK\x03\x04target"


def test_omitted_stage_and_explicit_stage_mode_map_to_service_without_legacy_side_effects(
    client,
) -> None:
    test_client, service, _ = client
    assert test_client.post("/api/jobs", files=_files()).status_code == 201
    assert (
        test_client.post(
            "/api/jobs", files=_files(), data={"stage": "14.2", "mode": "dry-run"}
        ).status_code
        == 201
    )

    assert [(call["stage"], call["mode"]) for call in service.create_calls] == [
        (None, "write"),
        ("14.2", "dry-run"),
    ]
    assert all(call["validate_target_stage"] is True for call in service.create_calls)


def test_reconcile_period_is_forwarded_exactly_and_verify_period_is_rejected_before_creation(
    client,
) -> None:
    test_client, service, _ = client

    created = test_client.post("/api/jobs", files=_files(), data={"reporting_period": "2026-08"})

    assert created.status_code == 201
    assert service.create_calls[-1]["operation"] == "reconcile"
    assert service.create_calls[-1]["reporting_period"] == "2026-08"

    rejected = test_client.post(
        "/api/jobs",
        files=_files(),
        data={"operation": "verify", "reporting_period": "2026-08"},
    )

    assert rejected.status_code == 400
    assert len(service.create_calls) == 1


def test_period_is_forwarded_for_multi_source_upload_path(client) -> None:
    test_client, service, _ = client
    content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    created = test_client.post(
        "/api/jobs",
        files=[
            ("sources", ("source-1.xlsx", b"PK\x03\x04one", content_type)),
            ("sources", ("source-2.xlsx", b"PK\x03\x04two", content_type)),
            ("target", ("target.xlsx", b"PK\x03\x04target", content_type)),
        ],
        data={"reporting_period": "2026-08"},
    )

    assert created.status_code == 201
    assert service.create_calls[-1]["sources"] == [
        ("source-1.xlsx", b"PK\x03\x04one"),
        ("source-2.xlsx", b"PK\x03\x04two"),
    ]
    assert service.create_calls[-1]["reporting_period"] == "2026-08"


def test_period_whitespace_is_forwarded_without_http_normalization(client) -> None:
    test_client, service, _ = client

    created = test_client.post("/api/jobs", files=_files(), data={"reporting_period": " 2026-08"})

    assert created.status_code == 201
    assert service.create_calls[-1]["reporting_period"] == " 2026-08"


def test_stage_selection_and_missing_stage_responses_are_controlled_and_private(client) -> None:
    test_client, service, tmp_path = client
    service.stage_error = TargetStageSelectionError(
        "selection_required", ("14.2", "13.1", "/private/target.xlsx")
    )

    selection = test_client.post("/api/jobs", files=_files())

    assert selection.status_code == 409
    assert selection.json() == {
        "error": "В отчёте найдено несколько этапов. Выберите нужный этап.",
        "code": "selection_required",
        "stage_options": ["13.1", "14.2"],
    }
    assert str(tmp_path) not in selection.text and "private" not in selection.text.casefold()
    assert "download_url" not in selection.json() and "job_id" not in selection.json()

    service.stage_error = TargetStageSelectionError("not_found")
    missing = test_client.post("/api/jobs", files=_files(), data={"stage": "99.9"})

    assert missing.status_code == 400
    assert missing.json()["code"] == "not_found"
    assert missing.json()["stage_options"] == []
    assert "download_url" not in missing.json() and "job_id" not in missing.json()


def test_malformed_target_container_returns_controlled_not_found_without_a_job_directory(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "jobs"
    service = AdminPanelService(workspace)
    app = create_app(service=service, workspace_root=workspace)
    directories_before = {path.name for path in workspace.iterdir() if path.is_dir()}
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/jobs",
            files={
                "source": _files()["source"],
                "target": (
                    "target.xlsx",
                    b"PK\x03\x04malformed-target",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            },
        )

    assert response.status_code == 400
    assert response.json()["code"] == "not_found"
    assert response.json()["stage_options"] == []
    assert service.jobs == {}
    assert {path.name for path in workspace.iterdir() if path.is_dir()} == directories_before


def test_job_payload_uses_controlled_ids_and_never_leaks_private_paths(client) -> None:
    test_client, _, tmp_path = client
    response = test_client.get("/api/jobs/job-001")
    payload = response.json()

    assert response.status_code == 200
    assert payload["job_id"] == "job-001"
    assert set(payload) >= {"job_id", "stage", "status", "summary", "discrepancies", "suggestions"}
    assert str(tmp_path) not in response.text
    assert "private-result.bin" not in response.text


def test_review_needs_explicit_fit_or_not_fit_and_download_is_safe(client) -> None:
    test_client, service, tmp_path = client
    invalid = test_client.post(
        "/api/jobs/job-001/decisions",
        json={"suggestion_id": "suggestion-001", "decision": "approve"},
    )
    accepted = test_client.post(
        "/api/jobs/job-001/decisions",
        json={"suggestion_id": "suggestion-001", "decision": "fit"},
    )
    download = test_client.get("/api/jobs/job-001/result")

    assert invalid.status_code == 400
    assert accepted.status_code == 200
    assert service.decision_calls == [
        {"job_id": "job-001", "suggestion_id": "suggestion-001", "decision": "fit"}
    ]
    assert accepted.json()["download_url"] == "/api/jobs/job-001/result"
    assert accepted.json()["decisions"] == [{"suggestion_id": "suggestion-001", "decision": "fit"}]
    assert download.status_code == 200 and download.content == b"controlled-result"
    assert "optimized-report.xlsx" in download.headers["content-disposition"]
    assert str(tmp_path) not in download.headers["content-disposition"]
    assert "private-result.bin" not in download.headers["content-disposition"]


def test_manual_discrepancy_decision_uses_a_bounded_group_contract(client) -> None:
    test_client, service, _ = client
    invalid = test_client.post(
        "/api/jobs/job-001/manual-discrepancy-decisions",
        json={"group_id": "manual-group", "discrepancy_ids": ["manual-001"], "decision": "fit"},
    )
    accepted = test_client.post(
        "/api/jobs/job-001/manual-discrepancy-decisions",
        json={"group_id": "manual-group", "discrepancy_ids": ["manual-001"], "decision": "approve"},
    )

    assert invalid.status_code == 400
    assert accepted.status_code == 200
    assert service.manual_decision_calls == [
        {"group_id": "manual-group", "discrepancy_ids": ["manual-001"], "decision": "approve"}
    ]


def test_manual_discrepancy_decision_rejects_a_list_above_the_api_cap(client) -> None:
    test_client, service, _ = client
    response = test_client.post(
        "/api/jobs/job-001/manual-discrepancy-decisions",
        json={
            "group_id": "manual-group",
            "discrepancy_ids": ["manual-001"] * 5_001,
            "decision": "approve",
        },
    )

    assert response.status_code == 400
    assert service.manual_decision_calls == []


@pytest.mark.parametrize("path", ("/api/jobs/unknown", "/api/jobs/unknown/result"))
def test_unknown_job_tokens_have_controlled_not_found_responses(client, path: str) -> None:
    response = client[0].get(path)
    assert response.status_code == 404
    assert "traceback" not in response.text.casefold()


def test_local_ui_is_accessible_mobile_safe_and_uses_only_local_assets(client) -> None:
    test_client, _, _ = client
    page = test_client.get("/")
    stylesheet = test_client.get("/static/admin.css")
    theme_script = test_client.get("/static/theme.js")
    html = page.text.casefold()
    css = stylesheet.text.casefold()

    assert page.status_code == stylesheet.status_code == theme_script.status_code == 200
    for label in (
        "проверка документов",
        "исходные книги",
        "отчёт для сравнения",
        "проверить документы",
    ):
        assert label in html
    assert 'id="sources"' in html and 'name="sources"' in html
    assert 'id="target"' in html and 'name="target"' in html
    assert 'id="sources" name="sources" type="file" accept=".xlsx,.xlsm"' in html
    assert 'id="target" name="target" type="file" accept=".xlsx"' in html
    assert 'target-help">один excel-файл .xlsx' in html
    assert 'id="stage-selection"' in html and 'id="stage"' in html
    assert 'aria-describedby="stage-selection-help"' in html
    assert "post /api/jobs" in html
    assert 'name="viewport"' in html and "focus" in css
    assert 'id="theme-toggle"' in html
    assert 'src="/static/theme.js"' in html
    assert "report-processor.theme.v1" in theme_script.text
    assert "#0079c2" in css
    assert (
        ".file-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); "
        "align-items: start;" in css
    )
    assert ".file-field { min-width: 0; align-content: start; }" in css
    assert 'input[type="file"] { min-width: 0; min-height: 56px; padding: 6px 10px;' in css
    assert 'input[type="file"]::file-selector-button {' in css
    assert "height: 40px; margin-inline-end: 10px;" in css
    assert (
        "border: 1px solid var(--input-border); border-radius: 2px; background: var(--soft-blue);"
        in css
    )
    assert 'input[type="file"]:hover::file-selector-button {' in css
    assert 'input[type="file"]:focus-visible {' in css
    for token in ("review-panel", "review-group", "mode-switch", "review-actions"):
        assert token in css
    assert "@media" in css
    assert "http://" not in html + css and "https://" not in html + css
    javascript = test_client.get("/static/admin.js").text
    assert "selection_required" in javascript
    assert "showStageSelection" in javascript and "clearStageSelection" in javascript
    assert 'data.append("stage", stage.value)' in javascript
    assert 'sourceWorkbookExtensions = new Set([".xlsx", ".xlsm"])' in javascript
    assert 'targetWorkbookExtensions = new Set([".xlsx"])' in javascript
    assert "Целевой отчёт должен быть Excel-файлом .xlsx." in javascript


def test_admin_review_cards_expose_authoritative_group_and_row_controls(client) -> None:
    test_client, _, _ = client
    javascript = test_client.get("/static/admin.js").text
    css = test_client.get("/static/admin.css").text
    html = test_client.get("/").text

    assert 'id="review-panel"' in html and 'id="review-groups"' in html
    assert 'id="review-apply"' in html and 'id="review-state"' in html
    assert "reviewGroupsFrom" in javascript and "unresolved_review_count" in javascript
    assert "/review/groups/${encodeURIComponent(group.group_id)}" in javascript
    assert "/review/items/${encodeURIComponent(member.row_id)}" in javascript
    assert "mode-switch" in javascript and "review-category" in javascript
    assert "Принять" in javascript and "Отклонить" in javascript
    assert "Убрать изменение" in javascript and "Применить решения" in html
    assert 'composition.className = "review-composition";' in javascript
    assert "cell.dataset.label = label;" in javascript
    assert "minimumFractionDigits: 2" in javascript
    assert "maximumFractionDigits: 2" in javascript
    assert ".review-group { container-type: inline-size;" in css
    assert ".review-group-head { display: flex; justify-content: space-between;" in css
    assert ".group-decision { display: grid;" in css
    assert "@container (max-width: 620px)" in css
    assert ".review-composition {" in css
    assert ".review-composition td:first-child { grid-column: 1 / -1; }" in css
    assert "content: attr(data-label);" in css

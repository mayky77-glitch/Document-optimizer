"""Black-box contract tests for the local-only Block 18 admin panel."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app


class FakeAdminService:
    """Injectable in-memory service with a private result path."""

    def __init__(self, result_path: Path) -> None:
        self.result_path = result_path
        self.create_calls: list[dict[str, object]] = []
        self.decision_calls: list[dict[str, str]] = []
        self.manual_decision_calls: list[dict[str, object]] = []
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
        source_name: str,
        source_content: bytes,
        target_name: str,
        target_content: bytes,
        stage: str,
        mode: str,
    ) -> Mapping[str, object]:
        self.create_calls.append(
            {
                "source_name": source_name,
                "source_content": source_content,
                "target_name": target_name,
                "target_content": target_content,
                "stage": stage,
                "mode": mode,
            }
        )
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


def test_default_stage_and_explicit_stage_mode_map_to_service_without_legacy_side_effects(
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
        ("13.1", "write"),
        ("14.2", "dry-run"),
    ]


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
        "сверка документов",
        "исходные документы",
        "целевой отчёт",
        "запустить сверку",
    ):
        assert label in html
    assert 'id="sources"' in html and 'name="sources"' in html
    assert 'id="target"' in html and 'name="target"' in html
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
    for token in ("unit_conflict", "unchanged_value", "cost_threshold", "manual_review"):
        assert token in css
    assert "@media" in css
    assert "http://" not in html + css and "https://" not in html + css


def test_admin_review_cards_keep_passive_discrepancies_and_controlled_decisions(client) -> None:
    test_client, _, _ = client
    javascript = test_client.get("/static/admin.js").text
    css = test_client.get("/static/admin.css").text
    html = test_client.get("/").text

    assert 'id="discrepancies"' in html
    assert 'id="suggestion-review"' in html and 'id="suggestions"' in html
    assert "unresolvedSuggestions" in javascript
    assert "manual_review_groups" in javascript
    assert "suggestion_review_groups" in javascript
    assert "manual-discrepancy-decisions" in javascript
    assert "discrepancy-count" in javascript
    assert "Одобрить" in javascript and "Отклонить" in javascript
    assert "/api/jobs/${encodeURIComponent(jobId)}/decisions" in javascript
    assert "decision })," in javascript
    assert (
        '[["Применить", "apply", "suggestion-fit"], ["Отклонить", "reject", "suggestion-not-fit"]]'
        in javascript
    )
    assert "setSuggestionBusy(card, true)" in javascript
    assert "setSuggestionBusy(card, false)" in javascript
    assert 'card.className = "review-item suggestion-card";' in javascript
    assert 'card.className = "review-item manual-review-card";' in javascript
    assert 'header.className = "review-item-head";' in javascript
    assert 'list.className = "review-context";' in javascript
    assert 'decisionRegion.className = "review-decision";' in javascript
    assert 'actions.className = "review-decision-actions";' in javascript
    assert 'renderDecisionContext("Охват", `Вся группа · ${count} замечаний`)' in javascript
    assert 'renderDecisionContext("Действие", "Одобрить или отклонить")' in javascript
    assert 'renderDecisionContext("Эффект", "Только журнал решений")' in javascript
    assert 'details.className = "review-composition";' in javascript
    assert "cell.dataset.label = headings[index];" in javascript
    assert "(Array.isArray(members) ? members : []).forEach" in javascript
    assert "minimumFractionDigits: 2" in javascript
    assert "maximumFractionDigits: 2" in javascript
    assert ".review-item { container-type: inline-size;" in css
    assert ".review-item-head { display: flex; justify-content: space-between;" in css
    assert (
        ".review-context { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    )
    assert (
        ".review-decision { display: grid; grid-template-columns: minmax(220px, 280px) "
        "minmax(0, 390px) max-content;" in css
    )
    assert "@container (max-width: 620px)" in css
    assert (
        ".review-decision-actions { grid-column: auto; grid-template-columns: repeat(2, "
        "minmax(0, 1fr)); }" in css
    )
    assert ".manual-review-card { border-left-color: var(--manual-blue); }" in css
    assert ".review-composition {" in css
    assert ".review-composition td:first-child { grid-column: 1 / -1; }" in css
    assert "content: attr(data-label);" in css

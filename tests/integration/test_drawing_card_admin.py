"""Black-box HTTP contract for drawing-card admin routes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from report_processor.admin_panel import create_app
from report_processor.admin_panel.drawing_card_service import DrawingCardJob, DrawingCardService
from report_processor.drawing_card.models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER

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


def _review_job(service: DrawingCardService, job_id: str) -> DrawingCardJob:
    """Give the HTTP fake one deterministic unresolved inline-review row."""
    job = service.get_job(job_id)
    job.category_units = {
        category.value: (unit,)
        for category, unit in zip(
            CATEGORY_ORDER,
            ("шт", "м3", "т", "шт", "м", "шт", "м", "м"),
            strict=True,
        )
    }
    job.review_items = {
        "review-row-1": {
            "review_id": "review-row-1",
            "наименование": "Монтаж контрольного кабеля",
            "предлагаемая_категория": "low_current_cable",
            "предлагаемая_категория_id": "low_current_cable",
            "предлагаемая_категория_рус": "Прокладка кабеля, провода (Слаботочные сети)",
            "количество": "12",
            "source_unit": "м",
            "target_unit": "м",
            "стоимость": "3500",
            "confidence": 0.72,
        }
    }
    return job


def _cluster_review_job(service: DrawingCardService, job_id: str) -> DrawingCardJob:
    job = _review_job(service, job_id)
    from decimal import Decimal

    from report_processor.drawing_card.models import (
        DrawingSourceLocation,
        DrawingSourceRow,
        MatchDecision,
    )
    from report_processor.drawing_card.statuses import Status

    job.review_items = {
        **job.review_items,
        "review-row-2": {**job.review_items["review-row-1"], "review_id": "review-row-2"},
    }
    rows = {}
    decisions = {}
    for row_id in job.review_items:
        rows[row_id] = DrawingSourceRow(
            row_id=row_id,
            location=DrawingSourceLocation("source", "private.xlsx", "Лист1", 10, ("A10",)),
            object_index_raw="1006",
            drawing_code_raw="А-001",
            work_name_raw="Монтаж контрольного кабеля",
            unit_raw="м",
            remaining_quantity=Decimal("12"),
            remaining_total_cost=Decimal("3500"),
            formula_values=(),
            cached_values=(),
            source_document_type="ks6a",
            source_period=None,
            source_revision=None,
            status=Status.OK,
            warnings=(),
        )
        decisions[row_id] = MatchDecision(
            row_id,
            None,
            "review",
            "review",
            None,
            None,
            0.72,
            0.72,
            "manual_review",
            (),
            "review",
            True,
            Status.OK,
            (Status.UNIT_MISMATCH,),
        )
    job.review_rows, job.review_decisions = rows, decisions
    return job


def test_cluster_api_fans_out_undoes_and_hides_private_metadata(client) -> None:
    test_client, service, private_root = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _cluster_review_job(service, created.json()["job_id"])
    listing = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/clusters")
    cluster = listing.json()["items"][0]

    approved = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters/{cluster['cluster_id']}",
        json={"version": cluster["version"], "action": "approve", "category": "low_current_cable"},
    )
    stale = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters/{cluster['cluster_id']}",
        json={"version": "obsolete", "action": "reject"},
    )
    undone = test_client.delete(
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters/{cluster['cluster_id']}?version={cluster['version']}"
    )

    assert listing.status_code == approved.status_code == undone.status_code == 200
    assert stale.status_code == 409
    assert set(service.get_job(job.job_id).inline_approvals) == set()
    assert listing.json()["total_clusters"] == 1
    assert listing.json()["total_rows"] == 2
    for response in (listing, approved, stale, undone):
        assert str(private_root) not in response.text


def test_cluster_api_matches_the_review_asset_contract(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _cluster_review_job(service, created.json()["job_id"])
    listing = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/clusters")

    assert listing.status_code == 200
    assert "clusters" in listing.json()


def test_cluster_api_accepts_the_asset_delete_payload_and_returns_ui_decision_names(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _cluster_review_job(service, created.json()["job_id"])
    listing = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/clusters")
    cluster = listing.json()["items"][0]

    approved = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters/{cluster['cluster_id']}",
        json={"version": cluster["version"], "action": "approve", "category": "low_current_cable"},
    )
    refetched = test_client.get(
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters?only_unresolved=false"
    )
    undone = test_client.request(
        "DELETE",
        f"/api/drawing-card/jobs/{job.job_id}/review/clusters/{cluster['cluster_id']}",
        json={"version": cluster["version"]},
    )

    assert approved.status_code == 200
    assert refetched.json()["items"][0]["decision"] == "approved"
    assert undone.status_code == 200


def test_cluster_api_fans_out_cost_only_with_category_and_rejects_changed_membership(
    client,
) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _cluster_review_job(service, created.json()["job_id"])
    url = f"/api/drawing-card/jobs/{job.job_id}/review/clusters"
    cluster = test_client.get(url).json()["items"][0]

    applied = test_client.put(
        f"{url}/{cluster['cluster_id']}",
        json={
            "version": cluster["version"],
            "action": "cost_only",
            "category": "power_cable",
        },
    )
    refetched = test_client.get(f"{url}?only_unresolved=false")
    from dataclasses import replace

    extra_row = replace(job.review_rows["review-row-1"], row_id="review-row-3")
    extra_decision = replace(job.review_decisions["review-row-1"], row_id="review-row-3")
    job.review_rows[extra_row.row_id] = extra_row
    job.review_decisions[extra_decision.row_id] = extra_decision
    stale = test_client.put(
        f"{url}/{cluster['cluster_id']}",
        json={"version": cluster["version"], "action": "reject"},
    )

    assert applied.status_code == 200
    assert set(job.inline_approvals) == {"review-row-1", "review-row-2"}
    assert {approval.action for approval in job.inline_approvals.values()} == {"cost_only"}
    assert {approval.category.value for approval in job.inline_approvals.values()} == {
        "power_cable"
    }
    assert refetched.json()["items"][0]["decision"] == "cost_only"
    assert stale.status_code == 409


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


def test_exclusion_audit_is_bounded_and_never_exposes_absolute_paths(client) -> None:
    test_client, service, private_root = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = service.get_job(created.json()["job_id"])
    job.exclusion_audit = job.directory / "row_dispositions.jsonl"
    job.exclusion_audit.write_text(
        json.dumps(
            {
                "row_id": "row-1",
                "disposition": "HIERARCHY_AGGREGATE_EXCLUDED",
                "reason_code": "HIERARCHY_AGGREGATE_POLICY",
                "rule_id": None,
                "file_id": "file-1",
                "safe_basename": "source.xlsx",
                "sheet_name": "Лист 1",
                "row_number": 12,
                "position_code": "1.2",
                "row_role": "aggregate",
                "hazard_flags": ["INVALID_NUMBER"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    response = test_client.get(
        f"/api/drawing-card/jobs/{job.job_id}/audit/exclusions?page=1&page_size=10"
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "row_id": "row-1",
            "disposition": "HIERARCHY_AGGREGATE_EXCLUDED",
            "reason_code": "HIERARCHY_AGGREGATE_POLICY",
            "rule_id": None,
            "filename": "source.xlsx",
            "sheet_name": "Лист 1",
            "row_number": 12,
            "position_code": "1.2",
            "row_role": "aggregate",
            "hazard_flags": ["INVALID_NUMBER"],
        }
    ]
    assert str(private_root) not in response.text


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


@pytest.mark.parametrize("suffix", (".ods", ".pdf"))
def test_create_rejects_ods_and_pdf_with_supported_formats_copy(client, suffix: str) -> None:
    test_client, service, _ = client
    response = test_client.post("/api/drawing-card/jobs", files=_files(name=f"source{suffix}"))

    assert response.status_code == 400
    assert response.json() == {
        "error": "Неподдерживаемый тип файла. Загрузите Excel-файл (.xlsx, .xlsm или .xlsb)"
    }
    assert service.created_job_ids == []


def test_result_download_uses_localized_utf8_filename_and_keeps_private_artifact(client) -> None:
    test_client, service, private_root = client
    created = test_client.post("/api/drawing-card/jobs", data={"period": "2026-07"}, files=_files())
    job = service.get_job(created.json()["job_id"])
    job.result = job.directory / "drawing-card.xlsx"
    job.result.write_bytes(b"PK\x03\x04result")
    job.status = "ready"

    response = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/result")

    assert response.status_code == 200
    assert job.result.name == "drawing-card.xlsx"
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    assert (
        "filename*=UTF-8''%D0%9E%D1%82%D1%87%D1%91%D1%82%20%D0%BF%D0%BE%20"
        "%D0%BE%D1%81%D1%82%D0%B0%D1%82%D0%BA%D0%B0%D0%BC%20%D0%B7%D0%B0%20"
        "%D0%B8%D1%8E%D0%BB%D1%8C%202026.xlsx"
    ) in response.headers["content-disposition"]
    assert str(private_root) not in response.text


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
    assert "ZIP_SIGNATURES.some" in response.text
    assert "OLE_SIGNATURE" not in response.text
    assert "Файл «${name}» не является корректной Excel-книгой" in response.text
    assert "existingCard.files[0]" in response.text


def test_drawing_card_assets_keep_recoverable_review_state_and_use_category_select(client) -> None:
    test_client, _, _ = client
    page = test_client.get("/drawing-card")
    script = test_client.get("/static/drawing-card.js")
    review_script = test_client.get("/static/drawing-card-review.js")

    assert page.status_code == 200
    assert script.status_code == 200
    assert review_script.status_code == 200
    assert '<select class="category-input"' in review_script.text
    assert 'class="category-input" type="text"' not in review_script.text
    assert "sessionStorage" in script.text
    assert "currentJobId" in script.text
    assert "currentReviewPage" in script.text
    assert "operation.value" in script.text
    assert "period.value" in script.text
    assert "sourceFiles.files.length" in script.text
    assert "/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}" in script.text
    assert "error.status === 404" in script.text
    assert "Уже загружено для текущего отчёта" in script.text
    assert "category.focus()" in review_script.text
    assert "selected_category" in review_script.text
    assert 'class="apply-cluster-action approve-action">Применить</button>' in review_script.text
    assert 'class="reject-cluster-action danger-action">Отклонить</button>' in review_script.text
    assert 'category.value === state.proposed ? "approve" : "change_category"' in review_script.text
    assert "renderJob: (payload, reviewPage) => renderJob(payload, reviewPage)" in script.text
    assert review_script.text.count("await this.renderJob(payload, this.page);") == 2
    assert "extractPeriodFromFilename" in script.text
    assert 'payload.status === "blocked"' in script.text
    assert "Отчёт не сформирован" in script.text
    assert "blocking_reasons" in script.text
    assert 'id="job-issues"' in page.text
    assert "Подготовка запущена. Следующий шаг" not in script.text


def test_drawing_card_page_offers_only_detected_periods(client) -> None:
    test_client, _, _ = client

    response = test_client.get("/drawing-card")

    assert response.status_code == 200
    assert '<select id="period" name="period"' in response.text
    assert '<option value="">Последний найденный период</option>' in response.text
    assert "Доступны только периоды, найденные в выбранных файлах." in response.text
    assert 'type="text" maxlength="64"' not in response.text


def test_period_discovery_route_unions_files_and_uses_russian_labels(client) -> None:
    test_client, _, _ = client
    response = test_client.post(
        "/api/drawing-card/periods",
        files=[
            ("sources", _files("КС-2 2026-06.xlsx")[0][1]),
            ("sources", _files("0906 КС-6а июль 31_2026.xlsb")[0][1]),
        ],
    )

    assert response.status_code == 200
    assert response.json()["periods"] == [
        {"value": "2026-06", "label": "июнь 2026"},
        {"value": "2026-07", "label": "июль 2026"},
    ]
    assert response.json()["latest"] == "2026-07"


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


def test_inline_review_exposes_the_eight_original_categories_in_russian(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])

    response = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")

    assert response.status_code == 200
    assert response.json()["categories"] == [
        {
            "value": category.value,
            "label": CATEGORY_DISPLAY_NAMES[category],
            "target_unit": target_unit,
        }
        for category, target_unit in zip(
            CATEGORY_ORDER,
            ("шт", "м3", "т", "шт", "м", "шт", "м", "м"),
            strict=True,
        )
    ]
    assert len(response.json()["categories"]) == 8


@pytest.mark.parametrize("action", ["approve", "cost_only"])
def test_inline_review_accepts_approve_and_cost_only_with_selected_category(
    client, action: str
) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])

    response = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/items/review-row-1",
        json={"action": action, "category": "low_current_cable"},
    )
    page = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")

    assert response.status_code == 200
    assert service.get_job(job.job_id).inline_approvals["review-row-1"].action == action
    assert page.json()["items"][0]["decision"] == (
        "approved" if action == "approve" else "cost_only"
    )
    assert page.json()["items"][0]["selected_category"] == "low_current_cable"


def test_inline_review_rejects_category_outside_original_eight(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])

    response = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/items/review-row-1",
        json={"action": "approve", "category": "arbitrary_category"},
    )

    assert response.status_code == 400
    assert response.json() == {"error": "Выберите допустимое решение и категорию"}


@pytest.mark.parametrize("final_action", ["approve", "cost_only"])
def test_changed_category_can_be_followed_by_a_final_approval_action(
    client, final_action: str
) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])
    url = f"/api/drawing-card/jobs/{job.job_id}/review/items/review-row-1"

    changed = test_client.put(
        url,
        json={"action": "change_category", "category": "concrete_works"},
    )
    finalized = test_client.put(
        url,
        json={"action": final_action, "category": "concrete_works"},
    )
    page = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")

    assert changed.status_code == 200
    assert finalized.status_code == 200
    assert page.json()["items"][0]["decision"] == (
        "approved" if final_action == "approve" else "cost_only"
    )
    assert page.json()["items"][0]["selected_category"] == "concrete_works"
    assert page.json()["items"][0]["target_unit"] == "м3"


def test_changed_category_is_shown_as_draft_then_as_accepted_after_refetch(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])
    url = f"/api/drawing-card/jobs/{job.job_id}/review/items/review-row-1"

    changed = test_client.put(
        url,
        json={"action": "change_category", "category": "concrete_works"},
    )
    draft = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")
    accepted = test_client.put(
        url,
        json={"action": "approve", "category": "concrete_works"},
    )
    refetched = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")

    assert changed.status_code == 200
    assert draft.json()["items"][0] == {
        "review_id": "review-row-1",
        "work_name": "Монтаж контрольного кабеля",
        "category": "low_current_cable",
        "category_label": "Прокладка кабеля, провода (Слаботочные сети)",
        "proposed_category": "low_current_cable",
        "proposed_category_label": "Прокладка кабеля, провода (Слаботочные сети)",
        "selected_category": "concrete_works",
        "selected_category_label": "Бетонные работы",
        "quantity": "12",
        "source_unit": "м",
        "target_unit": "м3",
        "total_cost": "3500",
        "confidence": 0.72,
        "decision": "change_category",
    }
    assert accepted.status_code == 200
    assert refetched.json()["items"][0]["selected_category"] == "concrete_works"
    assert refetched.json()["items"][0]["selected_category_label"] == "Бетонные работы"
    assert refetched.json()["items"][0]["target_unit"] == "м3"
    assert refetched.json()["items"][0]["decision"] == "approved"


def test_reject_keeps_the_proposed_category_and_target_unit(client) -> None:
    test_client, service, _ = client
    created = test_client.post("/api/drawing-card/jobs", files=_files())
    job = _review_job(service, created.json()["job_id"])

    response = test_client.put(
        f"/api/drawing-card/jobs/{job.job_id}/review/items/review-row-1",
        json={"action": "reject"},
    )
    page = test_client.get(f"/api/drawing-card/jobs/{job.job_id}/review/items")

    assert response.status_code == 200
    assert page.json()["items"][0]["decision"] == "rejected"
    assert page.json()["items"][0]["selected_category"] is None
    assert page.json()["items"][0]["target_unit"] == "м"

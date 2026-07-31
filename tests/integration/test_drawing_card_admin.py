"""Black-box HTTP contract for drawing-card admin routes."""

from __future__ import annotations

import json
import subprocess
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
    assert "hasZipSignature(bytes)" in response.text
    assert "OLE_SIGNATURE" not in response.text
    assert "Файл «${name}» не является корректной Excel-книгой" in response.text
    assert "existingCard.files[0]" in response.text


def test_drawing_card_assets_keep_recoverable_review_state_and_use_category_select(client) -> None:
    test_client, _, _ = client
    page = test_client.get("/drawing-card")
    script = test_client.get("/static/drawing-card.js")

    assert page.status_code == 200
    assert script.status_code == 200
    assert '<select class="category-input"' in page.text
    assert 'class="category-input" type="text"' not in page.text
    assert "sessionStorage" in script.text
    assert "currentJobId" in script.text
    assert "currentPage" in script.text
    assert "operation.value" in script.text
    assert "period.value" in script.text
    assert "sourceFiles.files.length" in script.text
    assert "/api/drawing-card/jobs/${encodeURIComponent(currentJobId)}" in script.text
    assert "response.status === 404" in script.text
    assert "Файлы нужно выбрать повторно" in script.text
    assert 'editor.querySelector("select").focus()' in script.text
    assert "selectedCategory" in script.text


def test_drawing_card_page_offers_only_detected_periods(client) -> None:
    test_client, _, _ = client

    response = test_client.get("/drawing-card")

    assert response.status_code == 200
    assert '<select id="period" name="period"' in response.text
    assert '<option value="">Последний найденный период</option>' in response.text
    assert "Доступны только периоды, найденные в выбранных файлах." in response.text
    assert 'type="text" maxlength="64"' not in response.text


def test_drawing_card_asset_derives_detected_period_options() -> None:
    asset = (
        Path(__file__).parents[2]
        / "src"
        / "report_processor"
        / "admin_panel"
        / "assets"
        / "drawing-card.js"
    )
    script = """
const fs = require("node:fs");
const listeners = {};
const inert = { addEventListener() {} };
const period = {
  value: "",
  options: [],
  replaceChildren(...options) { this.options = options; },
  append(option) { this.options.push(option); },
};
const sources = {
  files: [
    { name: "0906 КС-6а июль 31_2026.xlsb" },
    { name: "КС-2 2026-06.xlsx" },
  ],
  addEventListener(name, callback) { listeners[name] = callback; },
};
global.Option = class Option {
  constructor(text, value) { this.text = text; this.value = value; }
};
global.document = {
  querySelector(selector) {
    return selector === "#sources" ? sources : selector === "#period" ? period : inert;
  },
  querySelectorAll() { return []; },
};
eval(fs.readFileSync(process.argv[1], "utf8"));
listeners.change();
console.log(JSON.stringify({ value: period.value, options: period.options }));
"""

    result = subprocess.run(
        ["node", "-e", script, str(asset)], check=True, capture_output=True, text=True
    )

    assert json.loads(result.stdout) == {
        "value": "2026-07",
        "options": [
            {"text": "Последний найденный период", "value": ""},
            {"text": "июнь 2026", "value": "2026-06"},
            {"text": "июль 2026", "value": "2026-07"},
        ],
    }


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
        {"value": category.value, "label": CATEGORY_DISPLAY_NAMES[category]}
        for category in CATEGORY_ORDER
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

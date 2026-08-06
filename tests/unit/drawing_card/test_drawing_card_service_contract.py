"""Public contract for the private drawing-card job service."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_processor.admin_panel.drawing_card_presentation import drawing_card_job_payload
from report_processor.admin_panel.drawing_card_service import _RESULT_NAME, DrawingCardService
from report_processor.drawing_card.output.contract import (
    CARD_HEADERS,
    COST_FORMAT,
    FRACTIONAL_QUANTITY_FORMAT,
    INTEGER_QUANTITY_FORMAT,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "drawing_card"


def _source(name: str = "source.xlsx") -> tuple[str, bytes]:
    return name, (FIXTURES / "demo_source.xlsx").read_bytes()


def _service(tmp_path: Path) -> DrawingCardService:
    return DrawingCardService(tmp_path / "private-workspaces")


@pytest.mark.parametrize("count", (1, 32))
def test_create_accepts_the_inclusive_source_count_boundary(tmp_path: Path, count: int) -> None:
    service = _service(tmp_path)
    job = service.create_job(sources=[_source(f"source-{index}.xlsx") for index in range(count)])

    assert job.status in {"processing", "review_required", "ready", "blocked", "failed"}
    assert job.job_id


@pytest.mark.parametrize("count", (0, 33))
def test_create_rejects_source_counts_outside_the_contract(tmp_path: Path, count: int) -> None:
    service = _service(tmp_path)

    with pytest.raises(ValueError):
        service.create_job(sources=[_source(f"source-{index}.xlsx") for index in range(count)])


@pytest.mark.parametrize("suffix", (".xlsx", ".xlsm", ".xlsb"))
def test_create_accepts_supported_excel_suffixes(tmp_path: Path, suffix: str) -> None:
    job = _service(tmp_path).create_job(sources=[_source(f"source{suffix}")])

    assert job.job_id


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("archive.zip", b"PK\x03\x04zip"),
        ("not-a-workbook.xlsx", b"not-an-excel-container"),
        ("../private.xlsx", b"PK\x03\x04workbook"),
        ("C:\\private.xlsx", b"PK\x03\x04workbook"),
    ],
)
def test_create_rejects_archives_invalid_magic_and_path_like_names(
    tmp_path: Path, name: str, content: bytes
) -> None:
    with pytest.raises(ValueError):
        _service(tmp_path).create_job(sources=[(name, content)])


def test_create_rejects_legacy_ole_payload_for_xlsb(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _service(tmp_path).create_job(
            sources=[("legacy.xlsb", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1binary-workbook")]
        )


@pytest.mark.parametrize("suffix", (".ods", ".pdf"))
def test_create_rejects_ods_and_pdf_sources(tmp_path: Path, suffix: str) -> None:
    with pytest.raises(ValueError, match="unsupported workbook type"):
        _service(tmp_path).create_job(sources=[_source(f"source{suffix}")])


@pytest.mark.parametrize(
    ("period", "expected_name"),
    (
        ("2026-07", "Отчёт по остаткам за июль 2026.xlsx"),
        (None, "Отчёт по остаткам.xlsx"),
    ),
)
def test_result_keeps_private_name_and_uses_localized_public_name(
    tmp_path: Path, period: str | None, expected_name: str
) -> None:
    service = _service(tmp_path)
    job = service.create_job(sources=[_source()], period=period)
    job.result = job.directory / _RESULT_NAME
    job.result.write_bytes(b"PK\x03\x04result")
    job.status = "ready"

    result, name = service.get_result(job.job_id)

    assert result.name == _RESULT_NAME
    assert name == expected_name


def test_update_requires_an_existing_xlsx_card_and_period_is_optional(tmp_path: Path) -> None:
    service = _service(tmp_path)
    source = [_source()]

    with pytest.raises(ValueError):
        service.create_job(sources=source, mode="update")
    with pytest.raises(ValueError):
        service.create_job(
            sources=source,
            mode="update",
            existing_name="existing.xlsm",
            existing_content=(FIXTURES / "default_template.xlsx").read_bytes(),
        )

    job = service.create_job(
        sources=source,
        mode="update",
        existing_name="existing.xlsx",
        existing_content=(FIXTURES / "default_template.xlsx").read_bytes(),
        period="2026-07",
    )
    assert job.job_id
    assert job.period == "2026-07"


@pytest.mark.parametrize("period", ("июль 26", "июнь 2026 июль 2026", "2026-13"))
def test_create_rejects_invalid_or_ambiguous_periods(tmp_path: Path, period: str) -> None:
    with pytest.raises(ValueError):
        _service(tmp_path).create_job(sources=[_source()], period=period)


def test_jobs_keep_workspace_private_and_disable_rag_network(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("socket.create_connection", lambda *args, **kwargs: pytest.fail("network"))
    service = _service(tmp_path)
    job = service.create_job(sources=[_source()])
    serialized = str(job)

    assert str(tmp_path) not in serialized
    assert "rag" not in serialized.casefold() or "off" in serialized.casefold()


def test_manifest_paths_survive_an_aliased_workspace_parent(tmp_path: Path) -> None:
    actual_parent = tmp_path / "actual"
    actual_parent.mkdir()
    aliased_parent = tmp_path / "alias"
    aliased_parent.symlink_to(actual_parent, target_is_directory=True)

    job = DrawingCardService(aliased_parent / "private-workspaces").create_job(sources=[_source()])

    assert job.job_id


def test_presenter_exposes_only_controlled_job_fields(tmp_path: Path) -> None:
    job = _service(tmp_path).create_job(sources=[_source()])
    payload = drawing_card_job_payload(job)

    assert set(payload) == {
        "active_step",
        "attempt",
        "can_cancel",
        "can_retry",
        "job_id",
        "mode",
        "period",
        "phase",
        "progress",
        "started_at",
        "status",
        "summary",
        "terminal_cause",
        "updated_at",
        "warnings",
        "issues",
        "blocking_reasons",
        "result_url",
        "review_url",
        "can_upload_review",
        "funnel",
        "schema_recognition",
        "exclusion_audit_url",
    }
    assert payload["mode"] == "create"
    assert payload["period"] is None
    assert payload["active_step"] == "sources"
    assert payload["phase"] == job.phase
    assert set(payload["progress"]) == {
        "processed_files",
        "total_files",
        "processed_rows",
        "total_rows",
    }
    assert payload["attempt"] == job.attempt
    assert payload["can_cancel"] is (job.status in {"queued", "processing"})
    assert payload["can_retry"] is (job.status in {"cancelled", "failed", "blocked"})
    assert set(payload["summary"]) == {
        "source_files",
        "extracted_rows",
        "card_rows",
        "manual_review",
    }
    assert payload["funnel"]["terminal_dispositions"] == payload["funnel"]["extracted_rows"]
    assert all(
        item["recognition"] in {"recognized", "uncertain", "unsupported"}
        for item in payload["schema_recognition"]
    )
    assert payload["exclusion_audit_url"].endswith("/audit/exclusions")
    assert str(tmp_path) not in str(payload)


def test_output_contract_keeps_required_columns_and_numeric_formats() -> None:
    assert CARD_HEADERS == (
        "Шифр чертежа",
        "Наименование этапа работ",
        "Ед. изм.",
        "Количество",
        "Общая стоимость, млн руб.",
        "По договору — объём",
        "По договору — стоимость, млн руб.",
        "Выполнено за весь период — объём",
        "Выполнено за весь период — стоимость, млн руб.",
    )
    assert INTEGER_QUANTITY_FORMAT == "0.00"
    assert FRACTIONAL_QUANTITY_FORMAT == "0.00"
    assert COST_FORMAT == "#,##0.00"

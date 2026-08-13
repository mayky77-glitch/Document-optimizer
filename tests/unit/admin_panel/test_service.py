import gc
import hashlib
import json
import tracemalloc
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from report_processor.admin_panel import service as admin_service
from report_processor.admin_panel.service import MAX_MANUAL_DISCREPANCY_DECISIONS, AdminPanelService
from report_processor.domain.exceptions import UnsupportedExcelFormatError
from report_processor.domain.statuses import StatusCode


def _manual_result():
    normalized = SimpleNamespace(
        rows=(
            SimpleNamespace(
                source_row_id="source-a",
                work_name="Монтаж трубопровода",
                position_code=None,
            ),
            SimpleNamespace(
                source_row_id="source-b",
                work_name="Устройство бетонной подготовки",
                position_code=None,
            ),
        )
    )
    matches = (
        SimpleNamespace(
            result_id="target-stage",
            target_row=SimpleNamespace(stage="13.1. Подготовительные работы", work_name=None),
        ),
    )
    suggestion = SimpleNamespace(
        target_identity="target-stage",
        candidates=(
            SimpleNamespace(source_identity="source-a", score=0.91),
            SimpleNamespace(source_identity="source-b", score=0.82),
        ),
    )
    return SimpleNamespace(
        artifacts={
            "normalized": normalized,
            "matches": matches,
            "stage_relation_suggestions": (suggestion,),
        },
        state="MANUAL_REVIEW_REQUIRED",
        exit_code=3,
        warnings=(),
        errors=(),
    )


def _manual_discrepancy_result():
    issues = tuple(
        SimpleNamespace(
            issue_id=f"issue-{index}",
            code="AMBIGUOUS" if index < 3 else "UNMATCHED",
            severity="manual_review",
            message="Связь требует ручной проверки" if index < 3 else "Позиция не сопоставлена",
        )
        for index in range(4)
    )
    return SimpleNamespace(
        artifacts={
            "quality_report": SimpleNamespace(
                summary={"manual_review_issue_count": 4}, issues=issues
            )
        },
        state="MANUAL_REVIEW_REQUIRED",
        exit_code=3,
        warnings=(),
        errors=(),
    )


def test_private_job_requires_each_manual_relation_before_safe_download(tmp_path: Path) -> None:
    source_content = b"PK\x03\x04source"
    target_content = b"PK\x03\x04target"

    def execute(job):
        assert job.source.read_bytes() == source_content
        assert job.target.read_bytes() == target_content
        return _manual_result()

    service = AdminPanelService(tmp_path / "jobs", execute=execute)
    job = service.create_job(
        source_name="source.xlsx",
        source_content=source_content,
        target_name="target.xlsx",
        target_content=target_content,
        stage="13.1",
    )

    assert job.status == "review_required"
    assert len(job.suggestions) == 2
    assert job.output is None
    assert job.source.read_bytes() == source_content
    assert job.target.read_bytes() == target_content
    assert job.directory.stat().st_mode & 0o777 == 0o700
    assert job.source.stat().st_mode & 0o777 == 0o600

    first, second = (item["suggestion_id"] for item in job.suggestions)
    service.record_decision(job_id=job.job_id, suggestion_id=first, decision="fit")
    with pytest.raises(KeyError):
        service.get_result(job.job_id)
    service.record_decision(job_id=job.job_id, suggestion_id=second, decision="not_fit")

    result_path, result_name = service.get_result(job.job_id)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_name == "review-journal.json"
    assert [item["decision"] for item in payload["decisions"]] == ["fit", "not_fit"]
    assert str(tmp_path) not in result_path.read_text(encoding="utf-8")
    assert payload["statement"].startswith("Решения оператора записаны отдельно")


def test_omitted_stage_auto_selects_the_only_structurally_valid_target_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        admin_service,
        "_structurally_valid_target_stages",
        lambda _target, _digest: ("14.2",),
    )
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    job = service.create_job(
        source_name="source.xlsx",
        source_content=b"PK\x03\x04source",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage=None,
    )

    assert job.stage == "14.2"


@pytest.mark.parametrize(
    ("stages", "code"),
    (((), "not_found"), (("13.1", "14.2"), "selection_required")),
)
def test_omitted_stage_stops_before_execution_when_selection_is_not_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stages: tuple[str, ...], code: str
) -> None:
    monkeypatch.setattr(
        admin_service,
        "_structurally_valid_target_stages",
        lambda _target, _digest: stages,
    )
    executed = []
    service = AdminPanelService(tmp_path / "jobs", execute=lambda job: executed.append(job))

    with pytest.raises(admin_service.TargetStageSelectionError) as error:
        service.create_job(
            source_name="source.xlsx",
            source_content=b"PK\x03\x04source",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage=None,
        )

    assert error.value.code == code
    expected_options = stages if code == "selection_required" else ()
    assert error.value.stage_options == expected_options
    assert executed == []
    assert not [path for path in (tmp_path / "jobs").iterdir() if path.is_dir()]


def test_explicit_missing_stage_stops_before_review_when_api_validation_is_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        admin_service,
        "_structurally_valid_target_stages",
        lambda _target, _digest: ("13.1",),
    )
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(admin_service.TargetStageSelectionError) as error:
        service.create_job(
            source_name="source.xlsx",
            source_content=b"PK\x03\x04source",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="14.2",
            validate_target_stage=True,
        )

    assert error.value.code == "not_found"
    assert not [path for path in (tmp_path / "jobs").iterdir() if path.is_dir()]


def test_workbook_domain_errors_become_not_found_and_remove_unregistered_job_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_open(_request):
        raise UnsupportedExcelFormatError(StatusCode.UNSUPPORTED_EXCEL_FORMAT, "private detail")

    monkeypatch.setattr("report_processor.excel.open_dual_workbook", fail_open)
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(admin_service.TargetStageSelectionError, match="not_found") as error:
        service.create_job(
            source_name="source.xlsx",
            source_content=b"PK\x03\x04source",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04malformed",
            stage=None,
        )

    assert error.value.code == "not_found"
    assert not [path for path in (tmp_path / "jobs").iterdir() if path.is_dir()]


def test_structural_stage_discovery_opens_the_workbook_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = []
    discovered = []
    monkeypatch.setattr(
        "report_processor.excel.open_dual_workbook",
        lambda request: opened.append(request) or nullcontext(object()),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_target.structurally_valid_reconciliation_stages",
        lambda session, *, maximum: discovered.append((session, maximum)) or ("Секция (А)",),
    )
    target = tmp_path / "target.xlsx"
    target.write_bytes(b"PK\x03\x04target")

    stages = admin_service._structurally_valid_target_stages(target, "digest")

    assert stages == ("Секция (А)",)
    assert len(opened) == len(discovered) == 1


def test_stage_selection_limits_an_overlarge_ambiguous_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        admin_service,
        "_structurally_valid_target_stages",
        lambda _target, _digest: tuple(f"Этап {index}" for index in range(65)),
    )
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(admin_service.TargetStageSelectionError) as error:
        service.create_job(
            source_name="source.xlsx",
            source_content=b"PK\x03\x04source",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage=None,
        )

    assert error.value.code == "selection_limit_exceeded"
    assert error.value.stage_options == ()
    assert not [path for path in (tmp_path / "jobs").iterdir() if path.is_dir()]


def test_suggestion_group_decision_is_atomic_and_replay_safe(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())
    job = service.create_job(
        source_name="source.xlsx",
        source_content=b"PK\x03\x04source",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )
    from report_processor.admin_panel.presentation import job_payload

    group = job_payload(job)["suggestion_review_groups"][0]
    selected = group["candidates"][0]["suggestion_id"]
    with pytest.raises(ValueError):
        service.record_suggestion_group_decision(
            job_id=job.job_id, group_id=group["group_id"], suggestion_id="unknown", decision="apply"
        )
    assert job.decisions == []
    service.record_suggestion_group_decision(
        job_id=job.job_id, group_id=group["group_id"], suggestion_id=selected, decision="apply"
    )
    assert {item["suggestion_id"] for item in job.decisions} == {
        item["suggestion_id"] for item in job.suggestions
    }
    assert [item["decision"] for item in job.decisions].count("fit") == 1
    with pytest.raises(ValueError):
        service.record_suggestion_group_decision(
            job_id=job.job_id, group_id=group["group_id"], suggestion_id=selected, decision="apply"
        )


def test_manual_discrepancy_groups_require_exact_atomic_decisions(tmp_path: Path) -> None:
    service = AdminPanelService(
        tmp_path / "jobs", execute=lambda _job: _manual_discrepancy_result()
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=b"PK\x03\x04source",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )

    from report_processor.admin_panel.presentation import job_payload
    from report_processor.admin_panel.review_presentation import manual_review_groups

    groups = manual_review_groups(job.discrepancies, job.decisions, include_ids=True)
    assert job.status == "review_required"
    assert len(groups) == 2
    first = groups[0]
    ids = first["discrepancy_ids"]
    with pytest.raises(ValueError, match="exactly"):
        service.record_manual_discrepancy_decision(
            job_id=job.job_id,
            group_id=first["group_id"],
            discrepancy_ids=ids[:-1],
            decision="approve",
        )
    assert job.decisions == []
    with pytest.raises(ValueError, match="duplicate"):
        service.record_manual_discrepancy_decision(
            job_id=job.job_id,
            group_id=first["group_id"],
            discrepancy_ids=[ids[0], ids[0]],
            decision="approve",
        )
    assert job.decisions == []
    service.record_manual_discrepancy_decision(
        job_id=job.job_id,
        group_id=first["group_id"],
        discrepancy_ids=ids,
        decision="approve",
    )
    assert {item["discrepancy_id"] for item in job.decisions} == set(ids)
    with pytest.raises(ValueError, match="exactly"):
        service.record_manual_discrepancy_decision(
            job_id=job.job_id,
            group_id=first["group_id"],
            discrepancy_ids=ids,
            decision="approve",
        )
    remaining = job_payload(job)["manual_review_groups"]
    service.record_manual_discrepancy_decision(
        job_id=job.job_id,
        group_id=remaining[0]["group_id"],
        discrepancy_ids=None,
        decision="reject",
    )
    result_path, _ = service.get_result(job.job_id)
    journal = result_path.read_text(encoding="utf-8")
    assert job.unresolved_manual_discrepancy_ids == set()
    assert "source.xlsx" not in journal and str(tmp_path) not in journal


def test_manual_discrepancy_decision_rejects_oversized_request_before_mutation(
    tmp_path: Path,
) -> None:
    service = AdminPanelService(
        tmp_path / "jobs", execute=lambda _job: _manual_discrepancy_result()
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=b"PK\x03\x04source",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )

    with pytest.raises(ValueError, match="too many"):
        service.record_manual_discrepancy_decision(
            job_id=job.job_id,
            group_id="any-group",
            discrepancy_ids=["issue"] * (MAX_MANUAL_DISCREPANCY_DECISIONS + 1),
            decision="approve",
        )

    assert job.decisions == []


def test_failed_executor_removes_private_uploads_and_exposes_controlled_state(
    tmp_path: Path,
) -> None:
    def fail(_job):
        raise RuntimeError("sensitive internal failure")

    service = AdminPanelService(tmp_path / "jobs", execute=fail)
    job = service.create_job(
        source_name="source.xlsx",
        source_content=b"PK\x03\x04source",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )

    assert job.status == "failed"
    assert job.errors == ("PROCESSING_FAILED",)
    assert not job.directory.exists()
    with pytest.raises(KeyError):
        service.get_result(job.job_id)


@pytest.mark.parametrize("source_count", (1, 32))
def test_bulk_sources_accept_inclusive_bounds_and_preserve_upload_order(
    tmp_path: Path, source_count: int
) -> None:
    sources = [
        (f"source-{index:02d}.xlsx", b"PK\x03\x04" + str(index).encode())
        for index in range(1, source_count + 1)
    ]
    seen: list[tuple[bytes, ...]] = []

    def execute(job):
        seen.append(tuple(path.read_bytes() for path in job.sources))
        return _manual_result()

    service = AdminPanelService(tmp_path / "jobs", execute=execute)
    job = service.create_job(
        sources=sources,
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )

    assert seen == [tuple(content for _name, content in sources)]
    expected_paths = tuple(
        job.directory / f"source-{index:02d}.xlsx" for index in range(1, source_count + 1)
    )
    assert job.sources == expected_paths
    assert job.source == job.sources[0]
    assert job.source_digests == tuple(
        hashlib.sha256(content).hexdigest() for _name, content in sources
    )


@pytest.mark.parametrize("source_count", (0, 33))
def test_bulk_sources_reject_counts_outside_the_contract(tmp_path: Path, source_count: int) -> None:
    sources = [(f"source-{index}.xlsx", b"PK\x03\x04source") for index in range(source_count)]
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(ValueError, match="1 to 32"):
        service.create_job(
            sources=sources,
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="13.1",
        )


@pytest.mark.parametrize(
    "sources",
    (
        [("../private.xlsx", b"PK\x03\x04source")],
        [("source.xlsx", b"not-an-excel-container")],
        [("source.xlsx", b"PK\x03\x04source", b"unexpected")],
    ),
)
def test_bulk_sources_reject_unsafe_or_malformed_entries(tmp_path: Path, sources: object) -> None:
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(ValueError):
        service.create_job(
            sources=sources,
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="13.1",
        )


def test_legacy_single_source_remains_a_one_element_bulk_job(tmp_path: Path) -> None:
    source_content = b"PK\x03\x04source"
    seen: list[tuple[Path, ...]] = []

    def execute(job):
        seen.append(job.sources)
        return _manual_result()

    service = AdminPanelService(tmp_path / "jobs", execute=execute)
    job = service.create_job(
        source_name="legacy.xlsm",
        source_content=source_content,
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )

    assert seen == [(job.source,)]
    assert job.sources == (job.source,)
    assert job.source.read_bytes() == source_content


def test_bulk_and_legacy_inputs_cannot_be_combined(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(ValueError, match="sources or legacy"):
        service.create_job(
            sources=[("source.xlsx", b"PK\x03\x04source")],
            source_name="legacy.xlsx",
            source_content=b"PK\x03\x04legacy",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="13.1",
        )


def test_duplicate_source_content_is_rejected_even_when_names_differ(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    with pytest.raises(ValueError, match="duplicate source content"):
        service.create_job(
            sources=[
                ("first.xlsx", b"PK\x03\x04same"),
                ("second.xlsx", b"PK\x03\x04same"),
            ],
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="13.1",
        )


def test_completed_jobs_are_bounded_without_evicting_an_active_review(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path / "jobs", execute=lambda _job: _manual_result())

    active = service.create_job(
        source_name="active.xlsx",
        source_content=b"PK\x03\x04active",
        target_name="target.xlsx",
        target_content=b"PK\x03\x04target",
        stage="13.1",
    )
    assert active.status == "review_required"

    def complete_job(index: int) -> None:
        job = service.create_job(
            source_name=f"completed-{index}.xlsx",
            source_content=b"PK\x03\x04completed",
            target_name="target.xlsx",
            target_content=b"PK\x03\x04target",
            stage="13.1",
        )
        for suggestion in job.suggestions:
            service.record_decision(
                job_id=job.job_id,
                suggestion_id=suggestion["suggestion_id"],
                decision="fit",
            )

    tracemalloc.start()
    try:
        for index in range(80):
            complete_job(index)
        gc.collect()
        warmup_current, _ = tracemalloc.get_traced_memory()

        for index in range(80, 160):
            complete_job(index)
        gc.collect()
        retained_current, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert active.job_id in service.jobs
    assert len(service.jobs) < 65
    assert retained_current - warmup_current < 200_000

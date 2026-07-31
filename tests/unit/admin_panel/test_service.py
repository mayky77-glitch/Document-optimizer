import gc
import hashlib
import json
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import pytest

from report_processor.admin_panel.service import AdminPanelService


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

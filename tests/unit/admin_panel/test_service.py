import json
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

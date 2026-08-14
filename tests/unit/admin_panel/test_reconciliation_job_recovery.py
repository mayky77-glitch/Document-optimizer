"""Durable, fail-closed recovery contracts for reconciliation jobs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from report_processor.admin_panel.reconciliation_execution import ReconciliationReviewResult
from report_processor.admin_panel.reconciliation_target import ReconciliationTargetIdentity
from report_processor.admin_panel.service import AdminJob, AdminPanelService


def _upload(value: str) -> bytes:
    return b"PK\x03\x04" + value.encode()


def _ready_service(workspace: Path) -> AdminPanelService:
    def execute(job):
        output = job.directory / "result.xlsx"
        output.write_bytes(b"result")
        return output

    return AdminPanelService(workspace, execute=execute)


def _ready_job(service: AdminPanelService):
    return service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
    )


def test_ready_result_lazy_recovers_after_memory_pruning(tmp_path: Path, monkeypatch) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    monkeypatch.setattr("report_processor.admin_panel.service.MAX_RETAINED_TERMINAL_JOBS", 0)

    service._prune_terminal_jobs()
    assert job.job_id not in service.jobs

    restored = service.get_job(job.job_id)

    assert restored.status == "ready"
    assert restored.result_available is True
    assert restored.output is not None and restored.output.read_bytes() == b"result"


def test_restart_rebuilds_review_from_immutable_uploads(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "jobs"
    original = AdminPanelService(
        workspace,
        execute=lambda _job: ReconciliationReviewResult(state=object(), source_batch=None),
    )
    job = original.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
    )
    assert job.status == "review_required"
    observed: list[str] = []

    def rebuild(restored, _feedback):
        observed.append(restored.job_id)
        return ReconciliationReviewResult(state=object(), source_batch=None)

    monkeypatch.setattr("report_processor.admin_panel.service.prepare_review", rebuild)
    recovered = AdminPanelService(workspace)

    assert observed == [job.job_id]
    assert recovered.get_job(job.job_id).status == "review_required"
    manifest = recovered._job_store.load(job.job_id)
    assert manifest is not None and "summary" not in manifest and "discrepancies" not in manifest


def test_tampered_or_symlinked_ready_output_is_not_recovered(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    valid = _ready_job(service)
    tampered = _ready_job(service)
    assert tampered.output is not None
    tampered.output.write_bytes(b"changed")
    bad = _ready_job(service)
    assert bad.output is not None
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"outside")
    bad.output.unlink()
    bad.output.symlink_to(outside)
    changed_input = _ready_job(service)
    changed_input.source.write_bytes(b"changed-input")

    recovered = AdminPanelService(tmp_path / "jobs")

    assert recovered.get_job(valid.job_id).result_available is True
    with pytest.raises(KeyError):
        recovered.get_job(tampered.job_id)
    with pytest.raises(KeyError):
        recovered.get_job(bad.job_id)
    with pytest.raises(KeyError):
        recovered.get_job(changed_input.job_id)


def test_passed_verification_without_an_artifact_recovers(tmp_path: Path) -> None:
    service = AdminPanelService(tmp_path / "jobs")
    directory = service.workspace_root / "verify-only"
    directory.mkdir()
    source = directory / "source.xlsx"
    target = directory / "target.xlsx"
    source.write_bytes(_upload("source"))
    target.write_bytes(_upload("target"))
    job = AdminJob(
        job_id="verify-only",
        directory=directory,
        source=source,
        target=target,
        stage="13.1",
        mode="write",
        source_digest=hashlib.sha256(source.read_bytes()).hexdigest(),
        target_digest=hashlib.sha256(target.read_bytes()).hexdigest(),
        target_identity_digest=ReconciliationTargetIdentity(
            hashlib.sha256(target.read_bytes()).hexdigest(), "13.1"
        ).target_identity_digest,
        sources=(source,),
        source_digests=(hashlib.sha256(source.read_bytes()).hexdigest(),),
        operation="verify",
        status="ready",
        verification_status="pass",
        verification_message="verified",
    )
    service.jobs[job.job_id] = job
    service._persist_job(job)

    restored = AdminPanelService(service.workspace_root).get_job(job.job_id)

    assert restored.status == "ready"
    assert restored.output is None
    assert restored.verification_status == "pass"


def test_recovery_rejects_output_swapped_after_descriptor_validation(
    tmp_path: Path, monkeypatch
) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    assert job.output is not None
    outside = tmp_path / "outside.xlsx"
    outside.write_bytes(b"outside")
    from report_processor.admin_panel import service as service_module

    original = service_module._current_output_facts
    swapped = False

    def validate_then_swap(path):
        nonlocal swapped
        result = original(path)
        if not swapped:
            swapped = True
            path.unlink()
            outside.replace(path)
        return result

    monkeypatch.setattr(service_module, "_current_output_facts", validate_then_swap)
    recovered = AdminPanelService(tmp_path / "jobs")

    with pytest.raises(KeyError):
        recovered.get_result(job.job_id)
    assert job.output.read_bytes() == b"outside"


def test_get_result_rejects_replacement_after_ready_recovery(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    restored = AdminPanelService(tmp_path / "jobs").get_job(job.job_id)
    assert restored.output is not None
    replacement = tmp_path / "replacement.xlsx"
    replacement.write_bytes(b"replacement")
    replacement.replace(restored.output)

    with pytest.raises(KeyError):
        AdminPanelService(tmp_path / "jobs").get_result(job.job_id)
    assert restored.output.read_bytes() == b"replacement"


def test_ready_manifest_without_result_name_is_not_recovered(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    manifest.pop("result_name")
    service._job_store.save(job.job_id, manifest)

    recovered = AdminPanelService(tmp_path / "jobs")

    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)


def test_v1_manifest_is_invalidated_before_recovery(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    manifest_path = job.directory / "job-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["contract"] = "AdminReconciliationJobManifest-1.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    recovered = AdminPanelService(tmp_path / "jobs")

    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)


def test_interrupted_apply_fails_closed_without_a_download(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    assert job.output is not None
    job.status = "applying"
    service._persist_job(job)

    recovered = AdminPanelService(tmp_path / "jobs")

    # An old/incomplete applying record has no immutable replay plan and is
    # deliberately invisible rather than being rerun or made downloadable.
    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)


def test_apply_manifest_never_contains_workbook_derived_feedback_values(tmp_path: Path) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    job.status = "applying"
    job.output = job.directory / "result.xlsx"
    job.output.write_bytes(b"result")
    job.output_identity = (job.output.stat().st_dev, job.output.stat().st_ino)
    job.output_digest = hashlib.sha256(job.output.read_bytes()).hexdigest()
    job.apply_manifest = {
        "output_path": "result.xlsx",
        "output_digest": job.output_digest,
        "output_identity": list(job.output_identity),
        "apply_key": "a" * 64,
        "payload_hash": "b" * 64,
    }
    service._persist_job(job)

    text = json.dumps(service._job_store.load(job.job_id), ensure_ascii=False)

    assert "feedback" not in text
    assert "distinctive work" not in text
    assert "distinctive-unit" not in text

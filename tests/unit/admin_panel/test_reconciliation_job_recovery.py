"""Durable, fail-closed recovery contracts for reconciliation jobs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from report_processor.admin_panel.reconciliation_execution import ReconciliationReviewResult
from report_processor.admin_panel.reconciliation_verification import VerificationResult
from report_processor.admin_panel.service import AdminPanelService


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


def test_passed_verification_without_an_artifact_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = AdminPanelService(tmp_path / "jobs")
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_verification.verify_reconciliation",
        lambda *_args: VerificationResult("passed", "verified", 1, 0),
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
        operation="verify",
    )

    restored = AdminPanelService(service.workspace_root).get_job(job.job_id)

    assert restored.status == "ready"
    assert restored.output is None
    assert restored.verification_status == "passed"


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


@pytest.mark.parametrize(
    "mutation",
    (
        {"unexpected": "field"},
        {"status": "READY"},
        {"operation": "reconciliation"},
        {"result_name": None},
        {"result_name": "../result.xlsx"},
        {
            "output_path": None,
            "output_digest": None,
            "output_identity": None,
            "result_name": None,
        },
    ),
)
def test_recovery_rejects_noncanonical_manifest_envelope(
    tmp_path: Path, mutation: dict[str, object]
) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    manifest.update(mutation)
    (job.directory / "job-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(KeyError):
        AdminPanelService(tmp_path / "jobs").get_job(job.job_id)


@pytest.mark.parametrize(
    "mutation",
    (
        {"checked_row_count": True},
        {"failed_row_count": True},
        {"checked_row_count": 0, "failed_row_count": 1},
        {"checked_row_count": 1, "failed_row_count": 1},
        {"verification_status": "pass"},
        {"verification_status": "failed", "checked_row_count": 1, "failed_row_count": 1},
        {"verification_message": None},
    ),
)
def test_recovery_rejects_noncanonical_verification_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: dict[str, object]
) -> None:
    service = AdminPanelService(tmp_path / "jobs")
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_verification.verify_reconciliation",
        lambda *_args: VerificationResult("passed", "verified", 1, 0),
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
        operation="verify",
    )
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    manifest.update(mutation)
    (job.directory / "job-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(KeyError):
        AdminPanelService(tmp_path / "jobs").get_job(job.job_id)


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


def test_v3_applying_manifest_is_rejected_before_writer_or_feedback_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _ready_service(tmp_path / "jobs")
    job = _ready_job(service)
    manifest_path = job.directory / "job-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        contract="AdminReconciliationJobManifest-3.0",
        status="applying",
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    invoked: list[str] = []
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review",
        lambda *_args: invoked.append("writer"),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_feedback_store.ReconciliationFeedbackStore.commit_apply",
        lambda *_args, **_kwargs: invoked.append("feedback"),
    )

    recovered = AdminPanelService(service.workspace_root)

    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)
    assert invoked == []


def test_interrupted_apply_fails_closed_without_a_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "jobs"
    service = AdminPanelService(
        workspace,
        execute=lambda _job: ReconciliationReviewResult(state=object(), source_batch=None),
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
    )
    assert job.status == "review_required" and job.output is None
    job.status = "applying"
    service._persist_job(job)
    orphan = job.directory / "result.xlsx"
    orphan.write_bytes(b"writer completed before the replay plan was durable")
    orphan.chmod(0o600)
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review",
        lambda *_args: pytest.fail("recovery must not retry the writer"),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.service.prepare_review",
        lambda *_args: pytest.fail("pre-evidence recovery must not rebuild review"),
    )

    recovered = AdminPanelService(workspace)

    restored = recovered.get_job(job.job_id)
    assert restored.status == "failed" and restored.output is None
    with pytest.raises(KeyError):
        recovered.get_result(job.job_id)
    assert orphan.read_bytes() == b"writer completed before the replay plan was durable"


@pytest.mark.parametrize("partial", ["output", "apply"])
def test_applying_manifest_rejects_partial_evidence_envelopes(tmp_path: Path, partial: str) -> None:
    workspace = tmp_path / "jobs"
    service = AdminPanelService(
        workspace,
        execute=lambda _job: ReconciliationReviewResult(state=object(), source_batch=None),
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
    )
    job.status = "applying"
    service._persist_job(job)
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    if partial == "output":
        output = job.directory / "result.xlsx"
        output.write_bytes(b"partial")
        output.chmod(0o600)
        job.output = output
        job.result_name = "optimized-report.xlsx"
        with pytest.raises(ValueError, match="status artifacts"):
            service._persist_job(job)
        job.output = None
        job.result_name = None
        manifest.update(
            output_path=output.name,
            output_digest=hashlib.sha256(output.read_bytes()).hexdigest(),
            output_identity=[output.stat().st_dev, output.stat().st_ino],
            result_name="optimized-report.xlsx",
        )
    else:
        job.apply_manifest = {}
        with pytest.raises(ValueError, match="status artifacts"):
            service._persist_job(job)
        job.apply_manifest = None
        manifest["apply"] = {}
    (job.directory / "job-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(KeyError):
        AdminPanelService(workspace).get_job(job.job_id)


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
        "evidence": {
            "contract": "ReconciliationApplyReplay-2.0",
            "catalog_digest": "c" * 64,
            "target_identity_digest": job.target_identity_digest,
            "calculation_digest": "d" * 64,
            "rules_hash": "e" * 64,
            "actionable": True,
            "decisions": [],
            "input_snapshots": ["apply-input-source-01.xlsx", "apply-input-target.xlsx"],
        },
    }
    service._persist_job(job)

    text = json.dumps(service._job_store.load(job.job_id), ensure_ascii=False)

    assert "feedback" not in text
    assert "distinctive work" not in text
    assert "distinctive-unit" not in text


def test_review_required_manifest_rejects_self_consistent_forged_output(tmp_path: Path) -> None:
    workspace = tmp_path / "jobs"
    service = AdminPanelService(
        workspace,
        execute=lambda _job: ReconciliationReviewResult(state=object(), source_batch=None),
    )
    job = service.create_job(
        source_name="source.xlsx",
        source_content=_upload("source"),
        target_name="target.xlsx",
        target_content=_upload("target"),
        stage="13.1",
    )
    assert job.status == "review_required"
    output = job.directory / "result.xlsx"
    output.write_bytes(b"forged but internally self-consistent")
    output.chmod(0o600)
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    manifest.update(
        output_path=output.name,
        output_digest=hashlib.sha256(output.read_bytes()).hexdigest(),
        output_identity=[output.stat().st_dev, output.stat().st_ino],
        result_name="optimized-report.xlsx",
    )
    (job.directory / "job-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    job.output = output
    job.result_name = "optimized-report.xlsx"
    assert job.result_available is False

    recovered = AdminPanelService(workspace)

    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)
    with pytest.raises(KeyError):
        recovered.get_result(job.job_id)

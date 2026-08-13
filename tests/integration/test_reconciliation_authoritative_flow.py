import threading
from decimal import Decimal
from hashlib import sha256

import pytest

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.admin_panel.reconciliation_execution import (
    ReconciliationApplyResult,
    _apply_plan,
    _feedback_records,
)
from report_processor.admin_panel.reconciliation_state import ReconciliationReviewState
from report_processor.admin_panel.reconciliation_target import _bindings, writer_calculations
from report_processor.admin_panel.service import (
    AdminJob,
    AdminPanelService,
    _copy_verified_snapshot,
)
from report_processor.calculation import calculate_matches
from report_processor.matching import MatchResult, MatchStatus
from report_processor.reconciliation_review import (
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def test_two_accepted_source_rows_contribute_once_to_one_target_aggregate() -> None:
    first = calculation_source_row("source-a:1", quantity=Decimal("2"), cost=Decimal("10"))
    second = calculation_source_row("source-b:1", quantity=Decimal("3"), cost=Decimal("15"))
    first_match = match_result(first, candidate_id="candidate-a", target_row_id="target-1")
    second_match = match_result(second, candidate_id="candidate-b", target_row_id="target-1")
    combined = MatchResult(
        result_id="target-1",
        target_row_id="target-1",
        target_row=first_match.target_row,
        status=MatchStatus.MATCHED,
        selected_candidate=None,
        selected_candidates=(first_match.selected_candidate, second_match.selected_candidate),
        candidates=(first_match.selected_candidate, second_match.selected_candidate),
        warnings=(),
        explanation=("authoritative",),
    )

    (result,) = calculate_matches((combined,), calculation_rule_set())

    assert result.quantity == Decimal("5.00")
    assert result.cost == Decimal("25.00")


def test_reconciliation_target_binds_only_a_b_c_d_e_f_j_k_and_scales_writer_values() -> None:
    source = calculation_source_row(
        "source:1", quantity=Decimal("1.005"), cost=Decimal("1000000.005")
    )
    calculated = calculate_matches(
        (match_result(source),), calculation_rule_set(coefficient=Decimal("2.7"))
    )

    (written,) = writer_calculations(calculated)

    assert [(binding.logical_column.value, binding.column_letter) for binding in _bindings()] == [
        ("object_code", "A"),
        ("document_index", "B"),
        ("stage", "C"),
        ("row_number", "D"),
        ("work_name", "E"),
        ("unit", "F"),
        ("current_period_quantity", "J"),
        ("current_period_cost", "K"),
    ]
    assert written.quantity == Decimal("1.01")
    assert written.cost == Decimal("2.70")


def _review_job(tmp_path) -> tuple[AdminPanelService, AdminJob, str]:
    service = AdminPanelService(tmp_path)
    directory = tmp_path / "job"
    directory.mkdir()
    source, target = directory / "source.xlsx", directory / "target.xlsx"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    row = ReviewRow("source:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((row,))
    state = ReconciliationReviewState(
        rows={row.row_id: row},
        groups={group.group_id: group},
        categories={"target-1": "Цель"},
        source_digests=(sha256(source.read_bytes()).hexdigest(),),
        target_digest=sha256(target.read_bytes()).hexdigest(),
    )
    job = AdminJob(
        job_id="job",
        directory=directory,
        source=source,
        target=target,
        stage="13.1",
        mode="write",
        source_digest=state.source_digests[0],
        target_digest=state.target_digest,
        sources=(source,),
        source_digests=state.source_digests,
        status="review_required",
        review_state=state,
    )
    service.jobs[job.job_id] = job
    return service, job, group.group_id


def _accept_group(job: AdminJob, group_id: str) -> None:
    assert job.review_state is not None
    version = job.review_state.group_snapshot()[0].version
    job.review_state.put_group(
        group_id,
        ReviewDecision(
            action=ReviewAction.ACCEPT,
            mode=ReviewMode.QUANTITY_COST,
            target_category="target-1",
            group_id=group_id,
            version=version,
        ),
    )


def test_apply_blocks_unresolved_and_tampered_input_before_write(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    called = False

    def should_not_apply(*_args):
        nonlocal called
        called = True
        raise AssertionError("apply must not execute")

    monkeypatch.setattr("report_processor.admin_panel.service.apply_review", should_not_apply)
    with pytest.raises(ValueError, match="incomplete"):
        service.apply_reconciliation(job.job_id)
    assert called is False

    _accept_group(job, group_id)
    job.target.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="input upload changed"):
        service.apply_reconciliation(job.job_id)
    assert called is False and job.status == "failed"


def test_feedback_failure_removes_written_output_and_never_marks_job_ready(
    tmp_path, monkeypatch
) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"written")

    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )
    monkeypatch.setattr(
        service.feedback_store,
        "commit_apply",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("db")),
    )

    with pytest.raises(OSError, match="db"):
        service.apply_reconciliation(job.job_id)

    assert output.exists() is True
    assert job.output == output and job.status == "applying"
    assert job.result_available is False


@pytest.mark.parametrize("fault", ["before_commit", "after_commit"])
def test_restart_exact_replays_durable_apply_once(tmp_path, monkeypatch, fault) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    decisions = tuple(job.review_state.core_decisions())
    feedback = _feedback_records(job.review_state, decisions)

    def write_result(*_args):
        output.write_bytes(b"result")
        from report_processor.business_rules import load_default_rule_set

        apply_key, plan_hash = _apply_plan(
            job,
            job.review_state,
            load_default_rule_set().rule_set.content_hash,
            _feedback_records(job.review_state, decisions),
            decisions,
        )
        return ReconciliationApplyResult(output, feedback, apply_key, plan_hash)

    monkeypatch.setattr("report_processor.admin_panel.service.apply_review", write_result)
    monkeypatch.setattr(
        "report_processor.admin_panel.service.prepare_review",
        lambda *_args: __import__(
            "report_processor.admin_panel.reconciliation_execution",
            fromlist=["ReconciliationReviewResult"],
        ).ReconciliationReviewResult(state=job.review_state, source_batch=None),
    )
    if fault == "before_commit":
        monkeypatch.setattr(
            service.feedback_store,
            "commit_apply",
            lambda **_kwargs: (_ for _ in ()).throw(OSError("before commit")),
        )
    else:
        original_save = service._job_store.save
        calls = 0

        def fail_ready_manifest(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("after commit")
            return original_save(*args, **kwargs)

        monkeypatch.setattr(service._job_store, "save", fail_ready_manifest)

    with pytest.raises(OSError):
        service.apply_reconciliation(job.job_id)
    assert job.status == "applying"

    restored = AdminPanelService(tmp_path).get_job(job.job_id)

    assert restored.status == "ready"
    records = AdminPanelService(tmp_path).feedback_store.records(job.target_digest)
    assert len(records) == len(feedback)


def test_hostile_apply_hash_cannot_commit_feedback_or_publish_ready(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    decisions = tuple(job.review_state.core_decisions())
    feedback = _feedback_records(job.review_state, decisions)

    def write_result(*_args):
        output.write_bytes(b"result")
        from report_processor.business_rules import load_default_rule_set

        apply_key, plan_hash = _apply_plan(
            job,
            job.review_state,
            load_default_rule_set().rule_set.content_hash,
            feedback,
            decisions,
        )
        return ReconciliationApplyResult(output, feedback, apply_key, plan_hash)

    monkeypatch.setattr("report_processor.admin_panel.service.apply_review", write_result)
    monkeypatch.setattr(
        service.feedback_store,
        "commit_apply",
        lambda **_kwargs: (_ for _ in ()).throw(OSError("before commit")),
    )
    with pytest.raises(OSError):
        service.apply_reconciliation(job.job_id)
    manifest = service._job_store.load(job.job_id)
    assert manifest is not None
    manifest["apply"]["apply_key"] = "f" * 64
    service._job_store.save(job.job_id, manifest)
    monkeypatch.setattr(
        "report_processor.admin_panel.service.prepare_review",
        lambda *_args: __import__(
            "report_processor.admin_panel.reconciliation_execution",
            fromlist=["ReconciliationReviewResult"],
        ).ReconciliationReviewResult(state=job.review_state, source_batch=None),
    )

    recovered = AdminPanelService(tmp_path)

    with pytest.raises(KeyError):
        recovered.get_job(job.job_id)
    assert recovered.feedback_store.records(job.target_digest) == ()


def test_repeated_apply_keeps_verified_ready_result_unchanged(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    calls = 0

    def write_once(*_args):
        nonlocal calls
        calls += 1
        output.write_bytes(b"verified-result")
        return output, ()

    monkeypatch.setattr("report_processor.admin_panel.service.apply_review", write_once)

    first = service.apply_reconciliation(job.job_id)
    before = output.read_bytes()
    second = service.apply_reconciliation(job.job_id)

    assert first is second is job
    assert calls == 1
    assert output.read_bytes() == before
    assert job.status == "ready" and job.result_available is True


def test_apply_validates_and_chmods_output_before_feedback_commit(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"result")
    events: list[str] = []
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )
    original_fchmod = __import__("os").fchmod

    def fchmod(descriptor, mode):
        events.append("chmod")
        return original_fchmod(descriptor, mode)

    monkeypatch.setattr("report_processor.admin_panel.service.os.fchmod", fchmod)
    monkeypatch.setattr(
        service.feedback_store,
        "commit_apply",
        lambda **_kwargs: events.append("commit") or True,
    )

    service.apply_reconciliation(job.job_id)

    assert events[-1] == "commit" and "chmod" in events
    assert job.status == "ready" and job.output == output


def test_apply_chmod_failure_never_commits_feedback_and_removes_owned_output(
    tmp_path, monkeypatch
) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"result")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.service.os.fchmod",
        lambda _descriptor, _mode: (_ for _ in ()).throw(OSError("chmod")),
    )
    committed = False

    def should_not_commit(**_kwargs):
        nonlocal committed
        committed = True
        return True

    monkeypatch.setattr(service.feedback_store, "commit_apply", should_not_commit)

    with pytest.raises(OSError, match="chmod"):
        service.apply_reconciliation(job.job_id)

    assert committed is False and output.exists() is True and job.status == "failed"


def test_apply_failure_keeps_concurrent_output_replacement(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"attempt")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )

    def replace_then_fail(**_kwargs):
        replacement = job.directory / "replacement.xlsx"
        replacement.write_bytes(b"replacement")
        replacement.replace(output)
        raise OSError("database")

    monkeypatch.setattr(service.feedback_store, "commit_apply", replace_then_fail)

    with pytest.raises(OSError, match="database"):
        service.apply_reconciliation(job.job_id)

    assert output.read_bytes() == b"replacement"


def test_apply_rejects_wrong_output_path_before_feedback_commit(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    wrong = job.directory / "other.xlsx"
    wrong.write_bytes(b"result")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (wrong, ())
    )
    committed = False

    def should_not_commit(**_kwargs):
        nonlocal committed
        committed = True
        return True

    monkeypatch.setattr(service.feedback_store, "commit_apply", should_not_commit)
    with pytest.raises(RuntimeError, match="OUTPUT_INVALID"):
        service.apply_reconciliation(job.job_id)
    assert committed is False and wrong.exists()


def test_apply_precommit_rejects_replaced_source_and_preserves_owned_result(
    tmp_path, monkeypatch
) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"result")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )

    def replace_source_then_validate(**kwargs):
        replacement = job.directory / "replacement-source.xlsx"
        replacement.write_bytes(b"different source")
        replacement.replace(job.source)
        kwargs["precommit_validator"]()
        raise AssertionError("commit must not continue")

    monkeypatch.setattr(service.feedback_store, "commit_apply", replace_source_then_validate)
    with pytest.raises(RuntimeError, match="source upload changed"):
        service.apply_reconciliation(job.job_id)
    assert output.exists() is True


def test_apply_precommit_rejects_replaced_output_and_preserves_replacement(
    tmp_path, monkeypatch
) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"attempt")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )

    def replace_output_then_validate(**kwargs):
        replacement = job.directory / "replacement.xlsx"
        replacement.write_bytes(b"replacement")
        replacement.replace(output)
        kwargs["precommit_validator"]()

    monkeypatch.setattr(service.feedback_store, "commit_apply", replace_output_then_validate)
    with pytest.raises(RuntimeError, match="OUTPUT_INVALID"):
        service.apply_reconciliation(job.job_id)
    assert output.read_bytes() == b"replacement"


@pytest.mark.parametrize("mutation", ["content", "mode"])
def test_apply_precommit_rejects_in_place_output_mutation(tmp_path, monkeypatch, mutation) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"attempt")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review", lambda *_args: (output, ())
    )

    def mutate_then_validate(**kwargs):
        if mutation == "content":
            output.write_bytes(b"changed")
        else:
            output.chmod(0o644)
        kwargs["precommit_validator"]()

    monkeypatch.setattr(service.feedback_store, "commit_apply", mutate_then_validate)
    with pytest.raises(RuntimeError, match="OUTPUT_INVALID"):
        service.apply_reconciliation(job.job_id)
    assert output.exists()


def test_keyboard_interrupt_during_apply_marks_job_failed_and_keeps_output_safe(
    tmp_path, monkeypatch
) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    output.write_bytes(b"existing")
    monkeypatch.setattr(
        "report_processor.admin_panel.service.apply_review",
        lambda *_args: (_ for _ in ()).throw(KeyboardInterrupt()),
    )
    with pytest.raises(KeyboardInterrupt):
        service.apply_reconciliation(job.job_id)
    assert job.status == "failed" and output.read_bytes() == b"existing"


def test_failed_snapshot_copy_keeps_concurrent_replacement(tmp_path, monkeypatch) -> None:
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"source")
    destination = tmp_path / "private-snapshot.xlsx"

    def replace_then_fail(_descriptor, _content):
        replacement = tmp_path / "replacement.xlsx"
        replacement.write_bytes(b"replacement")
        replacement.replace(destination)
        raise OSError("write")

    monkeypatch.setattr("report_processor.admin_panel.service.os.write", replace_then_fail)
    with pytest.raises(OSError, match="write"):
        _copy_verified_snapshot(source, destination, sha256(source.read_bytes()).hexdigest())
    assert destination.read_bytes() == b"replacement"


def test_decision_mutation_cannot_interleave_authoritative_apply(tmp_path, monkeypatch) -> None:
    service, job, group_id = _review_job(tmp_path)
    _accept_group(job, group_id)
    output = job.directory / "result.xlsx"
    entered, release, mutation_done = threading.Event(), threading.Event(), threading.Event()
    errors: list[Exception] = []

    def blocked_apply(*_args):
        output.write_bytes(b"result")
        entered.set()
        assert release.wait(2)
        return output, ()

    monkeypatch.setattr("report_processor.admin_panel.service.apply_review", blocked_apply)
    apply_thread = threading.Thread(target=lambda: service.apply_reconciliation(job.job_id))
    apply_thread.start()
    assert entered.wait(2)

    def mutate():
        try:
            service.put_reconciliation_group(
                job.job_id, group_id, ReviewDecision(ReviewAction.REJECT)
            )
        except Exception as error:
            errors.append(error)
        finally:
            mutation_done.set()

    mutation_thread = threading.Thread(target=mutate)
    mutation_thread.start()
    release.set()
    apply_thread.join(2)
    mutation_thread.join(2)
    assert job.status == "ready" and len(errors) == 1 and isinstance(errors[0], ValueError)

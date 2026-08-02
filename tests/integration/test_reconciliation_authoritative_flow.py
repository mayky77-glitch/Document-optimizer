from decimal import Decimal
from hashlib import sha256

import pytest

from fixtures.calculation.builders import calculation_rule_set, calculation_source_row, match_result
from report_processor.admin_panel.reconciliation_state import ReconciliationReviewState
from report_processor.admin_panel.reconciliation_target import _bindings, writer_calculations
from report_processor.admin_panel.service import AdminJob, AdminPanelService
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
    with pytest.raises(RuntimeError, match="target upload changed"):
        service.apply_reconciliation(job.job_id)
    assert called is False and job.status == "review_required"


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
        service.feedback_store, "persist", lambda *_args: (_ for _ in ()).throw(OSError("db"))
    )

    with pytest.raises(OSError, match="db"):
        service.apply_reconciliation(job.job_id)

    assert output.exists() is False
    assert job.output is None and job.status == "failed"

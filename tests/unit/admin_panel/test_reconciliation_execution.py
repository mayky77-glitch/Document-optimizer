from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook, load_workbook

from report_processor.admin_panel.reconciliation_execution import (
    _Catalog,
    _feedback_records,
    _normalized_source_digests,
    _review_row_id,
    apply_review,
    prepare_review,
)
from report_processor.admin_panel.reconciliation_semantic_assist import RUBERT_TINY2_MODEL_REVISION
from report_processor.admin_panel.reconciliation_target import publish_unchanged_target
from report_processor.reconciliation_review import (
    FeedbackRecord,
    ReviewAction,
    ReviewDecision,
    ReviewMode,
    ReviewRow,
    build_review_groups,
)


def test_prepare_review_hides_leading_zero_row_without_hiding_later_nonzero_row(
    tmp_path, monkeypatch
) -> None:
    zero = ReviewRow("zero", "Нулевая работа", "м", Decimal("0"), Decimal("0"), "target-1")
    nonzero = ReviewRow("nonzero", "Ненулевая работа", "м", Decimal("1"), Decimal("2"), "target-1")
    job = SimpleNamespace(
        source_digests=("source",),
        target_digest="target",
        target=tmp_path / "target.xlsx",
        stage="13.1",
        directory=tmp_path,
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._sources",
        lambda _job: SimpleNamespace(rows=(), issues=()),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution.read_reconciliation_target",
        lambda *_args: (object(), ()),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._catalog",
        lambda _targets: _Catalog({"target-1": "Цель"}, {}),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._review_rows",
        lambda *_args: (zero, nonzero),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._available_categories",
        lambda *_args: {"zero": frozenset({"target-1"}), "nonzero": frozenset({"target-1"})},
    )

    result = prepare_review(job, (FeedbackRecord("нулевая работа", "м", ReviewAction.REJECT),))

    assert result.state is not None
    assert tuple(result.state.rows) == ("nonzero",)
    assert result.state.grouping.partition.hidden_rows == (zero,)
    assert result.state.grouping.version_context.model_revision == RUBERT_TINY2_MODEL_REVISION
    assert result.state.group_decisions == {} and result.state.row_decisions == {}


def test_package_version_source_digests_are_normalized_sorted_and_unique() -> None:
    assert _normalized_source_digests((" B ", "a", "b", "A")) == ("a", "b")
    with pytest.raises(ValueError, match="required"):
        _normalized_source_digests(("source", None))


def test_feedback_records_restore_row_feedback_over_group_feedback() -> None:
    first = ReviewRow("source-a:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    second = ReviewRow("source-b:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((first, second))
    state = SimpleNamespace(
        groups={group.group_id: group},
        rows={first.row_id: first, second.row_id: second},
        group_decisions={
            group.group_id: ReviewDecision(
                ReviewAction.ACCEPT,
                ReviewMode.QUANTITY_COST,
                "target-1",
                group_id=group.group_id,
            )
        },
        row_decisions={
            second.row_id: ReviewDecision(
                ReviewAction.REJECT,
                row_id=second.row_id,
            )
        },
    )

    feedback = _feedback_records(state)

    assert feedback == (
        FeedbackRecord(
            group.normalized_name or "",
            group.normalized_unit,
            ReviewAction.ACCEPT,
            "target-1",
            ReviewMode.QUANTITY_COST,
            1,
        ),
        FeedbackRecord("монтаж трубы", "м", ReviewAction.REJECT, sequence=2),
    )


def test_review_row_id_is_stable_and_hides_source_provenance() -> None:
    source_digest = "a" * 64
    source_row_id = f"source:0:{source_digest}:ks6a:455"
    job = SimpleNamespace(target_digest="b" * 64, source_digests=(source_digest,))

    row_id = _review_row_id(job, source_row_id)

    assert row_id == _review_row_id(job, source_row_id)
    assert row_id.startswith("review-row-")
    assert source_digest not in row_id
    assert "ks6a" not in row_id
    assert ":455" not in row_id


def test_unchanged_publisher_removes_link_after_final_verification_failure(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "target.xlsx"
    output = tmp_path / "result.xlsx"
    workbook = Workbook()
    workbook.save(source)
    workbook.close()
    digest = sha256(source.read_bytes()).hexdigest()
    calls = 0

    def fail_final_reopen(_path):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError("final reopen failed")

    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_target._reopen_xlsx",
        fail_final_reopen,
    )

    with pytest.raises(ValueError, match="final reopen failed"):
        publish_unchanged_target(source, output, digest)

    assert output.exists() is False
    assert sha256(source.read_bytes()).hexdigest() == digest


def test_unchanged_publisher_never_links_output_when_identity_probe_fails(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "target.xlsx"
    output = tmp_path / "result.xlsx"
    workbook = Workbook()
    workbook.save(source)
    workbook.close()
    digest = sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_target._file_identity",
        lambda _path: (_ for _ in ()).throw(OSError("stat failed")),
    )

    with pytest.raises(RuntimeError, match="PUBLISH_FAILED"):
        publish_unchanged_target(source, output, digest)

    assert output.exists() is False
    assert sha256(source.read_bytes()).hexdigest() == digest


def test_apply_review_all_rejected_writes_unchanged_target_and_feedback(
    tmp_path, monkeypatch
) -> None:
    row = ReviewRow("source:1", "Монтаж трубы", "м", Decimal("1"), Decimal("2"))
    (group,) = build_review_groups((row,))
    rejected = SimpleNamespace(
        rows={row.row_id: row},
        groups={group.group_id: group},
        group_decisions={
            group.group_id: ReviewDecision(
                ReviewAction.REJECT,
                group_id=group.group_id,
            )
        },
        row_decisions={},
        core_decisions=lambda: (
            ReviewDecision(ReviewAction.REJECT, group_id=group.group_id, version=group.version),
        ),
    )
    job = SimpleNamespace(
        target=tmp_path / "target.xlsx",
        target_digest="target-digest",
        stage="13.1",
        directory=tmp_path,
        rules_path=None,
    )
    workbook = Workbook()
    workbook.active["A1"] = "unchanged"
    input_stream = BytesIO()
    workbook.save(input_stream)
    workbook.close()
    input_bytes = input_stream.getvalue()
    job.target.write_bytes(input_bytes)
    job.target_digest = sha256(input_bytes).hexdigest()
    output = tmp_path / "result.xlsx"
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution.read_reconciliation_target",
        lambda *_args: (object(), ()),
    )
    monkeypatch.setattr(
        "report_processor.admin_panel.reconciliation_execution._sources",
        lambda _job: SimpleNamespace(rows=()),
    )

    def write_unchanged(source, destination, *_args):
        destination.write_bytes(source.read_bytes())
        return SimpleNamespace(output_sha256=sha256(destination.read_bytes()).hexdigest())

    monkeypatch.setattr("report_processor.excel_writer.write_target_report", write_unchanged)

    written, feedback = apply_review(job, rejected)

    assert written == output
    assert written.read_bytes() == input_bytes
    assert sha256(written.read_bytes()).hexdigest() == sha256(input_bytes).hexdigest()
    reopened = load_workbook(written, read_only=True, data_only=True)
    try:
        assert reopened.active["A1"].value == "unchanged"
    finally:
        reopened.close()
    assert feedback[0].action is ReviewAction.REJECT

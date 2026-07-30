from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from report_processor.drawing_card.matching.matcher import ReviewApproval
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
    WorkflowResult,
)
from report_processor.drawing_card.review.io import import_review_approvals
from report_processor.terminal_review import (
    collect_terminal_review,
    save_terminal_review_decisions,
)


def _row(row_id: str, index: int) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation(
            file_id="file",
            filename="source.xlsx",
            sheet_name="КС-6а",
            row_number=10 + index,
            coordinates=(f"A{10 + index}",),
        ),
        object_index_raw="0906",
        drawing_code_raw=f"DRAW-{index}",
        work_name_raw=f"Работа {index}",
        unit_raw="м",
        remaining_quantity=Decimal("12.5"),
        remaining_total_cost=Decimal("1000.25"),
        formula_values=(),
        cached_values=(),
        source_document_type="ks6a",
        source_period="2026-07",
        source_revision=None,
        status="WARNING",
        warnings=(),
    )


def _decision(
    row_id: str,
    category: TargetWorkCategory | None,
) -> MatchDecision:
    return MatchDecision(
        row_id=row_id,
        category=category,
        quantity_decision="review",
        cost_decision="review",
        quantity_rule_id=None,
        cost_rule_id=None,
        quantity_confidence=None,
        cost_confidence=None,
        matching_strategy="review",
        evidence_ids=(),
        reason="Needs user confirmation",
        requires_manual_review=True,
        status="UNCONFIRMED_CLASSIFICATION",
        warnings=("UNCONFIRMED_CLASSIFICATION",),
    )


def _result(
    categories: tuple[TargetWorkCategory | None, ...],
    tmp_path: Path,
) -> WorkflowResult:
    rows = [_row(f"row-{index}", index) for index in range(len(categories))]
    decisions = [
        _decision(row.row_id, category) for row, category in zip(rows, categories, strict=True)
    ]
    return WorkflowResult(
        run_id="run",
        status="BLOCKED",
        work_dir=tmp_path,
        source_rows=rows,
        decisions=decisions,
        manual_review_count=len(decisions),
    )


def _input(values: list[str]):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_reject_all_and_allow_partial(tmp_path: Path) -> None:
    result = _result((None, TargetWorkCategory.METAL_STRUCTURES), tmp_path)

    outcome = collect_terminal_review(
        result,
        input_fn=_input(["1", "д"]),
        output_fn=lambda _value: None,
    )

    assert outcome.proceed
    assert outcome.allow_partial
    assert {item.action for item in outcome.decisions.values()} == {"reject"}


def test_approve_available_requires_category_for_missing_proposal(tmp_path: Path) -> None:
    result = _result((TargetWorkCategory.METAL_STRUCTURES, None), tmp_path)

    outcome = collect_terminal_review(
        result,
        input_fn=_input(["2", "1", "2", "н"]),
        output_fn=lambda _value: None,
    )

    assert outcome.proceed
    assert not outcome.allow_partial
    assert outcome.decisions["row-0"] == ReviewApproval(
        "row-0", "approve", TargetWorkCategory.METAL_STRUCTURES
    )
    assert outcome.decisions["row-1"] == ReviewApproval(
        "row-1", "approve", TargetWorkCategory.CONCRETE_WORKS
    )


def test_item_by_item_supports_metric_and_reject_actions(tmp_path: Path) -> None:
    result = _result(
        (TargetWorkCategory.METAL_STRUCTURES, None, None),
        tmp_path,
    )

    outcome = collect_terminal_review(
        result,
        input_fn=_input(["3", "1", "3", "3", "5", "н"]),
        output_fn=lambda _value: None,
    )

    assert outcome.decisions["row-0"].action == "approve"
    assert outcome.decisions["row-1"] == ReviewApproval(
        "row-1", "quantity_only", TargetWorkCategory.METAL_STRUCTURES
    )
    assert outcome.decisions["row-2"].action == "reject"


def test_reject_remaining_and_json_round_trip(tmp_path: Path) -> None:
    result = _result((None, None, None), tmp_path)

    outcome = collect_terminal_review(
        result,
        input_fn=_input(["3", "8", "н"]),
        output_fn=lambda _value: None,
    )
    path = tmp_path / "decisions.json"
    save_terminal_review_decisions(path, outcome.decisions)

    loaded = import_review_approvals(path)
    assert loaded == outcome.decisions
    assert len(loaded) == 3


def test_invalid_input_retries_and_cancel_never_proceeds(tmp_path: Path) -> None:
    messages: list[str] = []
    result = _result((None,), tmp_path)

    outcome = collect_terminal_review(
        result,
        input_fn=_input(["bad", "3", "bad", "0"]),
        output_fn=messages.append,
    )

    assert not outcome.proceed
    assert not outcome.decisions
    assert messages.count("Введите номер из списка.") == 2


def test_row_details_are_printed(tmp_path: Path) -> None:
    messages: list[str] = []
    result = _result((TargetWorkCategory.METAL_STRUCTURES,), tmp_path)

    collect_terminal_review(
        result,
        input_fn=_input(["3", "5", "н"]),
        output_fn=messages.append,
    )

    rendered = "\n".join(messages)
    assert "Объект: 0906" in rendered
    assert "Шифр: DRAW-0" in rendered
    assert "Работа: Работа 0" in rendered
    assert "Количество: 12.5" in rendered
    assert "Стоимость: 1000.25" in rendered

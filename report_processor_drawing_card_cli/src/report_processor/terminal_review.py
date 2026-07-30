"""Interactive terminal review for disputed drawing-card rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from report_processor.drawing_card.audit import atomic_write_json
from report_processor.drawing_card.matching.matcher import ReviewApproval
from report_processor.drawing_card.models import (
    CATEGORY_DISPLAY_NAMES,
    DrawingSourceRow,
    MatchDecision,
    TargetWorkCategory,
    WorkflowResult,
)
from report_processor.drawing_card.review.io import review_approvals_payload

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class TerminalReviewOutcome:
    """Decisions collected in terminal before one audited workflow rerun."""

    decisions: dict[str, ReviewApproval]
    proceed: bool
    allow_partial: bool


def _choice(
    prompt: str,
    aliases: dict[str, str],
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> str:
    while True:
        value = input_fn(prompt).strip().lower()
        resolved = aliases.get(value)
        if resolved is not None:
            return resolved
        output_fn("Введите номер из списка.")


def _yes_no(prompt: str, *, input_fn: InputFn, output_fn: OutputFn) -> bool:
    while True:
        value = input_fn(prompt).strip().lower()
        if value in {"", "н", "нет", "n", "no", "0"}:
            return False
        if value in {"д", "да", "y", "yes", "1"}:
            return True
        output_fn("Введите «да» или «нет».")


def _review_items(
    result: WorkflowResult,
) -> list[tuple[DrawingSourceRow, MatchDecision]]:
    rows = {row.row_id: row for row in result.source_rows}
    return [
        (rows[decision.row_id], decision)
        for decision in result.decisions
        if decision.requires_manual_review and decision.row_id in rows
    ]


def _category(
    proposed: TargetWorkCategory | None,
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> TargetWorkCategory | None:
    categories = tuple(TargetWorkCategory)
    output_fn("Категория:")
    if proposed is not None:
        output_fn(f"  0. Оставить предложение: {CATEGORY_DISPLAY_NAMES[proposed]}")
    for index, category in enumerate(categories, 1):
        output_fn(f"  {index}. {CATEGORY_DISPLAY_NAMES[category]}")
    output_fn("  x. Отмена текущего решения")
    while True:
        value = input_fn("Выберите категорию: ").strip().lower()
        if value == "x":
            return None
        if value == "0" and proposed is not None:
            return proposed
        if value.isdigit() and 1 <= int(value) <= len(categories):
            return categories[int(value) - 1]
        output_fn("Введите номер категории.")


def _show_item(
    index: int,
    total: int,
    row: DrawingSourceRow,
    decision: MatchDecision,
    *,
    output_fn: OutputFn,
) -> None:
    proposed = (
        CATEGORY_DISPLAY_NAMES[decision.category]
        if decision.category is not None
        else "нет предложения"
    )
    output_fn("")
    output_fn(f"Спорная строка {index}/{total}")
    output_fn(f"Объект: {row.object_index_raw or '—'} | Шифр: {row.drawing_code_raw or '—'}")
    output_fn(
        f"Источник: {row.location.filename} / {row.location.sheet_name} / "
        f"строка {row.location.row_number}"
    )
    output_fn(f"Работа: {row.work_name_raw or '—'}")
    output_fn(
        f"Ед.: {row.unit_raw or '—'} | "
        f"Количество: {row.remaining_quantity if row.remaining_quantity is not None else '—'} | "
        f"Стоимость: {row.remaining_total_cost if row.remaining_total_cost is not None else '—'}"
    )
    output_fn(f"Предложение: {proposed}")
    output_fn(f"Причина: {decision.reason}")


def _approval(
    row_id: str,
    action: str,
    category: TargetWorkCategory | None,
) -> ReviewApproval:
    return ReviewApproval(row_id=row_id, action=action, category=category)


def _resolve_items(
    items: list[tuple[DrawingSourceRow, MatchDecision]],
    decisions: dict[str, ReviewApproval],
    *,
    input_fn: InputFn,
    output_fn: OutputFn,
) -> bool:
    pending = list(items)
    position = 0
    while position < len(pending):
        row, decision = pending[position]
        _show_item(position + 1, len(pending), row, decision, output_fn=output_fn)
        output_fn("  1. Одобрить предложение")
        output_fn("  2. Выбрать категорию и одобрить")
        output_fn("  3. Учесть только количество")
        output_fn("  4. Учесть только стоимость")
        output_fn("  5. Отклонить строку")
        output_fn("  6. Пропустить строку")
        output_fn("  7. Одобрить все оставшиеся предложения")
        output_fn("  8. Отклонить все оставшиеся строки")
        output_fn("  0. Отменить выпуск карточки")
        action = _choice(
            "Решение: ",
            {
                "1": "approve",
                "approve": "approve",
                "2": "category",
                "category": "category",
                "3": "quantity_only",
                "quantity_only": "quantity_only",
                "4": "cost_only",
                "cost_only": "cost_only",
                "5": "reject",
                "reject": "reject",
                "6": "skip",
                "skip": "skip",
                "7": "approve_available",
                "approve_available": "approve_available",
                "8": "reject_all",
                "reject_all": "reject_all",
                "0": "cancel",
                "cancel": "cancel",
            },
            input_fn=input_fn,
            output_fn=output_fn,
        )
        if action == "cancel":
            return False
        if action == "reject_all":
            for remaining_row, _remaining_decision in pending[position:]:
                decisions[remaining_row.row_id] = _approval(remaining_row.row_id, "reject", None)
            return True
        if action == "approve_available":
            unresolved = []
            approved = 0
            for remaining_row, remaining_decision in pending[position:]:
                if remaining_decision.category is None:
                    unresolved.append((remaining_row, remaining_decision))
                    continue
                decisions[remaining_row.row_id] = _approval(
                    remaining_row.row_id,
                    "approve",
                    remaining_decision.category,
                )
                approved += 1
            output_fn(f"Одобрено предложений: {approved}. Без категории: {len(unresolved)}.")
            if not unresolved:
                return True
            pending = unresolved
            position = 0
            continue
        if action in {"reject", "skip"}:
            decisions[row.row_id] = _approval(row.row_id, action, None)
            position += 1
            continue
        category = decision.category
        if action == "category" or category is None:
            category = _category(
                decision.category,
                input_fn=input_fn,
                output_fn=output_fn,
            )
            if category is None:
                output_fn("Решение не сохранено.")
                continue
        saved_action = "change_category" if action == "category" else action
        decisions[row.row_id] = _approval(row.row_id, saved_action, category)
        position += 1
    return True


def collect_terminal_review(
    result: WorkflowResult,
    *,
    input_fn: InputFn = input,
    output_fn: OutputFn = print,
) -> TerminalReviewOutcome:
    """Collect bulk or per-row review decisions without changing source files."""
    items = _review_items(result)
    if not items:
        output_fn("Спорные строки не найдены.")
        return TerminalReviewOutcome({}, False, False)

    output_fn("")
    output_fn(f"Нужно решить спорных строк: {len(items)}")
    output_fn("  1. Отклонить все спорные строки и создать карточку")
    output_fn("  2. Одобрить все доступные предложения")
    output_fn("  3. Решить каждую строку отдельно")
    output_fn("  0. Отменить выпуск карточки")
    action = _choice(
        "Выберите действие: ",
        {
            "1": "reject_all",
            "reject_all": "reject_all",
            "2": "approve_available",
            "approve_available": "approve_available",
            "3": "item_by_item",
            "item_by_item": "item_by_item",
            "0": "cancel",
            "cancel": "cancel",
        },
        input_fn=input_fn,
        output_fn=output_fn,
    )
    if action == "cancel":
        return TerminalReviewOutcome({}, False, False)

    decisions: dict[str, ReviewApproval] = {}
    if action == "reject_all":
        decisions = {row.row_id: _approval(row.row_id, "reject", None) for row, _decision in items}
        proceed = True
    else:
        pending = items
        if action == "approve_available":
            pending = []
            for row, decision in items:
                if decision.category is None:
                    pending.append((row, decision))
                else:
                    decisions[row.row_id] = _approval(row.row_id, "approve", decision.category)
            output_fn(f"Одобрено предложений: {len(decisions)}. Без предложения: {len(pending)}.")
        proceed = _resolve_items(
            pending,
            decisions,
            input_fn=input_fn,
            output_fn=output_fn,
        )
    if not proceed:
        return TerminalReviewOutcome(decisions, False, False)

    allow_partial = _yes_no(
        "Если останутся другие предупреждения, создать PARTIALLY_READY? [д/Н]: ",
        input_fn=input_fn,
        output_fn=output_fn,
    )
    return TerminalReviewOutcome(decisions, True, allow_partial)


def save_terminal_review_decisions(
    path: Path,
    decisions: dict[str, ReviewApproval],
) -> None:
    """Atomically save decisions using existing review JSON contract."""
    atomic_write_json(path, review_approvals_payload(decisions))

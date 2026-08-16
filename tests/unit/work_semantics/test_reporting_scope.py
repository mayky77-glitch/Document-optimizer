from __future__ import annotations

import pytest

from report_processor.work_semantics import is_reporting_scope


@pytest.mark.parametrize(
    "value",
    (
        "тридцать дней",
        "первый квартал",
        "отчетную дату",
        "выполненные сложные работы",
        "сто дней",
        "отчетность",
        "дату итогового отчета",
        "весь производственный этап",
        "выполнённые работы",
        "август 2026",
        "весь отчетный период",
        "текущий отчетный период",
    ),
)
def test_reporting_scope_accepts_bounded_reporting_and_work_phrases(value: str) -> None:
    assert is_reporting_scope(value)


@pytest.mark.parametrize(
    "value",
    (
        "работник",
        "работника-час",
        "датчик",
        "дневник",
        "дневной прокат",
        "оборудование для работ",
        "не выполненные работы",
        "оборудование для работ за август",
        "датчик за отчетный период",
    ),
)
def test_reporting_scope_rejects_collisions_and_embedded_objects(value: str) -> None:
    assert not is_reporting_scope(value)


def test_reporting_scope_rejects_over_budget_token_sequences() -> None:
    assert not is_reporting_scope(" ".join(("условный",) * 24 + ("дней",)))

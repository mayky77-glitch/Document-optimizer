"""Confirmed Russian dictionary masks for drawing-card classification."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.drawing_card.aggregation import aggregate_rows
from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import ConfirmedExample
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher, _exact_token_pattern
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    TargetWorkCategory,
)
from report_processor.drawing_card.statuses import Status


RULES = load_rules(
    Path(__file__).parents[3] / "src" / "report_processor" / "drawing_card" / "resources" / "rules.json"
)


def _row(
    name: str | None,
    *,
    unit: str | None = "м",
    quantity: Decimal | None = Decimal("7"),
    cost: Decimal | None = Decimal("1500"),
    row_id: str = "row-1",
) -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation("source", "source.xlsx", "Лист1", 2, ("A2",)),
        object_index_raw="1001",
        drawing_code_raw="А-1",
        work_name_raw=name,
        unit_raw=unit,
        remaining_quantity=quantity,
        remaining_total_cost=cost,
        formula_values=(),
        cached_values=(),
        source_document_type="visr",
        source_period=None,
        source_revision=None,
        status=Status.OK,
        warnings=(),
    )


def _matcher(*, examples: tuple[ConfirmedExample, ...] = ()) -> DrawingRowMatcher:
    return DrawingRowMatcher(RULES, examples, rag_mode="off")


@pytest.mark.parametrize(
    ("name", "category", "unit"),
    [
        ("Устройство основания из буроопускных металлических свай", "pile_foundation", "шт"),
        ("Бетонирование фундаментов общего назначения", "concrete_works", "м3"),
        ("Армирование и бетонирование монолитных участков из бетона", "concrete_works", "м³"),
        ("Монтаж м/к каркасов зданий и сооружений", "metal_structures", "т"),
        ("Монтаж металокнострукция эстакад", "metal_structures", "т"),
        ("Монтаж ТТ Д 108 мм", "tt_installation", "м"),
        ("Укладка трубопроводов Д 108 мм", "tt_installation", "м"),
        ("Монтаж ЗРА внутренних ИС Д 57 мм", "tt_valves_installation", "шт"),
    ],
)
def test_confirmed_dictionary_phrases_match_only_existing_categories(
    name: str, category: str, unit: str
) -> None:
    decision = _matcher().match(_row(name, unit=unit))

    assert decision.category is TargetWorkCategory(category)
    assert decision.quantity_decision == "include"
    assert decision.cost_decision == "include"
    assert decision.requires_manual_review is False


@pytest.mark.parametrize(
    "name",
    [
        "Кабель 16x1,0 м3 о СКАБ-С 660нг(А)-FRLS",
        "Прокладка\u00a0кабеля   электрической сети",
        "Прокладка кабеля силовои сети",
    ],
)
def test_generic_cable_and_safe_one_edit_long_token_default_to_power(name: str) -> None:
    decision = _matcher().match(_row(name))

    assert decision.category is TargetWorkCategory.POWER_CABLE
    assert decision.quantity_decision == "include"
    assert decision.cost_decision == "include"


@pytest.mark.parametrize(
    "name",
    [
        "Прокладка кабеля слаботочной сети по конструкциям",
        "Прокладка самонесущего кабеля ВОЛС по стальным опорам",
        "Прокладка кабеля сети связи",
        "Прокладка кабеля КИП и автоматики",
        "Прокладка и присоединение проводника заземляющего из полосовой оцинкованной стали",
    ],
)
def test_explicit_low_current_context_wins_over_generic_cable(name: str) -> None:
    decision = _matcher().match(_row(name))

    assert decision.category is TargetWorkCategory.LOW_CURRENT_CABLE
    assert decision.quantity_decision == "include"
    assert decision.cost_decision == "include"


@pytest.mark.parametrize(
    "name",
    [
        "Разводка по устройствам и подключение жил электрических кабелей",
        "Прокладка кабеля с подключением жил",
        "Прокладка кабеля слаботочной сети: разводка по устройствам",
    ],
)
def test_cable_termination_and_device_wiring_are_excluded(name: str) -> None:
    decision = _matcher().match(_row(name))

    assert decision.category is None
    assert decision.quantity_decision == "exclude"
    assert decision.cost_decision == "exclude"
    assert decision.requires_manual_review is False


@pytest.mark.parametrize(
    "name",
    [
        "Монтаж кабельных коробов и лотков",
        "Устройство поддержек для прокладки силового кабеля",
    ],
)
def test_power_cable_includes_route_supports_boxes_and_trays(name: str) -> None:
    decision = _matcher().match(_row(name))

    assert decision.category is TargetWorkCategory.POWER_CABLE
    assert decision.quantity_decision == "include"
    assert decision.cost_decision == "include"


def test_metal_cost_is_cost_only_but_installation_keeps_quantity_and_cost() -> None:
    cost = _matcher().match(_row("Стоимость м/к каркаса", unit="т"))
    install = _matcher().match(_row("Монтаж м/к фундаментов и ростверков", unit="т"))

    assert cost.category is TargetWorkCategory.METAL_STRUCTURES
    assert (cost.quantity_decision, cost.cost_decision) == ("exclude", "include")
    assert install.category is TargetWorkCategory.METAL_STRUCTURES
    assert (install.quantity_decision, install.cost_decision) == ("include", "include")


def test_deterministic_cost_only_persists_cost_without_quantity() -> None:
    row = _row("Стоимость м/к каркаса", unit="т")
    decision = _matcher().match(row)

    aggregated = aggregate_rows([row], [decision], drawing_code_mode="strict", strict=True)

    assert len(aggregated) == 1
    assert aggregated[0].quantity == Decimal("0")
    assert aggregated[0].total_cost == Decimal("1500")
    assert aggregated[0].quantity_rows == ()
    assert aggregated[0].cost_rows == ("row-1",)


@pytest.mark.parametrize(
    "name",
    [
        "Монтаж м/к мачт-молниеотводов",
        "Монтаж м/к антенных мачт",
        "Изготовление м/к емкостей",
    ],
)
def test_non_comparable_metal_work_is_not_auto_included(name: str) -> None:
    decision = _matcher().match(_row(name, unit="т"))

    assert decision.category is None
    assert decision.quantity_decision == "exclude"
    assert decision.cost_decision == "exclude"


@pytest.mark.parametrize(
    ("name", "unit"),
    [
        ("Устройство основания из буроопускных металлических свай", "м"),
        ("Монтаж железобетонных опор ВЛ", "т"),
        ("Армирование монолитных железобетонных конструкций", "т"),
    ],
)
def test_incompatible_units_do_not_auto_include_quantity(name: str, unit: str) -> None:
    decision = _matcher().match(_row(name, unit=unit))

    assert decision.quantity_decision != "include"
    assert decision.requires_manual_review is True


@pytest.mark.parametrize(
    "name",
    [
        "Испытание свай статической нагрузкой",
        "Контроль свай после погружения",
        "Динамическое испытание свай",
    ],
)
def test_pile_tests_are_not_pile_foundation_work(name: str) -> None:
    decision = _matcher().match(_row(name, unit="шт"))

    assert decision.category is None
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "exclude")


@pytest.mark.parametrize(
    ("quantity", "cost", "manual"),
    [
        (None, None, False),
        (Decimal("0"), Decimal("0"), False),
        (Decimal("0"), Decimal("300"), False),
        (Decimal("8"), Decimal("0"), False),
    ],
)
def test_empty_or_zero_only_rows_never_create_manual_review(
    quantity: Decimal | None, cost: Decimal | None, manual: bool
) -> None:
    decision = _matcher().match(
        _row("Прокладка силового кабеля", quantity=quantity, cost=cost)
    )

    assert decision.requires_manual_review is manual
    assert decision.quantity_decision == ("include" if quantity is not None else "exclude")
    assert decision.cost_decision == ("include" if cost is not None else "exclude")


@pytest.mark.parametrize("name", (None, "", "   \u00a0   "))
def test_blank_work_name_with_no_values_is_ignored_without_manual_review(name: str | None) -> None:
    decision = _matcher().match(_row(name, quantity=None, cost=None))

    assert decision.category is None
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "exclude")
    assert decision.requires_manual_review is False


def test_exact_confirmed_feedback_beats_a_generic_rule() -> None:
    example = ConfirmedExample(
        example_id="feedback-1",
        source_text="Прокладка кабеля слаботочной сети по конструкции",
        normalized_text="прокладка кабеля слаботочной сети по конструкции",
        category=TargetWorkCategory.POWER_CABLE,
        quantity_decision="exclude",
        cost_decision="include",
        unit="м",
        source_type="visr",
        confirmed_by="review",
        rule_version="1.0",
    )

    decision = _matcher(examples=(example,)).match(_row(example.source_text))

    assert decision.category is TargetWorkCategory.POWER_CABLE
    assert (decision.quantity_decision, decision.cost_decision) == ("exclude", "include")
    assert decision.matching_strategy == "confirmed_dictionary"


def test_exact_phrase_cache_is_bounded_for_many_unique_terms() -> None:
    _exact_token_pattern.cache_clear()
    for index in range(512):
        _exact_token_pattern(f"длинный-токен-{index}")

    info = _exact_token_pattern.cache_info()
    assert info.currsize <= info.maxsize == 256

from decimal import Decimal
from pathlib import Path

from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import load_confirmed_examples
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher, ReviewApproval
from report_processor.drawing_card.models import (
    DrawingSourceLocation,
    DrawingSourceRow,
    TargetWorkCategory,
)


def _row(row_id: str, name: str, unit: str, quantity="1", cost="2") -> DrawingSourceRow:
    return DrawingSourceRow(
        row_id=row_id,
        location=DrawingSourceLocation("file", "0906.xlsx", "ВиСР", 10, ("A10",)),
        object_index_raw="0906",
        drawing_code_raw="CODE-1",
        work_name_raw=name,
        unit_raw=unit,
        remaining_quantity=Decimal(quantity) if quantity is not None else None,
        remaining_total_cost=Decimal(cost) if cost is not None else None,
        formula_values=(),
        cached_values=(),
        source_document_type="visr",
        source_period="2026-07",
        source_revision="1",
        status="OK",
        warnings=(),
    )


def _matcher(project_root: Path) -> DrawingRowMatcher:
    rules = load_rules(project_root / "config" / "drawing_card" / "rules.json")
    examples = load_confirmed_examples(
        project_root / "config" / "drawing_card" / "confirmed_examples.jsonl"
    )
    return DrawingRowMatcher(rules, examples, rag_mode="off")


def test_power_and_low_current_are_not_inferred_by_complement(project_root: Path) -> None:
    matcher = _matcher(project_root)
    power = matcher.match(_row("1", "Прокладка силового кабеля", "м"))
    low = matcher.match(_row("2", "Прокладка слаботочного кабеля", "м"))
    unknown = matcher.match(_row("3", "Прокладка кабеля в коробе", "м"))
    assert power.category == TargetWorkCategory.POWER_CABLE
    assert low.category == TargetWorkCategory.LOW_CURRENT_CABLE
    assert unknown.category is None
    assert unknown.requires_manual_review


def test_quantity_and_cost_decisions_are_separate(project_root: Path) -> None:
    matcher = _matcher(project_root)
    decision = matcher.match(
        _row("4", "Стоимость металлоконструкций", "руб", quantity="5", cost="100")
    )
    assert decision.category == TargetWorkCategory.METAL_STRUCTURES
    assert decision.quantity_decision == "exclude"
    assert decision.cost_decision == "include"


def test_unit_mismatch_blocks_quantity_only(project_root: Path) -> None:
    matcher = _matcher(project_root)
    decision = matcher.match(_row("5", "Монтаж металлоконструкций", "м"))
    assert decision.quantity_decision == "review"
    assert decision.cost_decision == "include"
    assert decision.requires_manual_review


def test_confirmed_negative_example_excludes(project_root: Path) -> None:
    matcher = _matcher(project_root)
    decision = matcher.match(_row("6", "Гидравлическое испытание трубопроводов", "км"))
    assert decision.category is None
    assert decision.quantity_decision == "exclude"
    assert not decision.requires_manual_review


def test_abbreviations_and_montage_use_token_boundaries(project_root: Path) -> None:
    matcher = _matcher(project_root)
    irrelevant = matcher.match(_row("7", "Разработка грунта (прим. Демонтаж)", "м3"))
    valve = matcher.match(_row("8", "Монтаж технологической ЗРА Д мм 57-89", "шт"))
    assert irrelevant.category is None
    assert irrelevant.quantity_decision == "exclude"
    assert not irrelevant.requires_manual_review
    assert valve.category == TargetWorkCategory.TT_VALVES_INSTALLATION


def test_confirmed_structural_negatives_do_not_fill_card(project_root: Path) -> None:
    matcher = _matcher(project_root)
    tray = matcher.match(_row("9", "Монтаж кабельных коробов, лотков", "м"))
    supports = matcher.match(
        _row("10", "Монтаж опорных конструкций для крепления трубопроводов", "т")
    )
    unrelated = matcher.match(_row("11", "Затраты, связанные с перевозкой сыпучих грузов", "руб"))
    control = matcher.match(
        _row("12", "Контроль изоляции трубопровода методом катодной поляризации", "км")
    )
    equipment = matcher.match(_row("13", "Силовое электрооборудование", "компл"))
    assert tray.category is None and not tray.requires_manual_review
    assert supports.category is None and not supports.requires_manual_review
    assert unrelated.category is None and not unrelated.requires_manual_review
    assert control.category is None and not control.requires_manual_review
    assert equipment.category is None and not equipment.requires_manual_review


def test_imported_reject_explicitly_excludes_row(project_root: Path) -> None:
    rules = load_rules(project_root / "config" / "drawing_card" / "rules.json")
    matcher = DrawingRowMatcher(
        rules,
        (),
        rag_mode="off",
        approvals={"rejected": ReviewApproval("rejected", "reject", None)},
    )
    decision = matcher.match(_row("rejected", "Монтаж металлоконструкций", "т"))
    assert decision.category is None
    assert decision.quantity_decision == "exclude"
    assert decision.cost_decision == "exclude"
    assert decision.matching_strategy == "manual_review"

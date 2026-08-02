from __future__ import annotations

from decimal import Decimal

import pytest

from report_processor.reconciliation_grouping.packages import build_reconciliation_packages
from report_processor.reconciliation_review.models import ReviewGroup, ReviewRow


def _row(row_id: str, name: str, *, quantity: str = "1", cost: str = "2") -> ReviewRow:
    return ReviewRow(
        row_id=row_id,
        display_name=name,
        unit="м",
        quantity=Decimal(quantity),
        cost=Decimal(cost),
        proposed_category="Кабельные работы",
    )


def _group(group_id: str, row: ReviewRow) -> ReviewGroup:
    return ReviewGroup(
        group_id=group_id,
        version=f"version-{group_id}",
        normalized_name=row.display_name.casefold() if row.display_name else None,
        normalized_unit=row.unit,
        member_ids=(row.row_id,),
        proposed_category=row.proposed_category,
    )


def test_hard_power_low_current_conflict_is_explicit_and_never_safe() -> None:
    power = _row("row-power", "Монтаж силового кабеля")
    low_current = _row("row-low", "Монтаж слаботочного кабеля")
    groups = (_group("group-power", power), _group("group-low", low_current))

    result = build_reconciliation_packages((power, low_current), groups)

    assert any(exception.reason == "hard_low_current_vs_power" for exception in result.exceptions)
    assert result.packages[0].safe is False
    assert result.packages[0].member_group_ids == ("group-low", "group-power")


def test_installation_and_cost_conflict_is_explicit_before_any_similarity() -> None:
    work = _row("row-work", "Монтаж силового кабеля")
    price = _row("row-price", "Стоимость монтажа силового кабеля")
    groups = (_group("group-work", work), _group("group-price", price))

    result = build_reconciliation_packages((work, price), groups)

    assert any(exception.reason == "hard_cost_vs_installation" for exception in result.exceptions)


def test_visible_rows_have_one_exact_group_family_and_package_path_in_stable_order() -> None:
    first = _row("row-b", "Монтаж силового кабеля")
    second = _row("row-a", "Монтаж силового кабеля")
    groups = (_group("group-b", first), _group("group-a", second))

    first_result = build_reconciliation_packages((first, second), groups)
    second_result = build_reconciliation_packages((second, first), tuple(reversed(groups)))

    assert first_result.packages == second_result.packages
    assert first_result.families == second_result.families
    assert first_result.packages[0].member_group_ids == ("group-a", "group-b")
    assert {
        group_id for package in first_result.packages for group_id in package.member_group_ids
    } == {
        "group-a",
        "group-b",
    }


def test_zero_rows_must_be_removed_before_exact_review_grouping() -> None:
    zero = _row("row-zero", "Монтаж силового кабеля", quantity="0", cost="0")
    group = _group("group-zero", zero)

    with pytest.raises(ValueError, match="zero-activity"):
        build_reconciliation_packages((zero,), (group,))


def test_explicit_negative_feedback_and_category_availability_become_exceptions() -> None:
    first = _row("row-a", "Монтаж силового кабеля")
    second = _row("row-b", "Монтаж силового кабеля")
    groups = (_group("group-a", first), _group("group-b", second))

    result = build_reconciliation_packages(
        (first, second),
        groups,
        category_availability={"group-a": frozenset({"Другая категория"})},
        negative_pairs=(("group-a", "group-b"),),
    )

    assert {exception.reason for exception in result.exceptions} >= {
        "category_unavailable",
        "explicit_negative_feedback",
    }
    assert result.packages[0].safe is False

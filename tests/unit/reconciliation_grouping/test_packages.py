from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from report_processor.reconciliation_grouping.models import (
    FEATURE_CONTRACT_VERSION,
    FEATURE_RULE_VERSION,
    PackageVersionContext,
)
from report_processor.reconciliation_grouping.packages import build_reconciliation_packages
from report_processor.reconciliation_review.models import ReviewGroup, ReviewMode, ReviewRow


def _context() -> PackageVersionContext:
    return PackageVersionContext(
        source_digests=("source-digest-a",),
        target_digest="target-digest-a",
        category_catalog_version="catalog-v1",
        feature_contract_version=FEATURE_CONTRACT_VERSION,
        rule_version=FEATURE_RULE_VERSION,
        model_revision="local-model-r1",
    )


def _build(rows: tuple[ReviewRow, ...], groups: tuple[ReviewGroup, ...], **kwargs):
    return build_reconciliation_packages(rows, groups, version_context=_context(), **kwargs)


def _row(
    row_id: str,
    name: str,
    *,
    unit: str = "м",
    quantity: str = "1",
    cost: str = "2",
    category: str | None = "Кабельные работы",
) -> ReviewRow:
    return ReviewRow(
        row_id=row_id,
        display_name=name,
        unit=unit,
        quantity=Decimal(quantity),
        cost=Decimal(cost),
        proposed_category=category,
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

    result = _build((power, low_current), groups)

    assert any(exception.reason == "hard_low_current_vs_power" for exception in result.exceptions)
    assert not any(package.safe for package in result.packages)
    assert {group_id for package in result.packages for group_id in package.member_group_ids} == {
        "group-low",
        "group-power",
    }


def test_installation_and_cost_conflict_is_explicit_before_any_similarity() -> None:
    work = _row("row-work", "Монтаж силового кабеля")
    price = _row("row-price", "Стоимость монтажа силового кабеля")
    groups = (_group("group-work", work), _group("group-price", price))

    result = _build((work, price), groups)

    assert any(exception.reason == "hard_cost_vs_installation" for exception in result.exceptions)


def test_visible_rows_have_one_exact_group_family_and_package_path_in_stable_order() -> None:
    first = _row("row-b", "Монтаж силового кабеля")
    second = _row("row-a", "Монтаж силового кабеля")
    groups = (_group("group-b", first), _group("group-a", second))

    first_result = _build((first, second), groups)
    second_result = _build((second, first), tuple(reversed(groups)))

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
        _build((zero,), (group,))


def test_explicit_negative_feedback_and_category_availability_become_exceptions() -> None:
    first = _row("row-a", "Монтаж силового кабеля")
    second = _row("row-b", "Монтаж силового кабеля")
    groups = (_group("group-a", first), _group("group-b", second))

    result = _build(
        (first, second),
        groups,
        category_availability={"group-a": frozenset({"Другая категория"})},
        negative_pairs=(("group-a", "group-b"),),
    )

    assert {exception.reason for exception in result.exceptions} >= {
        "category_unavailable",
        "explicit_negative_feedback",
    }
    assert any(not package.safe for package in result.packages)


def test_cross_boundary_categories_and_modes_remain_independently_safe() -> None:
    quantity = _row("row-quantity", "Монтаж силового кабеля", category="Категория A")
    cost_only = _row("row-cost", "Монтаж силового кабеля", category="Категория B")
    groups = (_group("group-quantity", quantity), _group("group-cost", cost_only))

    result = _build(
        (quantity, cost_only),
        groups,
        modes={"group-cost": ReviewMode.COST_ONLY},
    )

    assert not result.exceptions
    assert len(result.packages) == 2
    assert all(package.safe for package in result.packages)


def test_quantity_cost_requires_recognized_exact_units_without_conversion() -> None:
    meters = _row("row-m", "Монтаж силового кабеля", unit="м")
    kilometers = _row("row-km", "Монтаж силового кабеля", unit="км")
    unknown = _row("row-unknown", "Монтаж силового кабеля", unit="условная единица")
    groups = (
        _group("group-m", meters),
        _group("group-km", kilometers),
        _group("group-unknown", unknown),
    )

    result = _build((meters, kilometers, unknown), groups)

    assert {exception.reason for exception in result.exceptions} >= {
        "quantity_cost_unit_mismatch",
        "quantity_cost_unit_unrecognized",
    }
    assert not any(package.safe for package in result.packages)


def test_cost_only_packages_remain_explicitly_eligible_with_different_exact_units() -> None:
    meters = _row("row-m", "Монтаж силового кабеля", unit="м")
    kilometers = _row("row-km", "Монтаж силового кабеля", unit="км")
    groups = (_group("group-m", meters), _group("group-km", kilometers))

    result = _build(
        (meters, kilometers),
        groups,
        modes={"group-m": ReviewMode.COST_ONLY, "group-km": ReviewMode.COST_ONLY},
    )

    assert not result.exceptions
    assert len(result.packages) == 1
    assert result.packages[0].safe is True


def test_dangling_negative_feedback_endpoint_is_rejected_after_group_materialization() -> None:
    row = _row("row-a", "Монтаж силового кабеля")
    group = _group("group-a", row)

    with pytest.raises(ValueError, match="unknown materialized group"):
        _build((row,), (group,), negative_pairs=(("group-a", "removed-group"),))


def test_package_without_a_proposed_category_is_never_mass_acceptable() -> None:
    row = _row("row-new", "Новая работа", category=None)
    group = _group("group-new", row)

    result = _build((row,), (group,))

    assert len(result.packages) == 1
    assert result.packages[0].package_key[0] == ""
    assert result.packages[0].safe is False


def test_unrelated_unknown_work_types_remain_isolated_and_manual() -> None:
    first = _row("row-clean", "Очистка поверхности")
    second = _row("row-paint", "Покраска поверхности")
    groups = (_group("group-clean", first), _group("group-paint", second))

    result = _build((first, second), groups)

    assert len(result.families) == len(result.packages) == 2
    assert {package.member_group_ids for package in result.packages} == {
        ("group-clean",),
        ("group-paint",),
    }
    assert not any(package.safe for package in result.packages)


def test_exceptions_are_separate_from_a_mass_acceptable_safe_remainder() -> None:
    first = _row("row-a", "Монтаж силового кабеля")
    second = _row("row-b", "Монтаж силового кабеля")
    safe = _row("row-c", "Монтаж силового кабеля")
    groups = (
        _group("group-a", first),
        _group("group-b", second),
        _group("group-c", safe),
    )

    result = _build((first, second, safe), groups, negative_pairs=(("group-a", "group-b"),))

    safe_packages = [package for package in result.packages if package.safe]
    manual_packages = [package for package in result.packages if not package.safe]
    assert len(safe_packages) == 1
    assert safe_packages[0].member_group_ids == ("group-c",)
    assert len(manual_packages) == 1
    assert manual_packages[0].member_group_ids == ("group-a", "group-b")
    assert len(manual_packages[0].family_ids) == 2
    assert {exception.reason for exception in result.exceptions} == {"explicit_negative_feedback"}
    assert {
        group_id
        for package in result.packages
        if not package.safe
        for group_id in package.member_group_ids
    } == {
        "group-a",
        "group-b",
    }


def test_manual_exception_packages_never_merge_across_hard_boundaries() -> None:
    first_a = _row("row-a", "Монтаж силового кабеля", category="Категория A")
    first_b = _row("row-b", "Монтаж силового кабеля", category="Категория A")
    second_a = _row("row-c", "Монтаж силового кабеля", category="Категория B")
    second_b = _row("row-d", "Монтаж силового кабеля", category="Категория B")
    groups = (
        _group("group-a", first_a),
        _group("group-b", first_b),
        _group("group-c", second_a),
        _group("group-d", second_b),
    )

    first_result = _build(
        (first_a, first_b, second_a, second_b),
        groups,
        negative_pairs=(("group-a", "group-b"), ("group-c", "group-d")),
    )
    second_result = _build(
        (second_b, second_a, first_b, first_a),
        tuple(reversed(groups)),
        negative_pairs=(("group-a", "group-b"), ("group-c", "group-d")),
    )

    manual_packages = [package for package in first_result.packages if not package.safe]
    assert first_result.packages == second_result.packages
    assert len(manual_packages) == 2
    assert {package.member_group_ids for package in manual_packages} == {
        ("group-a", "group-b"),
        ("group-c", "group-d"),
    }
    assert all(len(package.family_ids) == 2 for package in manual_packages)


def test_package_versions_bind_every_consequential_version_input() -> None:
    row = _row("row-a", "Монтаж силового кабеля")
    group = _group("group-a", row)
    baseline_context = _context()
    baseline = build_reconciliation_packages((row,), (group,), version_context=baseline_context)
    expected = (baseline.families[0].version, baseline.packages[0].version)

    changed_contexts = (
        replace(baseline_context, source_digests=("source-digest-b",)),
        replace(baseline_context, target_digest="target-digest-b"),
        replace(baseline_context, category_catalog_version="catalog-v2"),
        replace(baseline_context, feature_contract_version="ReconciliationFeatureContract-1.1"),
        replace(baseline_context, rule_version="reconciliation-features-2"),
        replace(baseline_context, model_revision="local-model-r2"),
    )

    for context in changed_contexts:
        changed = build_reconciliation_packages((row,), (group,), version_context=context)
        assert (changed.families[0].version, changed.packages[0].version) != expected

from __future__ import annotations

from decimal import Decimal
from time import perf_counter

import pytest

from report_processor.hierarchy import (
    HierarchyEntry,
    filter_aggregate_rows,
    is_ancestor_position,
    parse_position_code,
)


def entry(
    row_id: str,
    position: str | None,
    amount: str | None,
    *,
    context: tuple[str, ...] = (),
    transactional: bool = False,
) -> HierarchyEntry:
    return HierarchyEntry(
        row_id=row_id,
        position_code=position,
        amount=None if amount is None else Decimal(amount),
        context=context,
        is_transactional=transactional,
    )


def test_exact_dot_segments_do_not_make_610_a_child_of_61() -> None:
    parent = parse_position_code("6.1")

    assert parent is not None
    assert is_ancestor_position(parent, parse_position_code("6.1.3"))
    assert not is_ancestor_position(parent, parse_position_code("6.10"))


def test_numeric_fraction_is_not_an_automatic_hierarchy_code() -> None:
    assert parse_position_code(0.10829999949783087) is None
    assert parse_position_code(Decimal("0.25")) is None
    assert parse_position_code("2.7.1") is not None


@pytest.mark.parametrize("depth", (3, 4, 5))
def test_nested_aggregate_parents_are_excluded_at_each_depth(depth: int) -> None:
    positions = ["6"]
    for _part in range(1, depth):
        positions.append(positions[-1] + ".1")
    leaf = positions[-1] + ".3"
    result = filter_aggregate_rows(
        tuple(entry(f"row-{index}", code, "10") for index, code in enumerate((*positions, leaf)))
    )

    assert result.parent_row_ids == tuple(f"row-{index}" for index in range(len(positions)))
    assert result.leaf_row_ids == (f"row-{len(positions)}",)


def test_suffix_variant_is_a_sibling_and_leaf_order_is_preserved() -> None:
    result = filter_aggregate_rows(
        (
            entry("parent", "6.1", "20"),
            entry("child", "6.1.3", "20"),
            entry("suffix", "6.1а", "5"),
            entry("neighbour", "6.10", "7"),
        )
    )

    assert result.parent_row_ids == ("parent",)
    assert result.leaf_row_ids == ("child", "suffix", "neighbour")


def test_cost_match_keeps_only_direct_children_in_parent_comparison() -> None:
    result = filter_aggregate_rows(
        (
            entry("root", "1", "100"),
            entry("first-child", "1.1", "40"),
            entry("nested", "1.1.1", "40"),
            entry("second-child", "1.2", "60"),
        )
    )

    assert result.parent_row_ids == ("root", "first-child")
    assert result.leaf_row_ids == ("nested", "second-child")
    assert not any(issue.code == "HIERARCHY_COST_MISMATCH" for issue in result.issues)


def test_transactional_parent_is_retained_and_nested_resources_are_excluded() -> None:
    result = filter_aggregate_rows(
        (
            entry("section", "2.7.1.3.10", "13728"),
            entry("work", "2.7.1.3.10.7", "11770", transactional=True),
            entry("material", "2.7.1.3.10.7.1", "1958", transactional=True),
        )
    )

    assert result.parent_row_ids == ("section",)
    assert result.resource_detail_row_ids == ("material",)
    assert result.leaf_row_ids == ("work",)
    assert not any(issue.code == "HIERARCHY_COST_MISMATCH" for issue in result.issues)


def test_cost_mismatch_is_reported_without_losing_leaves() -> None:
    result = filter_aggregate_rows(
        (
            entry("parent", "2", "12"),
            entry("child-a", "2.1", "5"),
            entry("child-b", "2.2", "6"),
            entry("unrelated", "9", "3"),
        )
    )

    issue_codes = {issue.code for issue in result.issues}
    assert "HIERARCHY_COST_MISMATCH" in issue_codes
    assert result.leaf_row_ids == ("child-a", "child-b", "unrelated")
    mismatch = next(issue for issue in result.issues if issue.code == "HIERARCHY_COST_MISMATCH")
    assert mismatch.position_code == "2"
    assert mismatch.parent_amount == Decimal("12")
    assert mismatch.direct_children_amount == Decimal("11")
    assert mismatch.delta == Decimal("1")
    assert mismatch.tolerance == Decimal("0.01")


def test_missing_cost_gap_and_duplicate_are_reported_without_losing_rows() -> None:
    result = filter_aggregate_rows(
        (
            entry("parent", "2", "11"),
            entry("child-a", "2.1", "5"),
            entry("child-b", "2.3", None),
            entry("duplicate", "2.3", "6"),
            entry("unrelated", "9", "3"),
            entry("missing-code", None, "2"),
        )
    )

    issue_codes = {issue.code for issue in result.issues}
    assert {
        "HIERARCHY_MISSING_DIRECT_CHILD_COST",
        "HIERARCHY_POSITION_GAP",
        "HIERARCHY_DUPLICATE_POSITION",
    } <= issue_codes
    assert result.leaf_row_ids == ("child-a", "child-b", "duplicate", "unrelated", "missing-code")


def test_same_position_in_separate_contexts_does_not_create_parent_or_duplicate() -> None:
    result = filter_aggregate_rows(
        (
            entry("object-a", "1.1", "5", context=("object-a",)),
            entry("object-b", "1.1", "6", context=("object-b",)),
        )
    )

    assert result.parent_row_ids == ()
    assert result.leaf_row_ids == ("object-a", "object-b")
    assert not any(issue.code == "HIERARCHY_DUPLICATE_POSITION" for issue in result.issues)


def test_duplicate_parent_positions_are_reported_but_not_silently_excluded() -> None:
    result = filter_aggregate_rows(
        (
            entry("duplicate-a", "2", "11"),
            entry("duplicate-b", "2", "12"),
            entry("child", "2.1", "11"),
        )
    )

    assert result.parent_row_ids == ()
    assert result.leaf_row_ids == ("duplicate-a", "duplicate-b", "child")
    assert any(issue.code == "HIERARCHY_DUPLICATE_POSITION" for issue in result.issues)


def test_large_mostly_leaf_input_does_not_use_quadratic_parent_scanning() -> None:
    entries = tuple(entry(f"row-{index}", f"{index + 1}", "1") for index in range(50_000))

    started = perf_counter()
    result = filter_aggregate_rows(entries)

    assert result.leaf_row_ids == tuple(f"row-{index}" for index in range(50_000))
    assert result.parent_row_ids == ()
    assert perf_counter() - started < 5

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from report_processor.reconciliation_grouping.features import (
    extract_features,
    normalize_text,
    unit_family,
)
from report_processor.reconciliation_grouping.models import GroupInput, UnitFamily
from report_processor.reconciliation_grouping.zero_activity import is_zero_activity, partition_rows
from report_processor.reconciliation_review.models import ReviewGroup, ReviewMode, ReviewRow


def _row(row_id: str, *, quantity: str | None = "1", cost: str | None = "2") -> ReviewRow:
    return ReviewRow(
        row_id=row_id,
        display_name="Монтаж силового кабеля DN 50, 10 кВ",
        unit="м",
        quantity=Decimal(quantity) if quantity is not None else None,
        cost=Decimal(cost) if cost is not None else None,
        proposed_category="Кабельные работы",
    )


def _group(rows: tuple[ReviewRow, ...]) -> ReviewGroup:
    return ReviewGroup(
        group_id="group-cable",
        version="group-version",
        normalized_name="Монтаж силового кабеля DN 50, 10 кВ",
        normalized_unit="м",
        member_ids=tuple(sorted(row.row_id for row in rows)),
        proposed_category="Кабельные работы",
    )


def test_zero_activity_requires_two_finite_decimal_zeros_and_preserves_source_rows() -> None:
    rows = (_row("zero", quantity="0", cost="0"), _row("cost", quantity="0", cost="1"))

    partition = partition_rows(rows)

    assert tuple(row.row_id for row in partition.source_rows) == ("zero", "cost")
    assert tuple(row.row_id for row in partition.visible_rows) == ("cost",)
    assert tuple(row.row_id for row in partition.hidden_rows) == ("zero",)
    assert not is_zero_activity(SimpleNamespace(quantity=Decimal("NaN"), cost=Decimal("0")))
    assert not is_zero_activity(SimpleNamespace(quantity=0, cost=Decimal("0")))


def test_feature_contract_normalizes_and_retains_critical_typed_fields() -> None:
    row = _row("one")
    feature = extract_features(GroupInput(_group((row,)), (row,), ReviewMode.QUANTITY_COST))

    assert normalize_text("  Ёлка—КАБЕЛЬ ") == "елка кабель"
    assert unit_family("м²") is UnitFamily.AREA
    assert feature.action == "installation"
    assert feature.object_kind == "cable"
    assert feature.critical_modifiers == ("power",)
    assert feature.typed_modifiers == ("diameter_dn:50", "voltage_kv:10")
    assert feature.unit_family is UnitFamily.LENGTH


def test_group_input_refuses_membership_drift() -> None:
    row = _row("one")
    group = _group((row,))

    with pytest.raises(ValueError, match="exact ReviewGroup membership"):
        GroupInput(group, (), ReviewMode.QUANTITY_COST)

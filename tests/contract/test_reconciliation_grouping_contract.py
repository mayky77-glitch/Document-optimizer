from __future__ import annotations

from decimal import Decimal

from report_processor.reconciliation_grouping import (
    FEATURE_CONTRACT_VERSION,
    PACKAGE_CONTRACT_VERSION,
    build_reconciliation_packages,
)
from report_processor.reconciliation_review.models import ReviewGroup, ReviewRow


def test_reconciliation_grouping_contract_versions_and_privacy_projection() -> None:
    row = ReviewRow(
        row_id="opaque-row-1",
        display_name="Монтаж кабеля из секретного файла.xlsx",
        unit="м",
        quantity=Decimal("1"),
        cost=Decimal("2"),
        proposed_category="Кабельные работы",
    )
    group = ReviewGroup(
        group_id="opaque-group-1",
        version="group-version",
        normalized_name="монтаж кабеля из секретного файла xlsx",
        normalized_unit="м",
        member_ids=(row.row_id,),
        proposed_category=row.proposed_category,
    )

    payload = build_reconciliation_packages((row,), (group,)).public_payload()

    assert FEATURE_CONTRACT_VERSION == "ReconciliationFeatureContract-1.0"
    assert PACKAGE_CONTRACT_VERSION == "ReconciliationPackageContract-1.0"
    assert payload["feature_contract_version"] == FEATURE_CONTRACT_VERSION
    assert payload["package_contract_version"] == PACKAGE_CONTRACT_VERSION
    assert "secret" not in repr(payload)
    assert "xlsx" not in repr(payload)
    assert "display_name" not in repr(payload)

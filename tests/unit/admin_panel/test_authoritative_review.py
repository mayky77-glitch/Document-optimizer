from decimal import Decimal

from report_processor.admin_panel.reconciliation_review_presentation import (
    reconciliation_review_payload,
)
from report_processor.reconciliation_review import ReviewRow, build_review_groups


def test_safe_review_payload_has_controlled_two_decimal_facts_without_internal_metadata() -> None:
    row = ReviewRow("source:1", "Монтаж трубы", "м", Decimal("1.235"), Decimal("2.345"))
    (group,) = build_review_groups((row,))

    payload = reconciliation_review_payload((group,), {row.row_id: row})
    member = payload[0]["members"][0]

    assert member == {
        "row_id": "source:1",
        "display_name": "Монтаж трубы",
        "source_unit": "м",
        "quantity": "1.24",
        "cost": "2.35",
    }
    serialized = repr(payload)
    assert all(
        token not in serialized
        for token in (
            "path",
            "sheet",
            "coordinate",
            "provenance",
            "warnings",
            "metrics",
            "review_journal_only",
        )
    )

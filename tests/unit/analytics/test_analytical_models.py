from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from report_processor.analytics import AnalyticalStoreError
from tests.fixtures.analytics.builders import rule_set, source_row, target_row


def test_analytics_models_keep_full_provenance_classification_status_and_warnings():
    source = source_row()
    target = target_row(warnings=("TARGET_WARNING",))
    rules = rule_set()

    source_provenance = (
        source.source_file_id,
        source.source_filename,
        source.source_sheet,
        source.source_row,
    )
    assert source_provenance == (
        "source-a",
        "source-a.xlsx",
        "Sheet 1",
        17,
    )
    assert source.classification == "source_detail"
    assert source.status == "WARNING"
    assert source.warnings == ("SOURCE_WARNING",)
    assert target.target_source_fingerprint == "a" * 64
    assert target.classification == "target_detail"
    assert target.warnings == ("TARGET_WARNING",)
    assert rules.clauses == (("field", "equals", "value"),)
    assert rules.warnings == ("RULE_WARNING",)


@pytest.mark.parametrize(
    "invalid_quantity",
    [
        Decimal("100000000000000000000.000000000000000000"),
        Decimal("1.0000000000000000001"),
    ],
)
def test_decimal_38_18_rejects_overflow_and_excess_scale_without_rounding(
    invalid_quantity: Decimal,
):
    with pytest.raises(
        (AnalyticalStoreError, ValueError), match=r"Decimal|decimal|scale|precision"
    ):
        replace(source_row(), contract_quantity=invalid_quantity).validate()


def test_decimal_38_18_rejects_float_without_coercion():
    with pytest.raises((AnalyticalStoreError, TypeError, ValueError), match=r"Decimal|float"):
        replace(source_row(), contract_quantity=1.25).validate()  # type: ignore[arg-type]


def test_target_requires_nonempty_source_identity_and_fingerprint():
    with pytest.raises((AnalyticalStoreError, ValueError), match="target_source_id"):
        replace(target_row(), target_source_id="").validate()
    with pytest.raises((AnalyticalStoreError, ValueError), match="fingerprint"):
        replace(target_row(), target_source_fingerprint="").validate()


def test_target_id_is_deterministic_sha256_of_its_stable_identity():
    target = target_row(target_row_id="")
    validated = target.validate()

    assert validated.target_row_id == target.deterministic_id()
    assert len(validated.target_row_id) == 64
    assert all(character in "0123456789abcdef" for character in validated.target_row_id)

from __future__ import annotations

from decimal import Decimal

from report_processor.normalization import (
    NormalizationConfig,
    NormalizationResult,
    NormalizedBusinessKey,
    NormalizedSourceRow,
    normalize_training_rows,
)


def test_block7_rows_are_lossless_block8_input_and_public_models_are_exported(
    make_training_row,
) -> None:
    source = make_training_row()

    result = normalize_training_rows((source,), config=NormalizationConfig())

    assert isinstance(result, NormalizationResult)
    assert isinstance(result.rows[0], NormalizedSourceRow)
    assert isinstance(result.rows[0].business_key, NormalizedBusinessKey)
    assert result.rows[0].source_row is source
    assert result.rows[0].source_row.contract_quantity == Decimal("1.250")
    assert result.rows[0].source_row.total_cost == Decimal("1234.50")
    assert result.rows[0].line_id != source.line_id

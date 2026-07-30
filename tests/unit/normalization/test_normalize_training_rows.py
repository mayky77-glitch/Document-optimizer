from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal

from report_processor.normalization import NormalizationConfig, normalize_training_rows

from report_processor.training_data import (
    DataQualityStatus,
    FormulaErrorCode,
    TrainingDataRow,
)


def make_training_row(
    *,
    source_file_id: str = "source-a",
    source_row_id: str = "source-a:17",
    object_code: str = "0007",
    work_name: str = "Монтаж трубопровда",
    unit: str = "пог. м",
    period_cost: Decimal = Decimal("1234.50"),
    warnings: tuple[str, ...] = ("SOURCE_WARNING",),
) -> TrainingDataRow:
    return TrainingDataRow(
        document_type="ks2",
        document_period="2026-06",
        source_file_id=source_file_id,
        source_filename="КС-2 № 01.xlsx",
        source_sheet="Лист １",
        source_row=17,
        source_row_id=source_row_id,
        object_code=object_code,
        subobject_code="0003",
        position_code="000042",
        cost_type_code="СМР",
        drawing_code="Ч-007",
        basis_code="ГЭСН 01-01",
        work_name_raw=work_name,
        work_name_normalized=work_name.casefold(),
        unit_raw=unit,
        unit_normalized=unit.casefold(),
        contract_quantity=Decimal("001.250"),
        period_quantity=Decimal("2.50"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=Decimal("10.00"),
        contract_cost=None,
        period_cost=period_cost,
        cumulative_cost=None,
        total_cost=Decimal("1234.50"),
        is_detail=True,
        is_total=False,
        is_outdated=False,
        formula_error=FormulaErrorCode.NONE,
        data_quality_status=DataQualityStatus.WARNING,
        line_id="block-7-source-dependent-id",
        warnings=warnings,
    )


def test_normalizes_every_row_without_losing_source_provenance_or_decimals() -> None:
    source = make_training_row()

    result = normalize_training_rows((source,))

    assert result.statistics.input_rows == 1
    assert result.statistics.output_rows == 1
    normalized = result.rows[0]
    assert normalized.source_row == source
    assert normalized.provenance == {
        "source_file_id": "source-a",
        "source_filename": "КС-2 № 01.xlsx",
        "source_sheet": "Лист １",
        "source_row": 17,
        "source_row_id": "source-a:17",
    }
    assert normalized.source_row.period_cost == Decimal("1234.50")
    assert normalized.warnings == ("SOURCE_WARNING",)


def test_preserves_leading_zeros_unicode_units_and_stable_tokens() -> None:
    source = make_training_row()

    normalized = normalize_training_rows((source,)).rows[0]

    assert normalized.business_key.object_code == "0007"
    assert normalized.business_key.subobject_code == "0003"
    assert normalized.business_key.position_code == "000042"
    assert normalized.work_name == "монтаж трубопровда"
    assert normalized.unit == "м"
    assert normalized.work_name_tokens == ("монтаж", "трубопровда")
    assert normalized.unit_tokens == ("м",)
    assert normalized.code_tokens == (
        "0007",
        "0003",
        "000042",
        "СМР",
        "Ч",
        "007",
        "ГЭСН",
        "01",
        "01",
    )


def test_typos_are_replaced_only_by_exact_normalized_dictionary_key() -> None:
    config = NormalizationConfig(name_typos={"монтаж трубопровда": "монтаж трубопровода"})
    exact, near_match = normalize_training_rows(
        (
            make_training_row(),
            make_training_row(
                source_file_id="source-b",
                source_row_id="source-b:18",
                work_name="Монтаж трубопроводда",
            ),
        ),
        config=config,
    ).rows

    assert exact.work_name == "монтаж трубопровода"
    assert near_match.work_name == "монтаж трубопроводда"


def test_same_business_key_has_same_line_id_across_physical_sources_and_warns() -> None:
    first = make_training_row()
    second = replace(
        first,
        source_file_id="source-b",
        source_filename="Повтор КС-2.xlsx",
        source_row=99,
        source_row_id="source-b:99",
        period_cost=Decimal("999.00"),
    )

    result = normalize_training_rows((first, second))

    assert len(result.rows) == 2
    assert result.rows[0].line_id == result.rows[1].line_id
    assert result.statistics.line_id_collisions == 1
    assert any(warning.startswith("LINE_ID_COLLISION:") for warning in result.warnings)


def test_different_business_keys_get_different_ids_and_result_is_deterministic() -> None:
    first = make_training_row()
    second = replace(
        first,
        source_file_id="source-b",
        source_row_id="source-b:18",
        object_code="0008",
    )

    forward = normalize_training_rows((first, second))
    reverse = normalize_training_rows((second, first))

    forward_rows = {row.source_row.source_row_id: asdict(row) for row in forward.rows}
    reverse_rows = {row.source_row.source_row_id: asdict(row) for row in reverse.rows}
    assert forward_rows == reverse_rows
    assert forward.rows[0].line_id != forward.rows[1].line_id

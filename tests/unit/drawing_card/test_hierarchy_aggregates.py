from __future__ import annotations

from collections.abc import Iterator, Sequence
from decimal import Decimal
from typing import Any

from report_processor.drawing_card.models import ManifestEntry, SourceSchema
from report_processor.drawing_card.sources import detect_sheet_schema, extract_rows


class RowsReader:
    def __init__(self, rows: Sequence[tuple[Any, ...]]) -> None:
        self.rows = tuple(rows)

    def list_sheets(self) -> tuple[str, ...]:
        return ("Данные",)

    def iter_rows(
        self,
        sheet_name: str,
        *,
        min_row: int = 1,
        max_row: int | None = None,
        max_col: int | None = None,
        selected_columns: Sequence[int] | None = None,
    ) -> Iterator[tuple[tuple[Any, ...], tuple[Any, ...]]]:
        del sheet_name, max_col, selected_columns
        stop = max_row or len(self.rows)
        for row in self.rows[min_row - 1 : stop]:
            yield tuple(row), tuple(row)

    def close(self) -> None:
        pass


class DualRowsReader(RowsReader):
    def __init__(
        self, formula_rows: Sequence[tuple[Any, ...]], cached_rows: Sequence[tuple[Any, ...]]
    ) -> None:
        super().__init__(formula_rows)
        self.cached_rows = tuple(cached_rows)

    def iter_rows(
        self,
        sheet_name: str,
        *,
        min_row: int = 1,
        max_row: int | None = None,
        max_col: int | None = None,
        selected_columns: Sequence[int] | None = None,
    ) -> Iterator[tuple[tuple[Any, ...], tuple[Any, ...]]]:
        del sheet_name, max_col, selected_columns
        stop = max_row or len(self.rows)
        for formula, cached in zip(
            self.rows[min_row - 1 : stop], self.cached_rows[min_row - 1 : stop], strict=True
        ):
            yield tuple(formula), tuple(cached)


def manifest_entry() -> ManifestEntry:
    return ManifestEntry(
        file_id="source",
        source_kind="file",
        container_path="source.xlsx",
        logical_path="source.xlsx",
        filename="source.xlsx",
        extension=".xlsx",
        size=1,
        compressed_size=None,
        object_index_hint=None,
        document_type="ks6a",
        period="2026-07",
        revision=None,
        is_temporary=False,
        is_copy=False,
        is_outdated=False,
        status="OK",
    )


def test_schema_uses_position_alias_and_extractor_preserves_parent_code() -> None:
    schema = SourceSchema(
        sheet_name="Данные",
        header_start_row=1,
        header_end_row=1,
        data_start_row=1,
        columns={
            "position_code": 1,
            "drawing_code": 2,
            "work_name": 3,
            "unit": 4,
            "remaining_quantity": 5,
            "remaining_total_cost": 6,
        },
        logical_headers={},
        confidence=1,
        status="OK",
    )
    rows = tuple(
        extract_rows(
            RowsReader((("6.1", "Ч-1", "Итого", "м", 2, 10),)),
            manifest_entry(),
            schema,
            object_index="object",
        )
    )

    assert len(rows) == 1
    assert rows[0].position_code_raw == "6.1"
    assert rows[0].remaining_total_cost == Decimal("10")


def test_extractor_normalizes_numeric_integer_position_from_xlsb_reader() -> None:
    schema = SourceSchema(
        sheet_name="Данные",
        header_start_row=1,
        header_end_row=1,
        data_start_row=1,
        columns={
            "position_code": 1,
            "drawing_code": 2,
            "work_name": 3,
            "unit": 4,
            "remaining_quantity": 5,
            "remaining_total_cost": 6,
        },
        logical_headers={},
        confidence=1,
        status="OK",
    )

    rows = tuple(
        extract_rows(
            RowsReader(((1.0, "Ч-1", "Итого", "м", 2, 10),)),
            manifest_entry(),
            schema,
            object_index="object",
        )
    )

    assert rows[0].position_code_raw == "1"


def test_contract_and_performed_values_use_cached_cells_and_empty_values_are_zero() -> None:
    schema = SourceSchema(
        sheet_name="Данные",
        header_start_row=1,
        header_end_row=1,
        data_start_row=1,
        columns={
            "drawing_code": 1,
            "work_name": 2,
            "unit": 3,
            "remaining_quantity": 4,
            "remaining_total_cost": 5,
            "contract_quantity": 6,
            "contract_total_cost": 7,
            "performed_quantity": 8,
            "performed_total_cost": 9,
        },
        logical_headers={},
        confidence=1,
        status="OK",
    )
    rows = tuple(
        extract_rows(
            DualRowsReader(
                (("Ч-1", "Работа", "м", 1, 2, "=10+1", "=100+1", "=5+1", "=50+1"),),
                (("Ч-1", "Работа", "м", 1, 2, 11, 101, 6, 51),),
            ),
            manifest_entry(),
            schema,
            object_index="object",
        )
    )
    empty_rows = tuple(
        extract_rows(
            DualRowsReader(
                (("Ч-2", "Пустые значения", "м", 1, 2, None, None, None, None),),
                (("Ч-2", "Пустые значения", "м", 1, 2, None, None, None, None),),
            ),
            manifest_entry(),
            schema,
            object_index="object",
        )
    )

    assert (
        rows[0].contract_quantity,
        rows[0].contract_total_cost,
        rows[0].performed_quantity,
        rows[0].performed_total_cost,
    ) == (Decimal("11"), Decimal("101"), Decimal("6"), Decimal("51"))
    assert rows[0].formula_values[-4:] == ("=10+1", "=100+1", "=5+1", "=50+1")
    assert rows[0].cached_values[-4:] == (11, 101, 6, 51)
    assert (
        empty_rows[0].contract_quantity,
        empty_rows[0].contract_total_cost,
        empty_rows[0].performed_quantity,
        empty_rows[0].performed_total_cost,
    ) == (Decimal(0), Decimal(0), Decimal(0), Decimal(0))


def test_schema_detects_exact_contract_cost_header_and_performed_block() -> None:
    header = (
        "Шифр чертежа",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества",
        "Остаток стоимости",
        "Количество",
        "Цена за единицу",
        "Стоимость по договору, руб.",
        "ВЫПОЛНЕНО ЗА ВЕСЬ ПЕРИОД СТРОИТЕЛЬСТВА Количество",
        "ВЫПОЛНЕНО ЗА ВЕСЬ ПЕРИОД СТРОИТЕЛЬСТВА Стоимость",
    )
    data = ("Ч-1", "Работа", "м", 1, 2, 3, 4, 5, 6, 7)
    padding = tuple((None,) * len(header) for _ in range(8))

    schema = detect_sheet_schema(RowsReader((header, data, *padding)), "Данные")

    assert schema.columns["contract_quantity"] == 6
    assert schema.columns["contract_total_cost"] == 8
    assert schema.columns["performed_quantity"] == 9
    assert schema.columns["performed_total_cost"] == 10


def test_schema_recovers_one_strong_content_mask_but_tied_masks_fail_closed() -> None:
    header = (
        "Нестандартный номер",
        "Шифр чертежа",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества",
        "Остаток стоимости",
        "Другой код",
    )
    detail_rows = (
        ("1", "Ч-1", "Работа", "м", 1, 10, "8"),
        ("1.1", "Ч-1", "Работа", "м", 1, 10, "8.1"),
        ("1.1.1", "Ч-1", "Работа", "м", 1, 10, "8.1.1"),
        ("2", "Ч-1", "Работа", "м", 1, 10, "9"),
    )
    padding = tuple((None,) * len(header) for _ in range(28))

    tied = detect_sheet_schema(RowsReader((header, *detail_rows, *padding)), "Данные")

    assert "position_code" not in tied.columns
    assert "AMBIGUOUS_POSITION_COLUMN_CONTENT" in tied.warnings

    strong_rows = tuple((*row[:6], None) for row in detail_rows) + padding
    strong = detect_sheet_schema(RowsReader((header, *strong_rows)), "Данные")

    assert strong.columns["position_code"] == 1
    assert "POSITION_COLUMN_FROM_CONTENT" in strong.warnings

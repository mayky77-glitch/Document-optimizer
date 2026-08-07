from __future__ import annotations

from collections.abc import Iterator, Sequence
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from report_processor.drawing_card.models import ManifestEntry
from report_processor.drawing_card.sources import detect_sheet_schema, extract_rows
from report_processor.drawing_card.sources.openxml_safety import (
    MAX_OPENXML_MEMBER_BYTES,
    validate_openxml_archive,
    validate_openxml_bytes,
)
from report_processor.drawing_card.sources.readers import OpenXmlWorkbookReader
from report_processor.drawing_card.sources.schema import select_usable_schemas


class RowsReader:
    def __init__(
        self,
        rows: Sequence[tuple[Any, ...]],
        cached_rows: Sequence[tuple[Any, ...]] | None = None,
    ) -> None:
        self.rows = tuple(rows)
        self.cached_rows = tuple(cached_rows) if cached_rows is not None else self.rows

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
        formula_rows = self.rows[min_row - 1 : max_row]
        cached_rows = self.cached_rows[min_row - 1 : max_row]
        yield from zip(formula_rows, cached_rows, strict=True)

    def close(self) -> None:
        pass


def _entry() -> ManifestEntry:
    return ManifestEntry(
        file_id="synthetic",
        source_kind="file",
        container_path="synthetic.xlsx",
        logical_path="synthetic.xlsx",
        filename="synthetic.xlsx",
        extension=".xlsx",
        size=1,
        compressed_size=None,
        object_index_hint=None,
        document_type="ks6a",
        period=None,
        revision=None,
        is_temporary=False,
        is_copy=False,
        is_outdated=False,
        status="OK",
    )


def _openxml_container(members: dict[str, bytes]) -> bytes:
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return content.getvalue()


class CentralDirectoryArchive:
    def __init__(self, *infos: ZipInfo) -> None:
        self.infos = infos

    def infolist(self) -> tuple[ZipInfo, ...]:
        return self.infos


def _member_info(*, file_size: int) -> ZipInfo:
    info = ZipInfo("xl/worksheets/sheet2.bin")
    info.file_size = file_size
    info.compress_size = file_size
    return info


@pytest.mark.parametrize(
    ("members", "error"),
    [
        ({"../escape.xml": b"safe"}, "UNSAFE_ARCHIVE_PATH"),
        ({"xl\\escape.xml": b"safe"}, "UNSAFE_ARCHIVE_PATH"),
        ({"xl/huge.xml": b"A" * (2 * 1024 * 1024)}, "SUSPICIOUS_COMPRESSION_RATIO"),
    ],
)
def test_openxml_preflight_rejects_unsafe_members_before_reads(
    members: dict[str, bytes], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        validate_openxml_bytes(_openxml_container(members))


def test_openxml_preflight_accepts_member_at_256_mib_limit() -> None:
    archive = CentralDirectoryArchive(_member_info(file_size=MAX_OPENXML_MEMBER_BYTES))

    validate_openxml_archive(archive)  # type: ignore[arg-type]


def test_openxml_preflight_rejects_member_above_256_mib_limit() -> None:
    archive = CentralDirectoryArchive(_member_info(file_size=MAX_OPENXML_MEMBER_BYTES + 1))

    with pytest.raises(ValueError, match="VERY_LARGE_ARCHIVE_ENTRY"):
        validate_openxml_archive(archive)  # type: ignore[arg-type]


def test_openxml_reader_preflights_container_before_opening_member(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.xlsx"
    path.write_bytes(_openxml_container({"../workbook.xml": b"safe"}))

    with pytest.raises(ValueError, match="UNSAFE_ARCHIVE_PATH"):
        OpenXmlWorkbookReader(path)


def test_schema_normalizes_multiline_aliases_and_derives_cumulative_contract() -> None:
    rows = (
        (
            "ШИФР\nЧЕРТЕЖА",
            "Наименование\nработ",
            "Ед. изм.",
            "Осталось выполнить",
            "Осталось выполнить",
            "Выполнено за весь период\nстроительства",
            "Выполнено за весь период\nстроительства",
        ),
        (None, None, None, "Кол-во", "Стоимость", "Количество", "Сумма, руб."),
        ("Ч-1", "Работа", "м", 3, 30, 7, 70),
        ("Ч-2", "Работа", "м", None, None, 7, 70),
    )

    schema = detect_sheet_schema(RowsReader(rows), "Данные")
    extracted = tuple(extract_rows(RowsReader(rows), _entry(), schema, object_index="0907"))

    assert schema.status == "OK"
    assert schema.columns["remaining_quantity"] == 4
    assert schema.columns["remaining_total_cost"] == 5
    assert schema.columns["performed_quantity"] == 6
    assert schema.columns["performed_total_cost"] == 7
    assert extracted[0].contract_quantity == Decimal("10")
    assert extracted[0].contract_total_cost == Decimal("100")
    assert extracted[1].remaining_quantity is None
    assert extracted[1].remaining_total_cost is None
    assert extracted[1].contract_quantity == Decimal("7")
    assert extracted[1].contract_total_cost == Decimal("70")
    assert "CONTRACT_TOTAL_COST_DERIVED_FROM_PERFORMED_AND_RESIDUAL" in extracted[0].warnings


@pytest.mark.parametrize(
    ("work_header", "unit_header", "remaining_header", "quantity_header", "cost_header"),
    [
        (
            "Наименование работ и затрат",
            "Единица\nизмерения",
            "Осталось выполнить по договору",
            "Объём",
            "Сумма, руб.",
        ),
        (
            "Вид работ",
            "Ед. изм",
            "ОСТАТОК ПО ДОГОВОРУ",
            "Кол-во",
            "Общая стоимость, руб.",
        ),
    ],
)
def test_schema_accepts_safe_header_aliases(
    work_header: str,
    unit_header: str,
    remaining_header: str,
    quantity_header: str,
    cost_header: str,
) -> None:
    rows = (
        ("Шифр рабочей документации", work_header, unit_header, remaining_header, None),
        (None, None, None, quantity_header, cost_header),
        ("Ч-1", "Монтаж", "т", 1.21, 10_512_982),
    )

    schema = detect_sheet_schema(RowsReader(rows), "Данные")

    assert schema.status == "OK"
    assert schema.columns["drawing_code"] == 1
    assert schema.columns["work_name"] == 2
    assert schema.columns["unit"] == 3
    assert schema.columns["remaining_quantity"] == 4
    assert schema.columns["remaining_total_cost"] == 5


def test_intermediate_performed_block_cannot_authorize_contract_derivation() -> None:
    rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Единица измерения",
            "Остаток",
            "Остаток",
            "Выполнено за месяц",
            "Выполнено за месяц",
        ),
        (None, None, None, "Количество", "Стоимость", "Количество", "Стоимость"),
        ("Ч-1", "Работа", "м", 3, 30, 7, 70),
    )

    schema = detect_sheet_schema(RowsReader(rows), "Данные")
    extracted = tuple(extract_rows(RowsReader(rows), _entry(), schema, object_index="0907"))

    assert "performed_total_cost" not in schema.columns
    assert extracted[0].contract_total_cost == Decimal(0)


def test_explicit_period_roles_override_generic_direct_contract_triplet() -> None:
    rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Ед. изм.",
            "Количество",
            "Цена за единицу",
            "Стоимость по договору",
            "Выполнено за весь период строительства",
            "Выполнено за весь период строительства",
            "Остаток работ по договору",
            "Остаток работ по договору",
        ),
        (
            None,
            None,
            None,
            None,
            None,
            None,
            "Количество",
            "Стоимость",
            "Количество",
            "Стоимость",
        ),
        ("Ч-1", "Работа", "м", 3, 10, 30, 6, 60, 4, 40),
    )

    schema = detect_sheet_schema(RowsReader(rows), "Данные")
    extracted = tuple(extract_rows(RowsReader(rows), _entry(), schema, object_index="0907"))

    assert schema.columns["remaining_quantity"] == 9
    assert schema.columns["remaining_total_cost"] == 10
    assert schema.columns["contract_quantity"] == 4
    assert schema.columns["contract_total_cost"] == 6
    assert "PERIOD_ROLES_AUTHORITATIVE:contract_total_cost" in schema.warnings
    assert extracted[0].contract_quantity == Decimal("10")
    assert extracted[0].contract_total_cost == Decimal("100")


def test_cost_based_residual_quantity_formula_is_repaired_from_quantity_operands() -> None:
    formula_rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Ед. изм.",
            "ДРДЦ январь",
            "Количество",
            "Стоимость по договору",
            None,
            "Выполнено за весь период строительства",
            None,
            "Остаток работ по договору",
            None,
        ),
        (
            None,
            None,
            None,
            "Количество",
            None,
            "Стоимость за единицу",
            "Общая стоимость",
            "Количество",
            "Общая стоимость",
            "Количество",
            "Общая стоимость",
        ),
        ("Ч-1", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, "=G3-H3-D3", "=G3-I3"),
    )
    cached_rows = (
        formula_rows[0],
        formula_rows[1],
        ("Ч-1", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, 1395, 1100),
    )
    reader = RowsReader(formula_rows, cached_rows)

    schema = detect_sheet_schema(reader, "Данные")
    extracted = tuple(extract_rows(reader, _entry(), schema, object_index="0907"))

    assert schema.status == "OK"
    assert schema.columns["contract_quantity"] == 5
    assert schema.columns["contract_total_cost"] == 7
    assert schema.columns["remaining_quantity_base"] == 5
    assert any(
        warning.startswith("DIMENSIONALLY_INVALID_REMAINING_QUANTITY_FORMULA")
        for warning in schema.warnings
    )
    assert extracted[0].remaining_quantity == Decimal("9")
    assert extracted[0].remaining_total_cost == Decimal("1100")
    assert extracted[0].contract_quantity == Decimal("14")
    assert extracted[0].contract_total_cost == Decimal("1400")
    assert extracted[0].performed_quantity == Decimal("3")
    assert "REMAINING_QUANTITY_REPAIRED_FROM_DIMENSIONAL_FORMULA" in extracted[0].warnings


def test_dimensional_repair_preserves_upstream_total_contract_metrics() -> None:
    formula_rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Ед. изм.",
            "Количество",
            "Цена за единицу",
            "Стоимость по договору",
            "Выполнено ранее",
            "Выполнено ранее",
            "Количество",
            "Цена за единицу",
            "Стоимость по договору",
            "Выполнено в текущем периоде",
            "Выполнено в текущем периоде",
            "Выполнено за весь период строительства",
            "Выполнено за весь период строительства",
            "Остаток работ по договору",
            "Остаток работ по договору",
        ),
        (
            None,
            None,
            None,
            None,
            None,
            "Общая стоимость",
            "Количество",
            "Стоимость",
            None,
            None,
            "Общая стоимость",
            "Количество",
            "Стоимость",
            "Количество",
            "Общая стоимость",
            "Количество",
            "Общая стоимость",
        ),
        (
            "Ч-1",
            "Монтаж",
            "т",
            14,
            100,
            1400,
            2,
            200,
            "=D3-G3",
            100,
            "=F3-H3",
            3,
            300,
            5,
            500,
            "=K3-L3",
            "=K3-M3",
        ),
    )
    cached_rows = (
        formula_rows[0],
        formula_rows[1],
        ("Ч-1", "Монтаж", "т", 14, 100, 1400, 2, 200, 12, 100, 1200, 3, 300, 5, 500, 1197, 900),
    )
    reader = RowsReader(formula_rows, cached_rows)

    schema = detect_sheet_schema(reader, "Данные")
    extracted = tuple(extract_rows(reader, _entry(), schema, object_index="0907"))

    assert schema.status == "OK"
    assert schema.columns["remaining_quantity_base"] == 9
    assert schema.columns["contract_quantity"] == 4
    assert schema.columns["contract_total_cost"] == 6
    assert "TOTAL_CONTRACT_METRICS_RESTORED_FROM_UPSTREAM_BASE:9->4;11->6" in schema.warnings
    assert extracted[0].remaining_quantity == Decimal("9")
    assert extracted[0].contract_quantity == Decimal("14")
    assert extracted[0].contract_total_cost == Decimal("1400")
    assert extracted[0].performed_quantity == Decimal("5")


def test_cost_based_residual_repair_fails_closed_for_cross_row_formula() -> None:
    formula_rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Ед. изм.",
            "ДРДЦ январь",
            "Количество",
            "Стоимость по договору",
            None,
            "Выполнено за весь период строительства",
            None,
            "Остаток работ по договору",
            None,
        ),
        (
            None,
            None,
            None,
            "Количество",
            None,
            "Стоимость за единицу",
            "Общая стоимость",
            "Количество",
            "Общая стоимость",
            "Количество",
            "Общая стоимость",
        ),
        ("Ч-1", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, "=G3-H3-D3", "=G3-I3"),
        ("Ч-2", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, "=G3-H4-D4", "=G4-I4"),
        ("Ч-3", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, "=E5-H5-D5", "=G5-I5"),
    )
    cached_rows = (
        formula_rows[0],
        formula_rows[1],
        ("Ч-1", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, 1395, 1100),
        ("Ч-2", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, 1395, 1100),
        ("Ч-3", "Монтаж", "т", 2, 14, 100, 1400, 3, 300, 9, 1100),
    )
    reader = RowsReader(formula_rows, cached_rows)

    schema = detect_sheet_schema(reader, "Данные")
    extracted = tuple(extract_rows(reader, _entry(), schema, object_index="0907"))

    assert schema.status == "OK"
    assert extracted[0].remaining_quantity == Decimal("9")
    assert extracted[1].remaining_quantity is None
    assert "DIMENSIONAL_QUANTITY_REPAIR_SIGNATURE_MISMATCH" in extracted[1].warnings
    assert extracted[2].remaining_quantity == Decimal("9")
    assert "DIMENSIONAL_QUANTITY_REPAIR_SIGNATURE_MISMATCH" not in extracted[2].warnings


def test_ambiguous_optional_contract_triplets_do_not_block_explicit_period_roles() -> None:
    rows = (
        (
            "Шифр чертежа",
            "Наименование работ",
            "Ед. изм.",
            "Количество",
            "Цена за единицу",
            "Стоимость по договору",
            "Количество",
            "Цена за единицу",
            "Стоимость по договору",
            "Выполнено за весь период строительства",
            "Выполнено за весь период строительства",
            "Остаток работ по договору",
            "Остаток работ по договору",
        ),
        (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Количество",
            "Стоимость",
            "Количество",
            "Стоимость",
        ),
        ("Ч-1", "Работа", "м", 3, 10, 30, 2, 10, 20, 6, 60, 4, 40),
    )

    schema = detect_sheet_schema(RowsReader(rows), "Данные")
    extracted = tuple(extract_rows(RowsReader(rows), _entry(), schema, object_index="0907"))

    assert schema.status == "OK"
    assert "contract_total_cost" not in schema.columns
    assert any(item.startswith("AMBIGUOUS_OPTIONAL_CONTRACT_COLUMN") for item in schema.warnings)
    assert extracted[0].contract_total_cost == Decimal("100")


def test_tied_and_conflicting_semantic_roles_fail_closed() -> None:
    tied = (
        "Шифр чертежа",
        "Шифр рабочей документации",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества",
        "Остаток стоимости",
    )
    conflict = (
        "Шифр чертежа",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества и стоимость",
    )

    tied_schema = detect_sheet_schema(RowsReader((tied,)), "Данные")
    conflict_schema = detect_sheet_schema(RowsReader((conflict,)), "Данные")

    assert tied_schema.status == "MISSING_REQUIRED_COLUMNS"
    assert "drawing_code" not in tied_schema.columns
    assert conflict_schema.status == "MISSING_REQUIRED_COLUMNS"
    assert "remaining_quantity" not in conflict_schema.columns
    assert "remaining_total_cost" not in conflict_schema.columns
    assert any(item.startswith("CONFLICTING_PHYSICAL_ROLES") for item in conflict_schema.warnings)


def test_content_only_position_evidence_remains_diagnostic_and_unusable() -> None:
    header = (
        "Нестандартный номер",
        "Шифр чертежа",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества",
        "Остаток стоимости",
    )
    data = (
        ("1", "Ч-1", "Работа", "м", 1, 10),
        ("1.1", "Ч-1", "Работа", "м", 1, 10),
        ("1.1.1", "Ч-1", "Работа", "м", 1, 10),
        ("2", "Ч-1", "Работа", "м", 1, 10),
    )

    schema = detect_sheet_schema(RowsReader((header, *data)), "Данные")

    assert schema.status == "AMBIGUOUS_SCHEMA"
    assert "position_code" not in schema.columns
    assert "POSITION_COLUMN_FROM_CONTENT_DIAGNOSTIC" in schema.warnings
    assert select_usable_schemas([schema]) == ()


def test_explicit_position_header_remains_recognized_and_usable() -> None:
    header = (
        "Номер позиции",
        "Шифр чертежа",
        "Наименование работ",
        "Ед. изм.",
        "Остаток количества",
        "Остаток стоимости",
    )
    data = (
        ("1", "Ч-1", "Работа", "м", 1, 10),
        ("1.1", "Ч-1", "Работа", "м", 1, 10),
    )

    schema = detect_sheet_schema(RowsReader((header, *data)), "Данные")

    assert schema.status == "OK"
    assert schema.columns["position_code"] == 1
    assert select_usable_schemas([schema]) == (schema,)

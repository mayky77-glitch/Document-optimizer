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
        for row in self.rows[min_row - 1 : max_row]:
            yield row, row

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

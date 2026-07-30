from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from report_processor.extraction import (
    ExtractionSerializationError,
    save_extraction_results_jsonl,
    save_rows_jsonl,
)
from report_processor.extraction.models import CanonicalSourceRow, ExtractionResult, SourceLocation
from report_processor.schema import SheetType


def _row(row_number: int, *, sheet: str = "КС-2") -> CanonicalSourceRow:
    location = SourceLocation("file-1", "book.xlsx", sheet, "ks2", row_number)
    return CanonicalSourceRow(
        row_id=f"row-{sheet}-{row_number}",
        source_type="ks2",
        source_location=location,
        document_index=None,
        document_period=None,
        object_code_raw=None,
        object_name_raw=None,
        subobject_code_raw=None,
        subobject_name_raw=None,
        position_code_raw=f"{row_number:05d}",
        work_name_raw="Работа",
        unit_raw="м",
        contract_quantity=None,
        current_period_quantity=Decimal("123.450000000000000001"),
        cumulative_quantity=None,
        remaining_quantity=None,
        unit_price=None,
        contract_cost=None,
        current_period_cost=None,
        cumulative_cost=None,
        total_cost=None,
        basis_code_raw=None,
        drawing_code_raw=None,
        cost_type_code_raw=None,
        source_values=(),
        status="OK",
        warnings=(),
    )


def test_jsonl_is_streamed_and_decimal_is_string(tmp_path: Path):
    output = tmp_path / "extracted_rows.jsonl"
    result = save_rows_jsonl((_row(index) for index in range(1, 4)), output)
    assert result.row_count == 3
    lines = output.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    payload = json.loads(lines[0])
    assert payload["current_period_quantity"] == "123.450000000000000001"
    assert payload["position_code_raw"] == "00001"
    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta["total_rows"] == 3
    assert meta["schema_version"] == "6.0"


def test_partial_output_is_removed_when_iterable_fails(tmp_path: Path):
    output = tmp_path / "rows.jsonl"

    def broken_rows():
        yield _row(1)
        raise ValueError("boom")

    with pytest.raises(ExtractionSerializationError):
        save_rows_jsonl(broken_rows(), output)
    assert not output.exists()
    assert not list(tmp_path.glob(".rows.jsonl.*.tmp"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 1, 2), "2026-01-02"),
        (datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), "2026-01-02T03:04:05+00:00"),
        (time(3, 4, 5, 123456), "03:04:05.123456"),
    ],
)
def test_jsonl_serializes_supported_temporal_values(
    tmp_path: Path,
    value: date | datetime | time,
    expected: str,
):
    output = tmp_path / "temporal.jsonl"

    save_rows_jsonl((replace(_row(1), document_period=value),), output)

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["document_period"] == expected


def test_existing_jsonl_pair_is_restored_when_second_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "rows.jsonl"
    meta_path = output.with_suffix(".meta.json")
    output.write_text('{"old":"rows"}\n', encoding="utf-8")
    meta_path.write_text('{"old":"meta"}\n', encoding="utf-8")
    original_replace = Path.replace

    def fail_meta_commit(source: Path, target: Path) -> Path:
        if source.suffix == ".tmp" and target == meta_path:
            raise OSError("metadata commit failed")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_meta_commit)

    with pytest.raises(ExtractionSerializationError, match="Не удалось завершить запись JSONL"):
        save_rows_jsonl((_row(1),), output)

    assert output.read_text(encoding="utf-8") == '{"old":"rows"}\n'
    assert meta_path.read_text(encoding="utf-8") == '{"old":"meta"}\n'
    assert not list(tmp_path.glob(".rows.jsonl.*.tmp"))
    assert not list(tmp_path.glob(".rows.jsonl.*.bak"))
    assert not list(tmp_path.glob(".rows.meta.json.*.tmp"))
    assert not list(tmp_path.glob(".rows.meta.json.*.bak"))


def test_first_jsonl_write_leaves_no_partial_pair_when_second_commit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "rows.jsonl"
    meta_path = output.with_suffix(".meta.json")
    original_replace = Path.replace

    def fail_meta_commit(source: Path, target: Path) -> Path:
        if source.suffix == ".tmp" and target == meta_path:
            raise OSError("metadata commit failed")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_meta_commit)

    with pytest.raises(ExtractionSerializationError, match="Не удалось завершить запись JSONL"):
        save_rows_jsonl((_row(1),), output)

    assert not output.exists()
    assert not meta_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.bak"))


def test_jsonl_parent_creation_error_is_wrapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    output = tmp_path / "missing" / "rows.jsonl"
    original_mkdir = Path.mkdir

    def fail_output_parent(path: Path, *args: object, **kwargs: object) -> None:
        if path == output.parent:
            raise OSError("mkdir failed")
        original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_output_parent)

    with pytest.raises(ExtractionSerializationError, match="Не удалось создать каталог"):
        save_rows_jsonl((_row(1),), output)


@pytest.mark.parametrize("existing_pair", [False, True])
def test_metadata_serialization_failure_removes_only_staged_jsonl_temp(
    tmp_path: Path,
    existing_pair: bool,
):
    output = tmp_path / "rows.jsonl"
    meta_path = output.with_suffix(".meta.json")
    if existing_pair:
        output.write_text('{"old":"rows"}\n', encoding="utf-8")
        meta_path.write_text('{"old":"meta"}\n', encoding="utf-8")

    with pytest.raises(ExtractionSerializationError, match="Ошибка потоковой записи метаданных"):
        save_rows_jsonl((_row(1),), output, metadata={"bad": object()})

    if existing_pair:
        assert output.read_text(encoding="utf-8") == '{"old":"rows"}\n'
        assert meta_path.read_text(encoding="utf-8") == '{"old":"meta"}\n'
    else:
        assert not output.exists()
        assert not meta_path.exists()
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.bak"))


def test_workbook_meta_matches_results(tmp_path: Path):
    row1 = _row(1, sheet="КС-2")
    row2 = _row(1, sheet="КС-2 логистика")
    result1 = ExtractionResult(
        "file-1",
        "book.xlsx",
        "КС-2",
        SheetType.KS2,
        (row1,),
        2,
        1,
        1,
        0,
        0,
        2,
        3,
        "empty_row_limit_reached",
        "EMPTY_ROW_LIMIT_REACHED",
        (),
    )
    result2 = ExtractionResult(
        "file-1",
        "book.xlsx",
        "КС-2 логистика",
        SheetType.KS2,
        (row2,),
        1,
        1,
        0,
        0,
        0,
        2,
        2,
        "reported_end_reached",
        "OK",
        (),
    )
    output = tmp_path / "all.jsonl"
    write = save_extraction_results_jsonl((result1, result2), output)
    meta = json.loads(write.meta_path.read_text(encoding="utf-8"))
    assert meta["total_rows"] == 2
    assert len(meta["sheet_results"]) == 2
    sheet_names = [
        json.loads(line)["source_location"]["sheet_name"]
        for line in output.read_text().splitlines()
    ]
    assert sheet_names == [
        "КС-2",
        "КС-2 логистика",
    ]

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from report_processor.cli import main
from report_processor.normalization import (
    load_normalized_rows_jsonl,
    normalize_training_rows,
    save_normalized_rows_jsonl,
)


def test_jsonl_round_trip_preserves_nested_source_decimal_and_schema_8_metadata(
    tmp_path: Path,
    make_training_row,
) -> None:
    result = normalize_training_rows((make_training_row(),))
    output = tmp_path / "normalized.jsonl"

    saved = save_normalized_rows_jsonl(result, output)

    assert saved.row_count == 1
    payload = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
    restored = load_normalized_rows_jsonl(output)
    assert payload["source_row"]["period_cost"] == "1234.50"
    assert payload["source_row"]["source_row_id"] == "source-a:17"
    assert metadata["schema_version"] == "8.0"
    assert metadata["total_rows"] == 1
    assert metadata["warnings"] == []
    assert asdict(restored[0]) == asdict(result.rows[0])
    assert restored[0].provenance["source_row_id"] == "source-a:17"


def test_normalize_rows_cli_reads_block7_jsonl_writes_schema_8_and_keeps_input_unchanged(
    tmp_path: Path,
    make_training_row,
) -> None:
    source = tmp_path / "training.jsonl"
    output = tmp_path / "normalized.jsonl"
    payload = asdict(make_training_row())
    for field, value in payload.items():
        if hasattr(value, "as_tuple"):
            payload[field] = str(value)
        elif hasattr(value, "value"):
            payload[field] = value.value
    source.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    original = source.read_bytes()

    exit_code = main(["normalize-rows", "--input", str(source), "--output", str(output)])

    assert exit_code == 0
    assert source.read_bytes() == original
    assert output.exists()
    metadata = json.loads(output.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert metadata["schema_version"] == "8.0"

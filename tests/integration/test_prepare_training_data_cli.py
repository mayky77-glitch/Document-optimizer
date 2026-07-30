import json
from pathlib import Path

from report_processor.cli import main
from report_processor.storage import DuckDBStore
from report_processor.training_data import canonical_source_row_from_dict


def _row_payload() -> dict[str, object]:
    return {
        "row_id": "row-1",
        "source_type": "ks2",
        "source_location": {
            "source_file_id": "file-1",
            "filename": "КС-2.xlsx",
            "sheet_name": "КС-2",
            "sheet_type": "ks2",
            "row_number": 10,
            "column_number": None,
            "column_letter": None,
            "coordinate": None,
        },
        "document_index": "0918 (687)",
        "document_period": "2026-06",
        "object_code_raw": "ОБ-1",
        "object_name_raw": None,
        "subobject_code_raw": None,
        "subobject_name_raw": None,
        "position_code_raw": "15",
        "work_name_raw": "Монтаж трубопровода",
        "unit_raw": "м",
        "contract_quantity": None,
        "current_period_quantity": "2.5",
        "cumulative_quantity": None,
        "remaining_quantity": None,
        "unit_price": "10",
        "contract_cost": None,
        "current_period_cost": "25",
        "cumulative_cost": None,
        "total_cost": None,
        "basis_code_raw": "ГЭСН",
        "drawing_code_raw": None,
        "cost_type_code_raw": None,
        "source_values": [],
        "status": "OK",
        "warnings": [],
    }


def _assert_training_output(output: Path) -> None:
    assert output.exists()
    assert output.with_suffix(".meta.json").exists()
    payload = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
    assert payload["work_name_normalized"] == "монтаж трубопровода"
    assert payload["period_quantity"] == "2.5"


def test_prepare_training_data_cli_from_jsonl(tmp_path: Path):
    source = tmp_path / "rows.jsonl"
    output = tmp_path / "training.jsonl"
    source.write_text(json.dumps(_row_payload(), ensure_ascii=False) + "\n", encoding="utf-8")

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    _assert_training_output(output)


def test_prepare_training_data_cli_from_primary_duckdb(tmp_path: Path):
    source = tmp_path / "rows.duckdb"
    output = tmp_path / "training.jsonl"
    with DuckDBStore(source) as store:
        store.write_rows((canonical_source_row_from_dict(_row_payload()),))

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    _assert_training_output(output)


def test_prepare_training_data_cli_controls_input_errors(tmp_path: Path, capsys):
    source = tmp_path / "rows.data"
    source.write_text("{}\n", encoding="utf-8")

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--output",
            str(tmp_path / "training.jsonl"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 9
    assert "Не удалось определить формат входа" in captured.err
    assert "Traceback" not in captured.err


def test_prepare_training_data_cli_never_overwrites_primary_duckdb(tmp_path: Path, capsys):
    source = tmp_path / "rows.duckdb"
    with DuckDBStore(source) as store:
        store.write_rows((canonical_source_row_from_dict(_row_payload()),))
    original = source.read_bytes()

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--output",
            str(source),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 9
    assert "расширение .jsonl" in captured.err
    assert source.read_bytes() == original


def test_prepare_training_data_cli_never_overwrites_input_as_metadata(tmp_path: Path, capsys):
    source = tmp_path / "training.meta.json"
    output = tmp_path / "training.jsonl"
    source.write_text(json.dumps(_row_payload(), ensure_ascii=False) + "\n", encoding="utf-8")
    original = source.read_bytes()

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--input-format",
            "jsonl",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 9
    assert "файлом метаданных" in captured.err
    assert source.read_bytes() == original
    assert not output.exists()


def test_prepare_training_data_cli_resolves_symlink_before_output_check(tmp_path: Path, capsys):
    metadata_source = tmp_path / "training.meta.json"
    input_link = tmp_path / "rows.jsonl"
    output = tmp_path / "training.jsonl"
    metadata_source.write_text(
        json.dumps(_row_payload(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    input_link.symlink_to(metadata_source)
    original = metadata_source.read_bytes()

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(input_link),
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 9
    assert "файлом метаданных" in captured.err
    assert metadata_source.read_bytes() == original
    assert input_link.is_symlink()
    assert not output.exists()


def test_prepare_training_data_cli_rejects_non_finite_decimal(tmp_path: Path, capsys):
    source = tmp_path / "rows.jsonl"
    output = tmp_path / "training.jsonl"
    payload = _row_payload()
    payload["current_period_quantity"] = "NaN"
    source.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    exit_code = main(
        [
            "prepare-training-data",
            "--input",
            str(source),
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 9
    assert "конечное decimal-значение" in captured.err
    assert not output.exists()
    assert not output.with_suffix(".meta.json").exists()

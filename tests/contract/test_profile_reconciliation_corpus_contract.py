"""Public profile CLI boundary, using no real corpus material."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from report_processor.reconciliation_patterns import offline

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "profile_reconciliation_corpus.py"


def _profile_cli_module():
    spec = importlib.util.spec_from_file_location("profile_cli_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_cli_reports_stable_missing_input_code(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(tmp_path / "absent.jsonl"),
            "--output",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 3
    assert result.stderr.startswith("INPUT_NOT_FOUND: ")
    assert str(tmp_path) not in result.stderr and "Traceback" not in result.stderr


def test_loader_rejects_json_float_before_any_profile(tmp_path: Path) -> None:
    path = tmp_path / "float.jsonl"
    path.write_text('{"record_type":"header","ratio":1.0}\n', encoding="utf-8")
    try:
        offline.load_corpus_jsonl(path)
    except offline.OfflineContractError as error:
        assert error.code in {"INPUT_INVALID_JSON", "INPUT_SCHEMA_INVALID"}
    else:
        raise AssertionError("JSON floats must be rejected")


def test_public_models_are_frozen_slotted_and_canonical_bytes_reject_nonfinite() -> None:
    assert hasattr(offline.CorpusSnapshot, "__slots__")
    assert offline.CorpusSnapshot.__dataclass_params__.frozen
    for value in (float("nan"), float("inf"), float("-inf")):
        try:
            offline.canonical_json_bytes({"synthetic": value})
        except offline.OfflineContractError:
            continue
        raise AssertionError("non-finite JSON number must be rejected")


def test_canonical_json_rejects_unhashable_values_as_controlled_contract_errors() -> None:
    class Unserializable:
        pass

    try:
        offline.canonical_json_bytes({"synthetic": Unserializable()})
    except offline.OfflineContractError as error:
        assert error.code == "INVARIANT_VIOLATION"
    else:
        raise AssertionError("unserializable values must not escape as raw errors")


def test_profile_cli_rejects_nonpositive_top_and_input_output_alias(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(missing),
            "--output",
            str(missing),
            "--top",
            "0",
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 2
    assert "--top" in result.stderr
    assert str(missing) not in result.stderr


def test_profile_cli_uses_colon_delimited_controlled_errors(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(tmp_path / "absent.jsonl"),
            "--output",
            str(tmp_path / "out.json"),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 3
    assert result.stderr == "INPUT_NOT_FOUND: input is absent\n"


def test_profile_cli_reports_internal_invariant_as_exit_five_with_colon_protocol(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    profile_cli = _profile_cli_module()
    monkeypatch.setattr(profile_cli, "load_corpus_jsonl", lambda _: object())

    def explode(_: object, *, top: int) -> object:
        raise RuntimeError("synthetic internal failure")

    monkeypatch.setattr(profile_cli, "profile_corpus", explode)
    result = profile_cli.main(
        ["--input", str(tmp_path / "input"), "--output", str(tmp_path / "output")]
    )
    assert result == 5
    assert capsys.readouterr().err == "INVARIANT_VIOLATION: internal invariant failed\n"

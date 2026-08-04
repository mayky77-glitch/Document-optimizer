"""Descriptive evaluator must remain same-corpus and non-promoting."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from report_processor.reconciliation_patterns import offline

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "evaluate_reconciliation_patterns.py"


def test_evaluation_report_is_always_descriptive_and_has_no_wave5_verdicts() -> None:
    names = {field.name for field in fields(offline.CandidateEvaluationReport)}
    assert {
        "source_corpus_fingerprint",
        "evaluations",
        "evaluation_mode",
        "promotion_eligible",
        "version",
    } <= names
    forbidden = {"precision", "forbidden_merge_count", "holdout", "equivalence", "before", "after"}
    assert not names & forbidden


def test_candidate_set_source_fingerprint_is_part_of_evaluator_boundary() -> None:
    report = offline.CandidateEvaluationReport("sha256:" + "a" * 64, ())
    assert report.evaluation_mode == "descriptive_same_corpus"
    assert report.promotion_eligible is False


def test_evaluator_exposes_the_frozen_deduplicated_metrics_and_rational_agreement() -> None:
    assert {field.name for field in fields(offline.CandidateEvaluation)} == {
        "candidate_id",
        "matched_atom_count",
        "matched_semantic_identity_count",
        "matched_document_set_count",
        "confirmed_support_atom_count",
        "confirmed_contradiction_atom_count",
        "unresolved_match_atom_count",
        "hard_boundary_mismatch_count",
        "parse_warning_atom_count",
        "agreement",
        "risk_codes",
    }


def test_evaluator_cli_has_a_stable_controlled_input_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(tmp_path / "absent.jsonl"),
            "--candidates",
            str(tmp_path / "candidates.jsonl"),
            "--output",
            str(tmp_path / "evaluation.json"),
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 3
    assert result.stderr == "INPUT_NOT_FOUND: input is absent\n"

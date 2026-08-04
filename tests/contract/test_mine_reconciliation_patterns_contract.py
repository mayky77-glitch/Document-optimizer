"""Frozen inert-candidate shape and isolation contract."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from report_processor.reconciliation_patterns import offline

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "mine_reconciliation_patterns.py"


def test_exactly_seven_candidate_kinds_are_declared() -> None:
    expected = {
        "synonym_abbreviation",
        "slot_template",
        "include_exclude",
        "split_merge",
        "critical_modifier",
        "must_link_cannot_link",
        "category_specific_normalization",
    }
    assert set(offline._KINDS) == expected
    assert {member.value for member in offline.CandidateKind} == expected


def test_frozen_candidate_models_expose_full_scope_support_and_public_payload_fields() -> None:
    assert {field.name for field in fields(offline.PatternScope)} == {
        "category",
        "mode",
        "unit_family",
        "action",
        "object_kind",
        "document_type",
    }
    assert {field.name for field in fields(offline.SupportSummary)} == {
        "support_atom_count",
        "semantic_identity_count",
        "document_set_count",
        "confirmed_record_count",
        "contradictory_atom_count",
        "support_refs",
    }
    assert {field.name for field in fields(offline.PatternCandidate)} >= {
        "record_type",
        "candidate_id",
        "kind",
        "scope",
        "proposal",
        "expected_outcome",
        "support",
        "risk_codes",
        "state",
        "descriptive_only",
        "requires_owner_review",
        "fingerprint",
    }


def test_candidate_jsonl_is_private_canonical_and_has_no_legacy_imports() -> None:
    source = Path(offline.__file__).read_text(encoding="utf-8")
    forbidden = (
        "reconciliation_grouping",
        "reconciliation_review",
        "openpyxl",
        "qdrant",
        "socket",
        "requests",
        "httpx",
    )
    assert not any(token in source for token in forbidden)
    assert Path(offline.__file__).parent.joinpath("__init__.py").read_text(encoding="utf-8") == ""
    assert offline.MAX_SUPPORT_REFS == 10


def test_miner_cli_has_a_stable_controlled_input_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(tmp_path / "absent.jsonl"),
            "--output",
            str(tmp_path / "candidates.jsonl"),
            "--min-support-atoms",
            "1",
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 3
    assert result.stderr == "INPUT_NOT_FOUND: input is absent\n"


def test_miner_cli_rejects_zero_minimum_as_usage_before_any_input_access(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(tmp_path / "absent.jsonl"),
            "--output",
            str(tmp_path / "out.json"),
            "--min-support-atoms",
            "0",
        ],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert result.returncode == 2
    assert "--min-support-atoms" in result.stderr
    assert str(tmp_path) not in result.stderr


def test_candidate_loader_rejects_extra_header_top_and_nested_fields(tmp_path: Path) -> None:
    source = tmp_path / "candidates.jsonl"
    scope = offline.PatternScope()
    proposal = offline.IncludeExcludeProposal("synthetic", "accept")
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": "include_exclude",
            "scope": scope,
            "proposal": proposal,
        }
    )
    support = offline.SupportSummary(1, 1, 1, 1, 0, ())
    candidate = offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.INCLUDE_EXCLUDE,
        scope,
        proposal,
        offline.OutcomeSignature("accept", "quantity_cost", "synthetic_category"),
        support,
        (),
        offline.fingerprint({"candidate_id": candidate_id, "support": support, "risks": []}),
    )
    payload = [
        json.loads(line)
        for line in offline.candidate_jsonl_bytes(
            offline.CandidateSet("sha256:" + "a" * 64, (candidate,))
        ).splitlines()
    ]
    for index, field in (
        (0, "extra"),
        (1, "unknown_top"),
        (1, "scope_extra"),
        (1, "proposal_extra"),
    ):
        malformed = json.loads(json.dumps(payload))
        if field == "scope_extra":
            malformed[index]["scope"]["extra"] = "x"
        elif field == "proposal_extra":
            malformed[index]["proposal"]["extra"] = "x"
        else:
            malformed[index][field] = "x"
        source.write_bytes(
            b"".join(offline.canonical_json_bytes(value) + b"\n" for value in malformed)
        )
        with pytest.raises(offline.OfflineContractError) as error:
            offline.load_candidate_jsonl(source)
        assert error.value.code == "CANDIDATE_INPUT_INVALID"

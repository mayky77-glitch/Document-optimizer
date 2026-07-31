"""Fail-closed contracts for private drawing-card machine consensus."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from report_processor.drawing_card.autopilot import consensus_fingerprint, load_machine_consensus
from report_processor.drawing_card.config import load_rules
from report_processor.drawing_card.matching.examples import ConfirmedExample
from report_processor.drawing_card.matching.matcher import DrawingRowMatcher
from report_processor.drawing_card.models import TargetWorkCategory
from report_processor.drawing_card.statuses import Status

from .test_dictionary_masks import _row

RULES = load_rules(
    Path(__file__).parents[3]
    / "src"
    / "report_processor"
    / "drawing_card"
    / "resources"
    / "rules.json"
)


def _record(
    *,
    category: str | None = "low_current_cable",
    quantity: str = "include",
    cost: str = "include",
    active: bool = True,
    rules_version: str | None = None,
) -> dict[str, object]:
    text, unit, source_type = "неоднозначная работа", "м", "visr"
    version = rules_version or RULES.version
    return {
        "schema": "MachineConsensus-1.0",
        "provenance": "codex-consensus-v1",
        "active": active,
        "confirmed": False,
        "reusable_as_human_feedback": False,
        "confirmed_by": "machine-consensus",
        "normalized_text": text,
        "unit": unit,
        "source_type": source_type,
        "rules_version": version,
        "category": category,
        "quantity_decision": quantity,
        "cost_decision": cost,
        "fingerprint": consensus_fingerprint(
            normalized_text=text,
            unit=unit,
            source_type=source_type,
            rules_version=version,
            category=category,
            quantity_decision=quantity,
            cost_decision=cost,
        ),
    }


def _matcher(
    *, consensus_path: Path, examples: tuple[ConfirmedExample, ...] = ()
) -> DrawingRowMatcher:
    return DrawingRowMatcher(
        RULES, examples, rag_mode="off", machine_consensus=load_machine_consensus(consensus_path)
    )


@pytest.mark.parametrize(
    ("category", "quantity", "cost"),
    [
        ("low_current_cable", "include", "include"),
        (None, "exclude", "exclude"),
        ("low_current_cable", "exclude", "include"),
    ],
)
def test_valid_exact_machine_consensus_is_the_only_automatic_path(
    tmp_path: Path, category: str | None, quantity: str, cost: str
) -> None:
    path = tmp_path / "machine-consensus.jsonl"
    payload = json.dumps(_record(category=category, quantity=quantity, cost=cost))
    path.write_text(payload, encoding="utf-8")

    decision = _matcher(consensus_path=path).match(_row("Неоднозначная работа"))

    assert decision.matching_strategy == "machine_consensus_exact"
    assert decision.category == (TargetWorkCategory(category) if category else None)
    assert (decision.quantity_decision, decision.cost_decision) == (quantity, cost)
    assert decision.requires_manual_review is False


@pytest.mark.parametrize("mutation", ["fingerprint", "inactive", "malformed"])
def test_tampered_or_inactive_consensus_fails_closed(tmp_path: Path, mutation: str) -> None:
    payload = _record()
    if mutation == "fingerprint":
        payload["fingerprint"] = "tampered"
    elif mutation == "inactive":
        payload["active"] = False
    else:
        payload["quantity_decision"] = "unsafe"
    path = tmp_path / "machine-consensus.jsonl"
    path.write_text(json.dumps(payload), encoding="utf-8")

    decision = _matcher(consensus_path=path).match(_row("Неоднозначная работа"))

    assert decision.requires_manual_review is True
    assert decision.matching_strategy != "machine_consensus_exact"


def test_stale_or_conflicting_consensus_fails_closed(tmp_path: Path) -> None:
    stale = _record(rules_version="obsolete")
    conflict = _record(category="power_cable")
    path = tmp_path / "machine-consensus.jsonl"
    path.write_text("\n".join(map(json.dumps, (stale, _record(), conflict))), encoding="utf-8")

    decision = _matcher(consensus_path=path).match(_row("Неоднозначная работа"))

    assert decision.requires_manual_review is True
    assert Status.CONFLICT_REQUIRES_REVIEW in decision.warnings


def test_formula_guard_and_human_feedback_precede_machine_consensus(tmp_path: Path) -> None:
    path = tmp_path / "machine-consensus.jsonl"
    path.write_text(json.dumps(_record()), encoding="utf-8")
    formula_row = replace(
        _row("Неоднозначная работа"),
        formula_values=("=A1",),
        cached_values=(None,),
        warnings=(Status.FORMULA_WITHOUT_CACHED_VALUE,),
    )
    human = ConfirmedExample(
        example_id="human-1",
        source_text="Неоднозначная работа",
        normalized_text="неоднозначная работа",
        category=TargetWorkCategory.POWER_CABLE,
        quantity_decision="exclude",
        cost_decision="include",
        unit="м",
        source_type="visr",
        confirmed_by="inline-review",
        rule_version="1",
    )

    assert _matcher(consensus_path=path).match(formula_row).requires_manual_review is True
    human_decision = _matcher(consensus_path=path, examples=(human,)).match(
        _row("Неоднозначная работа")
    )
    assert human_decision.matching_strategy == "confirmed_dictionary"
    assert human_decision.category is TargetWorkCategory.POWER_CABLE


def test_available_formula_values_do_not_mark_every_extracted_row_unresolved(
    tmp_path: Path,
) -> None:
    path = tmp_path / "machine-consensus.jsonl"
    path.write_text(json.dumps(_record()), encoding="utf-8")
    resolved_row = replace(
        _row("Неоднозначная работа"),
        formula_values=(15.0, 16.0),
        cached_values=(15.0, 16.0),
        warnings=(),
    )

    decision = _matcher(consensus_path=path).match(resolved_row)

    assert decision.matching_strategy == "machine_consensus_exact"
    assert decision.requires_manual_review is False


def test_strong_unique_unit_mismatch_is_cost_only_but_broad_cue_stays_manual(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "absent.jsonl"

    strong = _matcher(consensus_path=missing).match(_row("Стоимость м/к каркаса", unit="м"))
    broad = _matcher(consensus_path=missing).match(_row("Металлоконструкции", unit="м"))

    assert strong.matching_strategy == "deterministic_strong_rule_cost_only"
    assert (strong.quantity_decision, strong.cost_decision) == ("exclude", "include")
    assert broad.requires_manual_review is True

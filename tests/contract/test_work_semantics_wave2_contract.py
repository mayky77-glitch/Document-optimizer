# ruff: noqa: E501
from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

from report_processor.work_semantics.semantic_skeleton import build_semantic_skeleton
from report_processor.work_semantics.typed_slots import (
    TYPED_SLOTS_VERSION,
    SlotKind,
    parse_typed_slots,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_wave2_versions_direct_imports_and_legacy_boundaries_are_frozen() -> None:
    assert TYPED_SLOTS_VERSION == "TypedSlots-1.0"
    assert build_semantic_skeleton("Кабель 0,4 кВ").version == "SemanticSkeleton-1.0"

    for relative in (
        "src/report_processor/work_semantics/typed_slots.py",
        "src/report_processor/work_semantics/semantic_skeleton.py",
    ):
        tree = ast.parse((_PROJECT_ROOT / relative).read_text(encoding="utf-8"))
        imported_modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert not any("reconciliation_" in name for name in imported_modules)
        assert not any(name.startswith("report_processor.excel") for name in imported_modules)


def test_wave2_direct_import_does_not_change_legacy_identity_feedback_or_package_key(
    tmp_path: Path,
) -> None:
    script = textwrap.dedent(
        """
        import json, sys
        from dataclasses import asdict
        from decimal import Decimal
        sys.path.insert(0, sys.argv[1])
        from report_processor.reconciliation_grouping import PackageVersionContext, build_reconciliation_packages
        from report_processor.reconciliation_review.feedback import feedback_from_decision
        from report_processor.reconciliation_review.grouping import build_review_groups
        from report_processor.reconciliation_review.models import ReviewAction, ReviewDecision, ReviewMode, ReviewRow
        row = ReviewRow(row_id="legacy-row-1", display_name="Монтаж кабеля", unit="м", quantity=Decimal("1"), cost=Decimal("2"), proposed_category="Кабельные работы")
        def snapshot():
            group = build_review_groups((row,))[0]
            feedback = feedback_from_decision(group, ReviewDecision(action=ReviewAction.ACCEPT, mode=ReviewMode.QUANTITY_COST, target_category="Кабельные работы", group_id=group.group_id), sequence=4)
            packages = build_reconciliation_packages((row,), (group,), version_context=PackageVersionContext(("source-a",), "target-a", "catalog-a"))
            return {
                "group": asdict(group),
                "feedback": {
                    **asdict(feedback),
                    "action": feedback.action.value,
                    "mode": feedback.mode.value if feedback.mode else None,
                },
                "feature": {
                    **asdict(packages.features[0]),
                    "mode": packages.features[0].mode.value,
                    "unit_family": packages.features[0].unit_family.value,
                    "package_key": list(packages.features[0].package_key),
                },
                "family": asdict(packages.families[0]),
                "package": asdict(packages.packages[0]),
                "context": asdict(packages.version_context),
            }
        before = snapshot()
        import report_processor.work_semantics.typed_slots
        import report_processor.work_semantics.semantic_skeleton
        print(json.dumps([before, snapshot()], ensure_ascii=False))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(_PROJECT_ROOT / "src")],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    before, after = __import__("json").loads(completed.stdout)

    assert before == after
    assert before == {
        "group": {
            "group_id": "reconciliation-group-f60096b18117f5c17684a321",
            "version": "f60096b18117f5c17684a3214f1659048611cd78aab1d09e56a9a24593fc0c43",
            "normalized_name": "монтаж кабеля",
            "normalized_unit": "м",
            "member_ids": ["legacy-row-1"],
            "proposed_category": "Кабельные работы",
        },
        "feedback": {
            "name_key": "монтаж кабеля",
            "unit_key": "м",
            "action": "accept",
            "target_category": "Кабельные работы",
            "mode": "quantity_cost",
            "sequence": 4,
        },
        "feature": {
            "group_id": "reconciliation-group-f60096b18117f5c17684a321",
            "group_version": "f60096b18117f5c17684a3214f1659048611cd78aab1d09e56a9a24593fc0c43",
            "normalized_name": "монтаж кабеля",
            "category": "Кабельные работы",
            "mode": "quantity_cost",
            "action": "installation",
            "object_kind": "cable",
            "critical_modifiers": [],
            "negative_markers": [],
            "typed_modifiers": [],
            "unit_family": "length",
            "token_ngrams": ["абе", "ажк", "бел", "еля", "жка", "каб", "мон", "нта", "онт", "таж"],
            "feature_contract_version": "ReconciliationFeatureContract-1.0",
            "rule_version": "reconciliation-features-1",
            "package_key": ["Кабельные работы", "quantity_cost", "length", "installation", "cable"],
        },
        "family": {
            "family_id": "reconciliation-family-667cdb895dabc40ef7c1afdc",
            "version": "667cdb895dabc40ef7c1afdc5cfce862926a78b6cf87f29253b549e32b4b65eb",
            "package_key": ["Кабельные работы", "quantity_cost", "length", "installation", "cable"],
            "member_group_ids": ["reconciliation-group-f60096b18117f5c17684a321"],
            "exception_reasons": [],
        },
        "package": {
            "package_id": "reconciliation-package-8fa4616a87b3bba08154a016",
            "version": "8fa4616a87b3bba08154a01653b2ea617fa513b66f2f28e080e17fcee08d1c40",
            "package_key": ["Кабельные работы", "quantity_cost", "length", "installation", "cable"],
            "family_ids": ["reconciliation-family-667cdb895dabc40ef7c1afdc"],
            "member_group_ids": ["reconciliation-group-f60096b18117f5c17684a321"],
            "safe": True,
            "exception_reasons": [],
        },
        "context": {
            "source_digests": ["source-a"],
            "target_digest": "target-a",
            "category_catalog_version": "catalog-a",
            "feature_contract_version": "ReconciliationFeatureContract-1.0",
            "rule_version": "reconciliation-features-1",
            "model_revision": "local-model-not-used",
        },
    }


def test_public_slot_kind_set_is_exact_and_document_index_is_not_semantic() -> None:
    assert {kind.value for kind in SlotKind} == {
        "diameter",
        "pressure",
        "voltage",
        "cable_section",
        "length",
        "mass",
        "count",
        "brand",
        "material",
        "execution",
        "gost",
        "tu",
        "fire_class",
        "model",
        "article",
        "document_index",
    }
    parsed = parse_typed_slots("документ № 123; 2 шт")
    assert [slot.kind for slot in parsed.slots] == [SlotKind.DOCUMENT_INDEX, SlotKind.COUNT]

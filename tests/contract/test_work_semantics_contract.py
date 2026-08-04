from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import zipfile
from decimal import Decimal
from pathlib import Path

from report_processor.reconciliation_grouping import (
    PackageVersionContext,
    build_reconciliation_packages,
)
from report_processor.reconciliation_review.models import ReviewGroup, ReviewRow
from report_processor.work_semantics import (
    DEFAULT_ONTOLOGY,
    DOMAIN_ONTOLOGY_VERSION,
    TERM_CANONICALIZATION_VERSION,
    UNIT_ONTOLOGY_VERSION,
    canonicalize_term,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_public_versions_default_resource_and_results_are_deterministic() -> None:
    first = canonicalize_term("Монтаж КС", category="electrical", ontology=DEFAULT_ONTOLOGY)
    second = canonicalize_term("Монтаж КС", category="electrical", ontology=DEFAULT_ONTOLOGY)

    assert (
        TERM_CANONICALIZATION_VERSION,
        DOMAIN_ONTOLOGY_VERSION,
        UNIT_ONTOLOGY_VERSION,
    ) == ("TermCanonicalization-2.0", "DomainOntology-1.0", "UnitOntology-1.0")
    assert DEFAULT_ONTOLOGY.version == DOMAIN_ONTOLOGY_VERSION
    assert first == second
    assert first.semantic_text == "монтаж cable"


def test_importing_work_semantics_does_not_change_legacy_exact_group_ids() -> None:
    row = ReviewRow(
        row_id="legacy-row-1",
        display_name="Монтаж кабеля",
        unit="м",
        quantity=Decimal("1"),
        cost=Decimal("2"),
        proposed_category="Кабельные работы",
    )
    group = ReviewGroup(
        group_id="legacy-exact-group-id",
        version="legacy-group-version",
        normalized_name="Монтаж кабеля",
        normalized_unit="м",
        member_ids=(row.row_id,),
        proposed_category=row.proposed_category,
    )

    result = build_reconciliation_packages(
        (row,),
        (group,),
        version_context=PackageVersionContext(("source-a",), "target-a", "catalog-a"),
    )

    assert result.features[0].group_id == "legacy-exact-group-id"
    assert result.families[0].member_group_ids == ("legacy-exact-group-id",)
    assert result.packages[0].member_group_ids == ("legacy-exact-group-id",)


def test_built_wheel_imports_ontology_resource_from_an_isolated_install(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools.build_meta import build_wheel; "
            "import sys; print(build_wheel(sys.argv[1]))",
            str(wheel_dir),
        ],
        check=True,
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("document_optimizer-*.whl"))
    installed = tmp_path / "isolated-install"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(installed)

    imported = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; "
            f"sys.path.insert(0, {str(installed)!r}); "
            "from report_processor.work_semantics import DEFAULT_ONTOLOGY; "
            "print(DEFAULT_ONTOLOGY.version)",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert imported.stdout.strip() == DOMAIN_ONTOLOGY_VERSION


def test_legacy_generated_identity_feedback_key_and_package_tuple_are_frozen_before_import(
    tmp_path: Path,
) -> None:
    script = textwrap.dedent(
        """
        import json
        import sys
        from decimal import Decimal

        sys.path.insert(0, sys.argv[1])
        from report_processor.reconciliation_grouping import (
            PackageVersionContext,
            build_reconciliation_packages,
        )
        from report_processor.reconciliation_review.feedback import feedback_from_decision
        from report_processor.reconciliation_review.grouping import build_review_groups
        from report_processor.reconciliation_review.models import (
            ReviewAction,
            ReviewDecision,
            ReviewMode,
            ReviewRow,
        )

        row = ReviewRow(
            row_id="legacy-row-1",
            display_name="Монтаж кабеля",
            unit="м",
            quantity=Decimal("1"),
            cost=Decimal("2"),
            proposed_category="Кабельные работы",
        )

        def legacy_snapshot():
            group = build_review_groups((row,))[0]
            feedback = feedback_from_decision(
                group,
                ReviewDecision(
                    action=ReviewAction.ACCEPT,
                    mode=ReviewMode.QUANTITY_COST,
                    target_category="Кабельные работы",
                    group_id=group.group_id,
                ),
                sequence=4,
            )
            packages = build_reconciliation_packages(
                (row,),
                (group,),
                version_context=PackageVersionContext(("source-a",), "target-a", "catalog-a"),
            )
            return {
                "group_id": group.group_id,
                "group_version": group.version,
                "feedback_key": (feedback.name_key, feedback.unit_key),
                "package_key": packages.features[0].package_key,
            }

        before = legacy_snapshot()
        import report_processor.work_semantics
        after = legacy_snapshot()
        print(json.dumps({"before": before, "after": after}, ensure_ascii=False))
        """
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script, str(_PROJECT_ROOT / "src")],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    snapshots = json.loads(completed.stdout)
    expected = {
        "group_id": "reconciliation-group-f60096b18117f5c17684a321",
        "group_version": "f60096b18117f5c17684a3214f1659048611cd78aab1d09e56a9a24593fc0c43",
        "feedback_key": ["монтаж кабеля", "м"],
        "package_key": ["Кабельные работы", "quantity_cost", "length", "installation", "cable"],
    }

    assert snapshots["before"] == expected
    assert snapshots["after"] == expected
    assert len(snapshots["after"]["package_key"]) == 5

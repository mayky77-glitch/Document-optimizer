---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave7-v1
task_id: package-optimizer
role: worker
agent_role: developer
owner: wave7-optimizer
profile: L2
routing_grade: P4
routing_reason: "Bounded deterministic optimization must preserve pairwise safety and membership exactly"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
source_base_sha: f2d63d82705e10c191ab67e8a756301ebc7e1ff2
branch: codex/wave7-package-optimizer
write_scope:
  - src/report_processor/reconciliation_grouping/optimizer.py
  - tests/unit/reconciliation_grouping/test_optimizer_v2.py
forbidden_paths:
  - src/report_processor/reconciliation_grouping/__init__.py
  - src/report_processor/reconciliation_grouping/models.py
  - src/report_processor/reconciliation_grouping/features.py
  - src/report_processor/reconciliation_grouping/constraints.py
  - src/report_processor/reconciliation_grouping/packages.py
  - src/report_processor/admin_panel
depends_on:
  - constrained-clustering
tags:
  - task/implementation
  - status/done
---

# Wave 7 package optimizer

Purpose: pack already complete-linkage-safe families under an explicit maximum
size, maximizing deterministic action reduction while preserving zero
cannot-link, full pairwise compatibility, visible outliers, unique membership,
stable identifiers and deterministic ordering. Defaults that require owner
approval are not invented.

Acceptance:

```text
uv run pytest -q tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py tests/unit/reconciliation_grouping/test_optimizer_v2.py
uv run ruff check src/report_processor/reconciliation_grouping/decision_packages_v2.py src/report_processor/reconciliation_grouping/clustering.py src/report_processor/reconciliation_grouping/optimizer.py tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py tests/unit/reconciliation_grouping/test_optimizer_v2.py
uv run ruff format --check src/report_processor/reconciliation_grouping/decision_packages_v2.py src/report_processor/reconciliation_grouping/clustering.py src/report_processor/reconciliation_grouping/optimizer.py tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py tests/unit/reconciliation_grouping/test_optimizer_v2.py
git diff --check
```

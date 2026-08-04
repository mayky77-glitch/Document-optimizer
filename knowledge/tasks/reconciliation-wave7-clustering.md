---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave7-v1
task_id: constrained-clustering
role: worker
agent_role: developer
owner: wave7-clustering
profile: L2
routing_grade: P4
routing_reason: "Complete-linkage correctness, deterministic outlier isolation and adversarial pair constraints"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
source_base_sha: f2d63d82705e10c191ab67e8a756301ebc7e1ff2
branch: codex/wave7-constrained-clustering
write_scope:
  - src/report_processor/reconciliation_grouping/clustering.py
  - tests/unit/reconciliation_grouping/test_clustering_v2.py
forbidden_paths:
  - src/report_processor/reconciliation_grouping/__init__.py
  - src/report_processor/reconciliation_grouping/models.py
  - src/report_processor/reconciliation_grouping/features.py
  - src/report_processor/reconciliation_grouping/constraints.py
  - src/report_processor/reconciliation_grouping/packages.py
  - src/report_processor/admin_panel
depends_on:
  - decision-package-contract
tags:
  - task/implementation
  - status/draft
---

# Wave 7 constrained clustering

Purpose: create category-aware deterministic complete-linkage families after
hard boundary partitioning. Critical and typed modifiers split subfamilies;
unknown work stays manual; unknown unit stays exact-only/manual; an incompatible
outlier must not destroy a compatible safe remainder. Hybrid ranking can order
candidates but cannot establish safety. Union-find is forbidden.

Acceptance:

```text
uv run pytest -q tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py
uv run ruff check src/report_processor/reconciliation_grouping/decision_packages_v2.py src/report_processor/reconciliation_grouping/clustering.py tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py
uv run ruff format --check src/report_processor/reconciliation_grouping/decision_packages_v2.py src/report_processor/reconciliation_grouping/clustering.py tests/contract/test_decision_package_v2_contract.py tests/unit/reconciliation_grouping/test_clustering_v2.py
git diff --check
```

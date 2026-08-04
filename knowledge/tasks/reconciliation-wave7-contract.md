---
type: task
status: draft
card_status: frozen
version: 1
work_id: reconciliation-wave7-v1
task_id: decision-package-contract
role: worker
agent_role: developer
owner: wave7-contract
profile: L2
routing_grade: P4
routing_reason: "Privacy-safe immutable contract and consequential invariants require difficult production design"
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
source_base_sha: f2d63d82705e10c191ab67e8a756301ebc7e1ff2
branch: codex/wave7-decision-package-contract
write_scope:
  - src/report_processor/reconciliation_grouping/decision_packages_v2.py
  - tests/contract/test_decision_package_v2_contract.py
forbidden_paths:
  - src/report_processor/reconciliation_grouping/__init__.py
  - src/report_processor/reconciliation_grouping/models.py
  - src/report_processor/reconciliation_grouping/features.py
  - src/report_processor/reconciliation_grouping/constraints.py
  - src/report_processor/reconciliation_grouping/packages.py
  - src/report_processor/admin_panel
depends_on:
  - reconciliation-wave6-adapter-v1
tags:
  - task/contract
  - status/draft
---

# Wave 7 DecisionPackage-2.0 contract

Purpose: define an additive, inert, frozen and privacy-safe contract for package
atoms, hard boundaries, canonical pair constraints, candidate families,
optimizer policy, decision packages and the final result.

Required invariants: controlled/opaque values only; canonical fingerprints;
input-order independence; exact version binding; bounded collections; no float
scores; safe packages require known boundary values, compatible non-unknown
unit, complete pairwise compatibility, no cannot-link/manual blocker and an
explicit size limit. Existing runtime contract remains untouched.

Acceptance:

```text
uv run pytest -q tests/contract/test_decision_package_v2_contract.py
uv run ruff check src/report_processor/reconciliation_grouping/decision_packages_v2.py tests/contract/test_decision_package_v2_contract.py
uv run ruff format --check src/report_processor/reconciliation_grouping/decision_packages_v2.py tests/contract/test_decision_package_v2_contract.py
git diff --check
```

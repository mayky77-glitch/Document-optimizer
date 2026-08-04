---
type: task
status: done
card_status: accepted
version: 1
work_id: reconciliation-wave7-v1
task_id: p6-remediation
role: recovery
agent_role: developer
owner: wave7-remediation
profile: L3
routing_grade: P5
routing_reason: "One bounded red-first correction of three cross-contract P6 findings"
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
source_base_sha: d8d7c7d7b4a7439ccbb98df8a522067eeeebc0f3
branch: codex/wave7-p6-remediation
write_scope:
  - src/report_processor/reconciliation_grouping/decision_packages_v2.py
  - src/report_processor/reconciliation_grouping/clustering.py
  - src/report_processor/reconciliation_grouping/optimizer.py
  - tests/contract/test_decision_package_v2_contract.py
  - tests/unit/reconciliation_grouping/test_clustering_v2.py
  - tests/unit/reconciliation_grouping/test_optimizer_v2.py
depends_on:
  - package-optimizer
tags:
  - task/recovery
  - status/done
---

# Wave 7 P6 bounded remediation

One red-first pass only. Close all three independent P6 findings:

1. A must-link is compatible only with controlled, version/context/scope-bound
   authoritative attestation; an arbitrary SHA or model/dense evidence is never
   sufficient.
2. Critical and typed signature partitions remain hard across clustering,
   optimizer composition and final `DecisionPackage.safe` evaluation.
3. The real `cluster_atoms` to `optimize_packages` path must prove the optimal
   action reduction under the finite search bound; clustering must not commit a
   greedy merge that hides a better clique partition. Unselected singleton
   remainders stay visible as outliers, while a cohort with no attested pair is
   manual.

Add the auditor's counterexamples before production changes. Preserve inertness,
privacy, deterministic ordering/IDs, fail-closed search exhaustion and all
legacy/runtime files.

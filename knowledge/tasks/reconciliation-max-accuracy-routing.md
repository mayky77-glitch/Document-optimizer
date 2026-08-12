---
type: task
status: draft
card_status: frozen
card_id: reconciliation-max-accuracy-routing
version: 1
work_id: reconciliation-max-accuracy-audit-v1
task_id: routing-triage
purpose: Produce a bounded eight-launch ORDA audit decomposition for current reconciliation.
role: worker
agent_role: orchestrator
owner: routing-triage
profile: L3
routing_grade: P5
assigned_model: gpt-5.6-sol
reasoning_effort: medium
launch_status: planned
source_base_sha: 8d87a2c96ec3a26b3263cbff157755d18d07ec05
branch: main
write_scope: []
forbidden_paths:
  - src
  - tests
  - docs/DRAWING_CARD_UX_IMPROVEMENT_SPEC.md
contract_versions:
  input: ReconciliationAuditObjective-1.0
  output: ReconciliationAuditRouting-1.0
acceptance_commands:
  - git status --short --branch
tags:
  - task/review
  - status/draft
  - domain/document-processing
  - risk/high
---

# ORDA routing triage

Read-only. Use current Code Graph and active task evidence to propose no more than six
independent specialist audits plus one final P6 review. Keep three concurrent workers maximum,
eight total launches including this triage, and give each specialist an exact question,
source/test scope and expected evidence. Do not edit files or repeat workbook analysis owned by root.

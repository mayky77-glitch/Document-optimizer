---
type: task
status: frozen
card_id: drawing-card-ux-wave1-funnel-audit
version: 1
supersedes: null
work_id: drawing-card-ux-wave1-v1
task_id: funnel-audit
purpose: Add exhaustive row dispositions, controlled exclusion audit and anomalous-exclusion safety.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave1-funnel-audit.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas: []
branch: codex/drawing-card-ux-wave1-funnel-audit
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/audit/funnel.py
  - src/report_processor/drawing_card/audit/__init__.py
  - tests/unit/drawing_card/test_workflow_funnel.py
forbidden_paths:
  - src/report_processor/drawing_card/sources
  - src/report_processor/admin_panel
  - src/report_processor/hierarchy
  - knowledge
  - docs
contract_versions:
  input: DrawingCardWorkflowResult-1.0
  output: DrawingCardRowDisposition-1.0+DrawingCardFunnel-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_workflow_funnel.py tests/unit/drawing_card/test_inline_review_flow.py
  - uv run ruff check src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py src/report_processor/drawing_card/audit tests/unit/drawing_card/test_workflow_funnel.py
  - git diff --check
---

# Funnel and audit

Give every extracted row exactly one terminal disposition. The private audit record must include a
controlled reason code, rule identifier, file ID, safe basename, sheet, row number, position,
row role and hazard flags while retaining the original extracted row artifact. Counts must
conserve and include an explicit unclassified bucket.

Hierarchy aggregate/resource exclusions remain conservative. Missing/unknown role policy or an
anomalous exclusion share must be surfaced as a strict blocker, never used to hide a hazard.
Do not change schema detection, column aliases, matching category rules, admin routes or UI.


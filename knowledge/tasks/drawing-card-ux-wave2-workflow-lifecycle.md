---
type: task
status: frozen
card_id: drawing-card-ux-wave2-workflow-lifecycle
version: 1
supersedes: null
work_id: drawing-card-ux-wave2-v1
task_id: workflow-lifecycle
purpose: Add deterministic phase/progress and cooperative cancellation hooks to the drawing-card workflow.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave2-workflow-lifecycle.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas: []
branch: codex/drawing-card-ux-wave2-workflow-lifecycle
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/lifecycle.py
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/workflow.py
  - tests/unit/drawing_card/test_workflow_lifecycle.py
forbidden_paths:
  - src/report_processor/admin_panel
  - knowledge
  - docs
contract_versions:
  input: DrawingCardWorkflowRequest-current
  output: DrawingCardLifecycle-1.0+DrawingCardProgress-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_workflow_lifecycle.py tests/unit/drawing_card/test_workflow_funnel.py
  - uv run ruff check src/report_processor/drawing_card/lifecycle.py src/report_processor/drawing_card/models.py src/report_processor/drawing_card/workflow.py tests/unit/drawing_card/test_workflow_lifecycle.py
  - git diff --check
---

# Workflow lifecycle

Add optional callback/cancellation seams with defaults that preserve all existing callers. Emit
the frozen phases at honest workflow boundaries and bounded numeric counters. Cancellation must
raise a controlled workflow-specific exception before publication and remove any partial public
output. Do not add background threads, manifests, routes, UI code or change matching decisions.

---
type: task
status: frozen
card_id: drawing-card-ux-wave2-idempotency-ui
version: 1
supersedes: null
work_id: drawing-card-ux-wave2-remediation-v1
task_id: idempotency-ui
purpose: Prevent the browser from reusing an upload idempotency key after any request-defining input changes.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave2-idempotency-ui.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 4afa647de751023b4f67dce82d1e06e87ba9d978
branch: codex/drawing-card-ux-wave2-idempotency-ui
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/assets/drawing-card.js
  - tests/integration/test_drawing_card_ui_contract.py
forbidden_paths:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/drawing_card_job_store.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/drawing_card
  - knowledge
  - docs
contract_versions:
  input: DrawingCardBrowserLifecycle-1.0
  output: DrawingCardBrowserLifecycle-1.1
acceptance_commands:
  - uv run pytest -q tests/integration/test_drawing_card_ui_contract.py
  - node --check src/report_processor/admin_panel/assets/drawing-card.js
  - git diff --check
---

# Browser idempotency invalidation

Reset the stored upload idempotency key whenever operation, period, existing-card file or source
files change, and after terminal completion before a later submission. Preserve refresh recovery
for the active job and do not clear the key merely because polling or rendering occurred.

Add static UI-contract coverage for every request-defining input and terminal reset.

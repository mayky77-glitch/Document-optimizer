---
type: task
status: frozen
card_id: reconciliation-ui-clarity-v4
version: 1
purpose: Remove unsafe implicit category defaults and correct all-bad source guidance.
role: developer
owner: reconciliation-ui-clarity-developer
profile: L1
routing_grade: P3
routing_reason: Small isolated frontend correctness fix from browser evidence.
planning_parent_sha: 3c73d90880567da61372ae7a713f8d64bad8e9f4
branch: codex/reconciliation-ui-clarity-v4
write_scope:
  - src/report_processor/admin_panel/assets/admin.js
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/assets/admin.css
  - tests
acceptance_commands:
  - node --check src/report_processor/admin_panel/assets/admin.js
  - git diff --check
tags:
  - task/implementation
  - status/frozen
  - capability/admin-panel
  - layer/frontend
  - risk/low
links:
  - "[[../ORCHESTRATION|Orchestration]]"
  - "[[reconciliation-real-data-tests-v4]]"
---

# Reconciliation UI clarity

- If a group has no proposed/selected category, keep the placeholder selected.
  Never silently choose the first catalog category. Accept must remain blocked until
  the operator explicitly chooses a category; reject remains immediately available.
- For a failed all-source job, every issue card says to repair and retry even if the
  per-file issue is technically recoverable when other usable files exist. The
  continuation text is allowed only while job status is not `failed`.
- Preserve the direct two-position radio mode, one accept/reject pair, row overrides,
  responsive layout, privacy boundary and existing Russian labels.

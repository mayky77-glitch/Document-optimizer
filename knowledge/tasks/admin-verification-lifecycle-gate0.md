---
type: orchestration
status: frozen
work_id: admin-verification-lifecycle-v1
objective: Make reconciliation apply transactional and restore safe admin jobs after restart or memory pruning.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: 75a39f3616880de3bd5cb7f408b49d44b18e9fd0
published_base_sha_source: exact planning commit containing this manifest and both lifecycle cards
wave: 1
max_parallel: 1
max_spawns: 3
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-13T11:10:00+08:00
tags:
  - task/implementation
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[admin-verification-accuracy-remediation|Master task]]"
  - "[[../errors/reconciliation-accuracy-findings|RA catalog]]"
---

# Verification lifecycle Gate 0

The accepted numeric/stage integration is `75a39f3`; its full release profile is
`1724 passed, 25 skipped`. Private workbooks, generated artifacts, screenshots and the unrelated
untracked drawing-card UX specification remain outside Git.

## Dependency waves

1. [[admin-verification-apply-integrity|apply-integrity]] closes RA-006, RA-009 and RA-010 and
   establishes stable idempotent apply commits.
2. [[admin-verification-job-recovery|job-recovery]] starts only from the accepted apply integration
   SHA and closes RA-012 using the apply key and commit contract from Wave 1.

The scopes intentionally overlap in `service.py`, so the tasks are never parallel. Code Graph was
attempted before this wave and returned `Transport closed`; source and tests are the fallback.

## Shared contracts

- `ReconciliationApplyIntegrity-1.0`: exact physical identity is
  `(source SHA-256, exact sheet name, exact positive row number)`; duplicate target
  `(document index, category)` fails closed; output is fully verified before one idempotent SQLite
  feedback commit; nothing fallible follows that commit.
- `AdminReconciliationJobManifest-1.0`: atomic private job-relative JSON, no workbook values,
  formulas, locations or absolute paths; ready output is restored only after digest/path/symlink
  checks; review state is rebuilt from immutable uploads plus the existing decision snapshot.

## Acceptance

- Each card runs its exact focused pytest, Ruff, format and diff gates.
- Each accepted wave runs the reconciliation profile and full suite.
- Release requires a representative private shadow comparison and separate knowledge validation.

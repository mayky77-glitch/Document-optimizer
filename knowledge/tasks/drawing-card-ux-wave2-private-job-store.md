---
type: task
status: frozen
card_id: drawing-card-ux-wave2-private-job-store
version: 1
supersedes: null
work_id: drawing-card-ux-wave2-v1
task_id: private-job-store
purpose: Implement a bounded atomic private JSON job-manifest store with strict path validation.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave2-private-job-store.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas: []
branch: codex/drawing-card-ux-wave2-private-job-store
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/admin_panel/drawing_card_job_store.py
  - tests/unit/admin_panel/test_drawing_card_job_store.py
forbidden_paths:
  - src/report_processor/admin_panel/drawing_card_service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/drawing_card
  - knowledge
  - docs
contract_versions:
  input: DrawingCardPrivateManifest-1.0
  output: DrawingCardPrivateManifestStore-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/admin_panel/test_drawing_card_job_store.py
  - uv run ruff check src/report_processor/admin_panel/drawing_card_job_store.py tests/unit/admin_panel/test_drawing_card_job_store.py
  - git diff --check
---

# Private job store

Implement a generic store for schema-versioned JSON mappings beneath one private workspace.
Writes must use a same-directory temporary file, flush, `fsync`, `os.replace`, directory `fsync`
where supported, and mode `0600`. Loading must be bounded, require safe job identifiers, validate
every stored path as a normalized job-relative path and skip corrupt/oversized/hostile manifests.
Expose no absolute path in returned serializable data. Do not couple the module to `DrawingCardJob`
or implement lifecycle threads, HTTP behavior or product decisions.

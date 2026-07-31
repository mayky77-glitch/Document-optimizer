---
type: task
card_id: drawing-card-admin-v1-tests
status: done
version: 1
work_id: drawing-card-admin-v1
task_id: tests
purpose: "Зафиксировать core, API, review, packaging и immutability контракты"
role: worker
agent_role: tester
owner: drawing-card-tests
profile: L1
routing_grade: P3
routing_reason: "Independent contract port with multipart security, binary artifacts and real-data immutability."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
progress_revision: 1
state_fingerprint: "d2c46a65362313f8865617b952b58490a79f3466f8d65503b12196c127b155e1"
no_progress_count: 0
circuit_state: closed
luna_benchmark_evidence: ""
exception_evidence: ""
last_verified: 2026-07-31
updated: 2026-07-31
card_path: knowledge/tasks/drawing-card-admin-v1-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas:
  - b8db88e43b0bf54ac31f4b39c9413ae93d50627e
branch: codex/drawing-card-tests
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - tests/fixtures/drawing_card
  - tests/unit/drawing_card
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_real_data.py
source_paths:
  - tests/fixtures/drawing_card
  - tests/unit/drawing_card
  - tests/unit/admin_panel/test_drawing_card_service.py
  - tests/integration/test_drawing_card_admin.py
  - tests/integration/test_drawing_card_real_data.py
depends_on: []
forbidden_paths:
  - src
  - pyproject.toml
  - uv.lock
  - tests/conftest.py
  - docs
  - README.md
  - knowledge
  - .github
  - ".env*"
  - "**/*.zip"
contract_versions:
  input: DrawingCardAdminJob-1.0
  output: DrawingCardAcceptance-1.0
acceptance_commands:
  - "uv run ruff check tests/fixtures/drawing_card tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_real_data.py"
  - "uv run ruff format --check tests/fixtures/drawing_card tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_real_data.py"
  - "uv run pytest -q tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py"
tags:
  - task/testing
  - status/done
  - layer/tests
  - risk/high
---

# Drawing-card tests

Port relevant source regressions into isolated test paths and add black-box
contracts for create/update, review upload, opaque downloads, input rejection,
path non-disclosure, package resources and source/template immutability. Test
binary files through temporary copies. Never modify the files in the source
project.

Completion evidence: upload, review, result, privacy, invalid container,
package-resource and immutable real-file contracts integrated; focused
drawing-card gate `23 passed, 3 skipped`; real demo `1 passed`.

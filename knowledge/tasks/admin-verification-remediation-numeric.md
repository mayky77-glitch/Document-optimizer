---
type: orda_task
status: frozen
card_id: admin-verification-remediation-numeric
version: 1
work_id: admin-verification-remediation-v2
task_id: numeric
purpose: Make verify verdict depend on exact aggregated target J/K equality after authoritative calculation and writer quantization.
role: developer
card_path: knowledge/tasks/admin-verification-remediation-numeric.md
card_commit_sha_source: exact planning SHA supplied by launch envelope
base_sha_source: accepted Wave 1 integration SHA supplied by launch envelope
dependency_shas_source: accepted Wave 1 task feature SHAs
branch: codex/admin-verification-numeric
branch_base_sha_source: accepted Wave 1 integration SHA
write_scope:
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - tests/unit/admin_panel/test_reconciliation_verification.py
  - tests/unit/admin_panel/test_reconciliation_execution.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/admin_panel/reconciliation_sources.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - knowledge
  - docs
contract_versions:
  input: UniversalReconciliationSource-2.0+SafeGrouping-2.0+VerificationArtifact-2.0
  output: VerificationNumericOracle-2.0
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff check src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_authoritative_flow.py
  - uv run --extra dev ruff format --check src/report_processor/admin_panel/reconciliation_numeric_verification.py src/report_processor/admin_panel/reconciliation_verification.py src/report_processor/admin_panel/reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_verification.py tests/unit/admin_panel/test_reconciliation_execution.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Numeric verification oracle

Preserve explicit reject precedence. Accept/safe decisions authorize one unambiguous category and
mode only; they never bypass arithmetic. Reuse `_selected_matches`, rule loading,
`calculate_matches()` and `writer_calculations()` to aggregate contributions per physical target
row. Compare J/K exactly after shared quantization. `cost_only` checks K only. Missing/non-finite
target values, unit mismatch, category ambiguity, duplicate target binding and duplicate source
identity are controlled verification failures, never `passed`. Failed source rows receive red
locations; a pre-verdict technical ambiguity creates no misleading red artifact.

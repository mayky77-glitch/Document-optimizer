---
type: orda_task
status: accepted
card_id: reconciliation-period-shared-formulas
version: 1
work_id: reconciliation-period-shared-formulas-v1
task_id: period-shared-formulas
purpose: Preserve complete shared-formula groups only when insertion cannot affect them.
role: developer
route: P4 -> developer / gpt-5.6-terra / high; reason: exact OOXML formula topology and inverse verification.
launch_status: accepted
card_path: knowledge/tasks/reconciliation-period-shared-formulas.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: exact planning commit containing this card
branch: codex/reconciliation-period-shared-formulas
branch_base_sha_source: exact planning commit containing this card
write_scope:
  - src/report_processor/excel_writer/period_insertion.py
  - tests/unit/excel_writer/test_period_insertion.py
forbidden_paths:
  - src/report_processor/admin_panel/reconciliation_period.py
  - src/report_processor/admin_panel/reconciliation_target_measure.py
  - src/report_processor/admin_panel/reconciliation_target.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/service.py
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/presentation.py
  - src/report_processor/admin_panel/assets
  - src/report_processor/excel_writer/engine.py
  - knowledge
  - docs
contract_versions:
  input: ReconciliationPeriodInsertion-1.0
  output: ReconciliationPeriodInsertion-1.1
acceptance_commands:
  - uv run --extra dev pytest -q tests/unit/admin_panel/test_reconciliation_target_measure.py tests/unit/admin_panel/test_reconciliation_period.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff check src/report_processor/excel_writer/period_insertion.py tests/unit/excel_writer/test_period_insertion.py
  - uv run --extra dev ruff format --check src/report_processor/excel_writer/period_insertion.py tests/unit/excel_writer/test_period_insertion.py
  - git diff --check
---

# Wholly-left shared-formula preservation

Allow one shared-formula group only when its anchor and every member are present exactly once, use
one non-negative `si`, match one rectangular `ref`, and every member cell plus the full `ref` is
strictly left of the structural insertion boundary. The anchor is the only member with formula
text and `ref`; followers have neither. Every covered cell must belong to that exact group, and no
cell outside the range may reuse its `si`.

Run the existing strict formula parser on the anchor text and require the translated result to be
byte-for-byte identical to the source text. Therefore a group whose formula uses a cell/range at or
right of the boundary is affected and fails controlled preflight; no shared formula is expanded,
rebased or reconstructed. Array, data-table, dynamic, cross-sheet, external, named, structured,
whole-row/column and ambiguous formula forms remain unsupported.

The forward transform preserves every accepted `<f>` attribute/text and member relationship
unchanged. The verifier independently rebuilds the shared-group topology on source and candidate,
then requires exact equality after the ordinary whole-sheet inverse proof. Duplicate anchors,
missing followers, extra members, overlapping groups, mismatched `si/ref`, changed formula text or
any shifted member fail `PERIOD_INSERTION_DELTA_INVALID` and publish nothing.

Regressions use only generated minimal packages: valid one-cell and multi-cell left groups; multiple
independent left groups; affected formula operand, affected/ref-crossing group, missing/extra member,
duplicate anchor/`si`, follower text/ref, array/data-table and candidate topology tampering. Re-run
all existing insertion/no-clobber tests. No private workbook and no full suite in this feature task.

## Accepted evidence

- Feature: `d06bab74de77338921d801d9fc470412e7f96c39`.
- ORDA integration: `2e28152c6cb688c9949cb690174296974f9175dd`.
- Published main: `90e7a73aa156897c60fc507a420ff805e0ba4474`.
- Exact focused profile: `86 passed`; Ruff check/format and diff check passed.
- Independent P6: merge yes after uint32/blank/duplicate physical cell, permissive-forward,
  forged-plan, topology-tamper and no-clobber probes.

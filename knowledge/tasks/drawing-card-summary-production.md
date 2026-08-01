---
type: task
status: done
work_id: drawing-card-summary-v1
role: worker
agent_role: developer
owner: "summary-developer"
profile: L2
routing_grade: P4
progress_revision: 2
state_fingerprint: "summary-unit-contract-tightened-2026-08-01"
no_progress_count: 0
circuit_state: closed
routing_reason: "Multi-file XLSX implementation with financial formulas"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: "Persistent developer profile; runtime did not expose an independent launch confirmation."
model_fallback: false
last_verified: 2026-08-01
updated: 2026-08-01
write_scope:
  - "src/report_processor/drawing_card/output/summary.py"
  - "src/report_processor/drawing_card/output/writer.py"
  - "src/report_processor/drawing_card/output/layout.py"
  - "src/report_processor/drawing_card/output/contract.py"
  - "src/report_processor/drawing_card/output/validator.py"
source_paths:
  - "src/report_processor/drawing_card/output/summary.py"
  - "src/report_processor/drawing_card/output/writer.py"
  - "src/report_processor/drawing_card/output/layout.py"
  - "src/report_processor/drawing_card/output/contract.py"
  - "src/report_processor/drawing_card/output/validator.py"
depends_on:
  - "drawing-card-summary-diagnosis"
tags:
  - "task/implementation"
  - "status/done"
  - "drawing-card"
  - "xlsx"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Сводный отчет и удаление пустых блоков

## Goal

Implement the accepted formula-bearing summary and safe trailing-slot trim.

## Scope and instructions

- Modify only `write_scope` paths.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/drawing_card/output/summary.py`, `writer.py`, `validator.py`, `contract.py`.
- Commands and checks: `python3 -m compileall -q src/report_processor/drawing_card/output`; `git diff --check`; isolated `PYTHONPATH=src` smoke with 3 indices × 8 categories; private LibreOffice recalculation through `xlsx/scripts/recalc.py`.
- Result: publication creates `Сводный отчет` with 8 rows per index plus 8 `Все индексы` rows, invariant `SUMIF` formulas, `#,##0.000` money format, and automatic/full calculation flags. The smoke confirms formula retention, recalculated values, and removal of only `T:X` for 3 occupied slots. The all-index quantity formula is written only when every index has exactly one normalized non-empty unit; missing and mixed units leave that quantity blank and fail strict validation as `SUMMARY_MISSING_UNIT` or `SUMMARY_MIXED_UNIT`.
- Integration verification supplied the dev extra: Ruff passed and the full suite finished with `752 passed, 22 skipped`.
- Risks or follow-up: summary publication intentionally rejects missing or mixed all-index units with `SUMMARY_MIXED_UNIT:<category>` rather than summing incomparable quantities. Existing user-created `Сводный отчет` sheets raise a controlled error and are not overwritten.
- Nonblocking follow-up: add post-LibreOffice numeric tolerance verification on a private recalculated copy; this P2 item is intentionally outside the current production scope.

## Proposed knowledge delta

- The drawing-card output now has a formula-bearing `Сводный отчет` publication boundary; LibreOffice verification must use a private copy because the released workbook must retain formulas.

## Handoff

Accepted after the missing-unit P1 follow-up and full regression gate.

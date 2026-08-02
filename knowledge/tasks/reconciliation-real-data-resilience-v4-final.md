---
type: task
status: done
tags:
  - task/implementation
  - status/done
  - domain/document-processing
  - capability/admin-panel
  - risk/medium
last_verified: 2026-08-02
updated: 2026-08-02
---

# Reconciliation real-data resilience v4 final

## Product contract delivered

- One card is one global normalized name/unit group with every member row.
- Group accept/reject/category and direct `quantity_cost` / `cost_only` decisions
  fan out authoritatively; a row override wins for an exception.
- Explicit decisions affect the selected calculation rows and verified XLSX, then
  persist as reusable private feedback. An all-reject review publishes a verified
  byte-identical target copy.
- Each source is parsed independently. A broken source does not suppress usable
  groups; its safe basename and one Russian repair hint are shown. A missing usable
  four-digit index is rejected before review.
- Public row IDs are opaque. Payloads do not expose paths, sheets, formulas,
  coordinates, provenance/evidence, raw warnings or source digests.

## Root cause and repair

A KS-2 detail row could extend the header boundary because header discovery used the
last non-empty value in the work/unit columns. The adapter now derives the boundary
only from explicit header tokens and keeps the strict quantity + total-cost pair.
The affected workbook itself requires no edit.

Final hardening also makes ready-result apply idempotent, rejects categories that do
not exist for a row's source index, ignores incompatible historical feedback, and
removes a partially linked unchanged result if final XLSX verification fails.

## Focused evidence

- Real private smoke: 12 usable sources, 0 source issues, 2,953 rows, 500 global
  groups, 15 target categories, 359 proposed rows; every input digest unchanged.
- Authoritative real write: one accepted non-zero row produced quantity `188.00`
  and cost `64.59` million RUB; the output reopened successfully.
- Focused tests: 29 unit passes; 10 integration passes and 1 opt-in skip when real
  environment variables are absent. Reviewer-remediation subset: 17 passes and 1
  opt-in skip.
- Ruff, Ruff format, Node syntax and `git diff --check` pass. Desktop/mobile,
  light/dark browser smoke has no console error or horizontal overflow at 390 px.

## Links

- [[reconciliation-real-data-source-core-v4]]
- [[reconciliation-real-data-lifecycle-ui-v4]]
- [[reconciliation-real-data-remediation-v4]]
- [[reconciliation-real-data-tests-v4]]
- [[reconciliation-ui-clarity-v4]]
- [[reconciliation-mobile-overflow-v4]]

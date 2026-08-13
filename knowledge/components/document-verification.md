---
type: component
tags:
  - knowledge/component
  - domain/document-processing
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-13
updated: 2026-08-13
source_paths:
  - src/report_processor/admin_panel/assets/index.html
  - src/report_processor/admin_panel/assets/admin.js
  - src/report_processor/admin_panel/app.py
  - src/report_processor/admin_panel/reconciliation_verification.py
  - src/report_processor/admin_panel/reconciliation_numeric_verification.py
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/excel_writer/row_annotations.py
---

# Проверка документов

## Actual production path

The `/` form submits `operation=verify`. The server discovers one valid target stage or asks the
user to select among bounded safe options. It extracts source rows, restores exact decisions,
authorizes safe/explicit matches and then runs the same Decimal calculation and writer
quantization as reconciliation. A clean result is possible only when the numeric oracle matches
the authoritative target pair.

Ordinary numeric mismatch fails every contributing physical source row. One failed source returns
an annotated copy; multiple sources return a no-clobber ZIP. Technical source, target, unit,
identity, formula-cache or publication failures never become `passed` and do not manufacture a red
artifact.

## Enforced invariants

- Uploaded originals and target remain private, read-only and digest-bound.
- Zero quantity plus zero cost is neutral and excluded from checked/failed counts.
- Explicit rejection overrides safe authorization; row decisions override broader scopes.
- Numeric comparison uses finite `Decimal`, exact canonical units without conversion, million-RUB
  scaling and the same two-decimal `ROUND_HALF_UP` writer boundary.
- Formula targets are eligible only with a trusted cache and `OK` status.
- Public payloads omit sheets, rows, values, formulas, private paths and workbook-derived labels.
- Red annotation preserves formulas/values and supports adjacent self-closing/paired style records;
  multi-source publication uses unique owned temporary paths.
- Ready/review/pass-without-artifact jobs recover safely after restart or bounded memory pruning.

## Active accuracy limit

The numeric oracle currently receives a positionally bound J/K pair. Direct comparison of the
clean target with the desired reference proves that pair is not the current reporting period for
the designated template: J/K remain unchanged and a new pair is inserted later. Until
[[../DECISIONS#DO-019: числовая пара цели определяется структурой, а не адресом (2026-08-13)|DO-019]]
is implemented, verification must not claim 100% accuracy on that layout. The required safe result
for a clean target without a structural current-period pair is
`TARGET_CURRENT_PERIOD_PAIR_MISSING`, not pass/red. Track implementation in
[[../tasks/reconciliation-real-layout-gate0|Real-layout Gate 0]].

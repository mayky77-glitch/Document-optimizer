---
type: component
tags:
  - knowledge/component
  - domain/document-processing
  - layer/backend
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-13
updated: 2026-08-13
source_paths:
  - src/report_processor/admin_panel/reconciliation_*
  - src/report_processor/reconciliation_review
  - src/report_processor/reconciliation_grouping
  - src/report_processor/matching
  - src/report_processor/calculation
  - src/report_processor/excel_writer
  - tests
---

# Сверка документов

## Adjacent authoritative reconciliation path

`operation=reconcile` reads each uploaded source independently, reads the target once, normalizes
source rows, builds deterministic global review groups/packages, applies explicit decisions,
recalculates authoritative matches and writes or copies one verified target workbook. It is not
the public `/` button: that surface runs [[document-verification|Проверка документов]] and annotates
source rows instead of writing target J/K.

## Fixed invariants

- A source needs one usable four-digit document index; unusable sources do not suppress usable siblings.
- Rows with finite zero quantity and zero cost stay internal and never create review or feedback.
- Row decisions override broader decisions. Local semantic hints never change membership,
  calculation or XLSX output.
- Arithmetic uses finite `Decimal` values. Only accepted `quantity_cost` or `cost_only`
  selections reach calculation.
- No selected calculations means byte-identical target publication; otherwise the writer must
  return a verified output digest.
- Private source names, paths, sheets, formulas and cell coordinates remain outside public API
  payloads and durable knowledge.

## Audit result

[[../tasks/reconciliation-max-accuracy-audit-v1|Maximum-accuracy audit]] verifies these
invariants against current code, adversarial tests and direct workbook comparison.

The audit found a real wrong-output path plus deterministic exact-once, transaction, format and
publication gaps. See [[../errors/reconciliation-accuracy-findings|accuracy findings]]. Until the
high-severity boundaries are remediated, neither reconcile nor verify supports a 100% accuracy
claim.

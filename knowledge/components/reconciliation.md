---
type: component
tags:
  - knowledge/component
  - domain/document-processing
  - layer/backend
  - capability/admin-panel
  - risk/high
last_verified: 2026-08-12
updated: 2026-08-12
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

## Production path

The `/` workflow reads each uploaded source independently, reads the target once,
normalizes source rows, builds deterministic global review groups/packages, applies explicit
row/group/package decisions, recalculates authoritative matches and writes or copies one
verified result workbook. Source and target workbooks are read-only inputs.

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

## Active audit

[[../tasks/reconciliation-max-accuracy-audit-v1|Maximum-accuracy audit]] verifies these
invariants against current code, adversarial tests and direct workbook comparison.

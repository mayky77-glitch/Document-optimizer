---
type: task
status: done
tags:
  - status/done
  - capability/reconciliation
  - domain/document-processing
last_verified: 2026-08-04
updated: 2026-08-04
---

# Excel-PDF reconciliation Wave 10 final handoff

Wave branch: `codex/excel-pdf-reconciliation-wave10`. Accepted code integration:
`3a37ece3d96ea183e078bdba7dd365b853881048`. Merge into `main` is intentionally
deferred until the remaining waves are complete.

## Delivered

- `report-processor reconcile-package --package <dir> --output <json>`;
- dynamic, read-only extraction of comparable KS-2 workbook rows;
- exact work-code package scoping and bounded local Poppler/Tesseract OCR;
- content-backed project/work matching and metre/kilometre quantity comparison;
- fail-closed `MATCH`, `MISMATCH`, `AMBIGUOUS`, `NO_EVIDENCE`, `NEEDS_REVIEW`;
- deterministic relative candidate context for unsupported documents;
- atomic private JSON (`0600`) without raw OCR, formulas or absolute paths.

## Evidence

- focused package suite: `43 passed`; Ruff, format and diff checks clean;
- full suite: `1413 passed`, `25 skipped`, with the same two unrelated existing
  failures in the Block 12 strategy contract and hierarchy presentation;
- independent final review: no HIGH or MEDIUM findings;
- two designated small pilots were used before remediation; the first confirmed
  one quantity mismatch and the second confirmed two matches;
- remediation used synthetic fixtures only and opened no additional package;
- all remaining private packages are reserved for later holdout.

No workbook, PDF, raw OCR, private absolute path or pilot-derived synthetic value
is present in the final tracked tree. Production/main activation remains stopped
until the user-directed all-waves merge.

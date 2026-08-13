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
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/excel_writer/row_annotations.py
---

# Проверка документов

## Actual production path

The `/` form submits `operation=verify`. It reads source workbooks and the target through the
shared reconciliation adapter, partitions zero-activity rows, builds match/group/package state and
then classifies each visible source row:

1. latest explicit ACCEPT passes and REJECT fails;
2. otherwise membership in a `DecisionPackage.safe` passes;
3. every other row fails and its physical source row is selected for red annotation.

One failed source returns an annotated copy; multiple sources return a ZIP with every original
basename once. Target J/K is never written by this operation. Numeric source values are not
compared with target values; they only affect visibility and grouping mode.

## Current invariants and limits

- Uploaded originals and target are private read-only copies and must retain their digests.
- Zero quantity plus zero cost is neutral and excluded from checked/failed counts.
- RAG/semantic hints cannot change pass/fail.
- Technical source/target failures must never become a clean `passed` result.
- Public payloads omit sheets, rows, values, formulas and private paths.
- The UI currently supplies no stage; the server silently uses `13.1`.
- A clean result has no artifact; a failed result requires a safe red-row artifact.

The current implementation cannot support a 100% accuracy claim. It has no numeric oracle, can
select the wrong source layout, accepts an empty target-stage catalog, and fails red annotation on
the representative real corpus. See
[[../errors/reconciliation-accuracy-findings|RA-001, RA-014, RA-015 and RA-017]].

## Tests and evidence

Synthetic verification tests cover decision precedence, technical failure projection, file type
and basic annotation/ZIP behavior. They do not cover numeric mismatch, alternate cumulative
headers, formula-without-cache rows, empty/ambiguous stages, duplicate source SHA or the real
mixed self-closing/paired style table. The 2026-08-13 audit compared current and independently
bound cumulative interpretations on immutable private copies and kept only de-identified counts.

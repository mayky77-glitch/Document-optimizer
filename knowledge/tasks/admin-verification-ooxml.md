---
type: task
status: ready
tags: [status/ready, capability/reconciliation, domain/excel]
assigned_profile: L2
assigned_grade: P4
---

# Verification OOXML row annotations

Base: `41943ec9141f6b6cdf5ddbd978c239c35423f313`.

Own only `src/report_processor/admin_panel/reconciliation_sources.py`, a new
`src/report_processor/excel_writer/row_annotations.py`, its package export if
required, and focused unit/contract tests. Preserve real source sheet provenance.
Provide a package-preserving function with the agreed interface:
`annotate_failed_rows(source_path, output_path, failed_rows)` where failed rows map
sheet names to positive physical row numbers. Copy OOXML atomically, add red style
variants only to existing cells on failed rows, keep other package parts and VBA
bytes unchanged, reject signed/unsafe packages, and never mutate the source.

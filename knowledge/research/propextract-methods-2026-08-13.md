---
type: research
status: current
tags:
  - knowledge/research
  - domain/document-processing
  - capability/admin-panel
last_verified: 2026-08-13
updated: 2026-08-13
source_url: https://github.com/mayky77-glitch/PropExtract
source_commit: 25918b54333e7ebf871f48fb3ec554d465287c57
---

# PropExtract methods applicable to verification

Read-only comparative audit of public repository
[PropExtract](https://github.com/mayky77-glitch/PropExtract/tree/25918b54333e7ebf871f48fb3ec554d465287c57).
The source domain is PDF permits → Excel registry, not KS-2/KS-6a reconciliation. Reuse only
general analysis/test methods and reimplement them independently.

## Applicable methods

| Method | Public evidence | Use in Document Optimizer |
| --- | --- | --- |
| Exact identity or ambiguity | Bounded labeled identity wins; multiple identities return no identity in [`rns_adapter.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/rns_adapter.py#L189-L224) | Apply to document index, target stage and layout candidates: never choose by filename/order after contradictory structural evidence |
| Field-level provenance | Extracted fields retain source kind and winning source in [`rns_adapter.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/rns_adapter.py#L304-L340) and [`app.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/app.py#L175-L235) | Keep private per-metric evidence: workbook digest, layout candidate, anchor, formula/cache status and target binding; expose only safe reason codes |
| Order-independent consensus | Newer valid dates use deterministic ordering; conflicting non-date values are quarantined in [`app.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/app.py#L78-L142) | Add permutation tests for source order, candidate order and duplicate/contradictory headers; ambiguity becomes review/input error, never first-success selection |
| Narrow comparison normalization | Only defined presentation differences are ignored; semantic words remain significant in [`normalization.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/normalization.py#L30-L70) | Define exact header/unit aliases and numeric tolerances explicitly; do not use fuzzy text as an automatic correctness oracle |
| Workbook delta allowlist | Staged output is reopened; formulas, styles, links and native formatting are compared outside intended cells in [`workbook.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/workbook.py#L244-L347) | Verification artifact acceptance should compare source/output OOXML parts, cell values/formulas and red-row set before publish |
| Stale input and real no-op | Source hash is rechecked before publish; already-equal runs preserve digest/mtime and create no backup in [`server.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/rns_import_server/server.py#L336-L384) | Preserve source/target digests, bind manual decisions to input versions and do not create artifacts for a genuinely clean verification |
| Adversarial regression shapes | Identity ambiguity, source-order permutations, conflict quarantine and cleanup/timeouts are explicit tests in [`test_identity_regressions.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/tests/test_identity_regressions.py#L22-L123), [`test_merge_regressions.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/tests/test_merge_regressions.py#L171-L211) and [`test_ocr_resource_limits.py`](https://github.com/mayky77-glitch/PropExtract/blob/25918b54333e7ebf871f48fb3ec554d465287c57/tests/test_ocr_resource_limits.py#L153-L197) | Add equivalent Excel-layout, index, stage, duplicate-SHA, formula-cache, package-unit and cleanup ownership regressions |

## Not transferable without a new requirement

- OCR/text-layer/geometry extraction is not part of current Excel-only `operation=verify`.
- RNS identity regexes, form labels, date precedence and object-preamble exception are domain-specific.
- PropExtract's local LLM mapping seam is dormant and fail-closed; it is not evidence for adding
  RAG or automatic financial confirmation here.

## License boundary

At the audited commit, the repository has no top-level LICENSE/COPYING file; GitHub metadata
reports no detected license. The included OCR model license covers those model files only. Treat
the application source as unlicensed/all-rights-reserved: do not copy code, tests or fixtures.
Only high-level methods may inform a clean independent design after owner/legal approval.

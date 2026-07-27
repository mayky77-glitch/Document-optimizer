---
type: component
tags: [knowledge/component, domain/document-reconciliation, status/accepted, risk/high]
last_verified: 2026-07-28
source_paths: ["docs/PRD.md", "docs/BUSINESS_RULES.md", "docs/ARCHITECTURE.md", "docs/ROADMAP.md"]
---
# Document reconciliation

Four linked planning documents define product, domain contract, architecture and critical roadmap.

## Canonical facts

- Table 1 is source KS-2/KS-3/KS-6a; Table 2 is `Расчет доп отчета карточка 23 Хандюк.xlsx`, `Лист1`.
- Table 2 `Лист1` is 180×17; 1006 block rows 139–144. Table 1 period fields are semantic: observed 1006 CF/CG, 1004 BL/BM, 0919 CJ/CK; KITSO differs.
- Stage 13.1 has 15 indices, 12 with candidates, missing 1005/0768/0778. Selection uses suffix-after-last-dot, Unicode token boundaries, `6а` Cyrillic/Latin/case and explicit missing/multiple review; semantic workbook content, not filename, proves stage.
- [BUSINESS_RULES](../../docs/BUSINESS_RULES.md) v1 is the canonical contract for M01–M14, Decimal raw-RUB aggregation, red/yellow statuses, feedback memory and Gate 0.

## Gate 0 / risks

- Implementation is blocked until owner decides M04/M05 exact include sets, M13/M14, suffix/supporting-work semantics, stage/month/period/quantity, coefficient 2.7, J/L tolerance, units, versions, formula freshness, feedback reuse/retention and AI context/token budget. M02/M06 literals are fixed.
- Feedback is versioned scoped memory, never online training: canonical SQLite IDs/FKs/hashes, deduplicated raw strings, active snapshot separate from immutable audit; deterministic SQL precedes any bounded GPT projection.
- Model gateway supports disabled, local CLI and manual strict-JSON GPT-application modes without requiring an API. MVP imports XLSX/folder/ZIP; XLSB is an explicit post-MVP adapter. Implementation orchestration has a pre-P1 xhigh-profile setup/restart gate.

## Links
- [PRD](../../docs/PRD.md) · [Rules](../../docs/BUSINESS_RULES.md) · [Architecture](../../docs/ARCHITECTURE.md) · [Roadmap](../../docs/ROADMAP.md) · [[../DECISIONS|Decisions]] · [[../tasks/remediate-plan-documents|Remediation task]]

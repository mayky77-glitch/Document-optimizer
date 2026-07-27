# ROADMAP — executable plan for orchestrator

Mode: **critical**. Gate 0 product decisions are recorded; current work is still planning only, and implementation starts only on a separate owner instruction. Для реализации пользователь явно запросил orchestration reasoning `xhigh`: перед стартом P1 отдельный setup gate проверяет/создаёт совместимый project orchestrator profile и перезапускает Codex/открывает новую задачу; текущий закреплённый `orchestrator` medium не объявляется xhigh и не подменяется вручную.

## Gate 0 — owner decision record

Complete: adaptive schema/mapping/run token budgets, storage/retrieval thresholds, exact feedback memory, M02/M06 literals and two bounded runtime AI workers are approved. This gate records product decisions but does not authorize implementation.

## DAG

`G0 → P1 corpus/preflight → P2 selector → P3 rules+Decimal → P4 feedback memory → P5 review → P6 export → P7 E2E/release audit`; P5 depends on P2/P3/P4, P6 on P3/P5, P7 on all prior packages. CodeGraph gate occurs immediately after the first scaffold in P1, never before it.

## Work packages

| Package / dependency | Owner route | Exclusive write scope | Deliverable and non-goals | Entry → exit / acceptance and tests |
| --- | --- | --- | --- | --- |
| P0 decision corpus / none | documentation-agent P1; tester P3 | documentation-agent: `knowledge/DECISIONS.md`, `docs/decision-record.md`; tester: `tests/fixtures/decision-corpus/` | Owner-approved decision record and fixture inventory. Orchestrator/explorer are read-only, own no write scope; no code. | Gate 0 record available → signed implementation handoff, fixture hashes and decision completeness check. |
| P1 model + preflight / P0 | developer P3; tester P3 | developer: `src/domain/`, `src/schema/`; tester: `tests/domain/`, `tests/schema/` | Semantic Table 1/2 model, KS-6a and whole-period-block preflight. No selector/UI/export. | CodeGraph init after first scaffold → Cyrillic/Latin/case sheet names, spelling/header variants, KS-2/KS-3/month exclusion, zero/multiple ambiguity, variable-header/merged/schema/lineage tests pass. |
| P2 selector / P1 | developer P3; tester P3 | developer: `src/files/`; tester: `tests/files/` | Unicode selector, semantic stage/month and explicit revision ranking. No mtime/first-file auto-choice. | Leading-zero/boundary/`6а` variants, `~$`, misleading filename, stage/month, `редN`/no-revision, misleading mtime, schema-quality tie and user-confirmation tests pass. |
| P3 baseline rules + calculation / P1,P2 | developer P4; tester P3 | developer: `src/rules/`, `src/calc/`; tester: `tests/rules/`, `tests/calc/` | M01–M14 registry, KGS power/low-current classifier, prefix matcher, ownership and Decimal core. | Explicit `слаботочн`/ВОЛС→M05, otherwise M04, cross-scope priority, wiring/support/auxiliary review-only, prefix/ownership/calculation tests pass. |
| P4 feedback memory / P3 | developer P4; tester P3; database-engineer P4 read-only consult | developer: `src/feedback/`, `src/storage/`; tester: `tests/feedback/`; database-engineer: no write scope | Exact feedback rules, indefinite active snapshot, append-only versions, compact on/off/restore UI projection. No physical delete, auto-match memory or generalization. | Post-export activation, indefinite reuse, opposite version, on/off/restore, cancelled run, drift, dedup/storage/latency and compaction-equivalence tests pass. |
| P5 review surfaces / P2,P3,P4 | developer P3; tester P3; designer P4 read-only spec | developer: `src/review/`, `src/cli/`, `src/site/api/`, `src/site/state/`, `src/site/components/`, `src/site/styles/`, `src/model_gateway/`; tester: `tests/review/`, `tests/model_gateway/`; designer: no write scope | Exactly two uploads, CLI args, month/stage UI, compact new-schema confirmation gate, one-table candidate checkboxes/comments/live totals, direct unit-group selection and model modes disabled/CLI/manual-app/optional-API. Implement deterministic `AiTaskRouter` plus only two stateless runtime workers: `schema_advisor` and `mapping_advisor`; no AI worker may calculate, select files, activate memory or export. Designer supplies read-only visual spec because templating/site code belongs to developer; no shared ownership. | Candidate API stable → matching/single-alternative/multiple-unit subtotals, no cross-unit sum, all-checked-row cost, `0/0` no-match, checkbox/comment/live-recalculation, uploads, month/stage, mandatory confirm/correct before schema cache, strict worker I/O, tokenizer/byte-bound packet split, allowlisted CLI/manual bridge, no auto-retry, cache/budgets/manual fallback and export-block tests pass. |
| P6 export + verify / P3,P5 | developer P4; tester P3 | developer: `src/export/`, `src/verify/`; tester: `tests/export/` | Dual-view cached-value validation/flattening, month pair, one standalone Table-2 XLSX, atomic save/reopen/internal manifest. No source overwrite, copied formula or external link. | Missing-cache evidence/re-save/re-upload tests; no blank/zero/LibreOffice fallback; `formula_count=0`, `external_link_count=0`, one-file delivery, value/style/hash/internal-manifest tests pass. |
| P7 hardening/release / P1–P6 | tester P3; documentation-agent P1; devops P3; reviewer/security-reviewer P6 read-only | tester: `tests/e2e/`; documentation-agent: `docs/release/`; devops: `pyproject.toml`, `.github/workflows/`; reviewer/security-reviewer: no write scope | E2E corpus, release docs and packaging/CI evidence. No feature expansion. | All packages exit → E2E/manual/GPT-rejection/security audit pass; release gate. |

Before each package the orchestrator creates cards that split listed source and test scopes into non-overlapping exact paths; developer and tester never write the same path. P6 reviewer does one final read-only audit after the standard/critical work group.

## Cross-package acceptance corpus

1006 goldens above; schema fixtures 1004/0919/KITSO; upload/stage/month, misleading filenames, candidate sets, M04/M05, ambiguity, units, missing cached formula values, formula flattening, zero external links, duplicate rows, M13/M14, feedback and order independence. GPT tests prove strict rejection, statelessness, role isolation, no authority, no repeated identical prompt and full manual fallback.

## Post-MVP adapters

После P7 и только по подтверждённой потребности отдельный package добавляет XLSB reader за тем же normalized-row контрактом. Entry: corpus unsupported XLSB + accepted-library/security decision. Exit: parity fixtures against trusted Excel values, no formula execution, same lineage/Decimal/export gates. RAR, cloud, auth и multi-user остаются вне scope до отдельного PRD.

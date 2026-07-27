# ROADMAP — executable plan for orchestrator

Mode: **critical**. No package that writes scaffold/implementation may enter before all Gate 0 decisions are owner-approved and recorded. Current work is planning only. Для реализации пользователь явно запросил orchestration reasoning `xhigh`: перед стартом P1 отдельный setup gate проверяет/создаёт совместимый project orchestrator profile и перезапускает Codex/открывает новую задачу; текущий закреплённый `orchestrator` medium не объявляется xhigh и не подменяется вручную.

## Gate 0 — owner decision record

Owner must approve: Table 1 sheet/whole-period semantics; M04 exact power include set and supporting works; M05 exact low-current include set; M13/M14 precedence; M03/M07/M08/M12 suffix semantics; stage/version selection; month/current-period validation; automatic unit conversion; missing cached formula-value recovery; feedback reuse compatibility, retention, deactivate/rollback and user authority; AI context/token budget and storage/retrieval thresholds. Standalone value-only one-XLSX output, formula flattening, zero external links, month-pair/rounding/J-L/coefficient/unit/review rules are fixed. M02/M06 literals are already fixed.

## DAG

`G0 → P1 corpus/preflight → P2 selector → P3 rules+Decimal → P4 feedback memory → P5 review → P6 export → P7 E2E/release audit`; P5 depends on P2/P3/P4, P6 on P3/P5, P7 on all prior packages. CodeGraph gate occurs immediately after the first scaffold in P1, never before it.

## Work packages

| Package / dependency | Owner route | Exclusive write scope | Deliverable and non-goals | Entry → exit / acceptance and tests |
| --- | --- | --- | --- | --- |
| P0 decision corpus / none | documentation-agent P1; tester P3 | documentation-agent: `knowledge/DECISIONS.md`, `docs/decision-record.md`; tester: `tests/fixtures/decision-corpus/` | Owner-approved decision record and fixture inventory. Orchestrator/explorer are read-only, own no write scope; no code. | Gate 0 open → signed record, fixture hashes and decision completeness check. |
| P1 model + preflight / P0 | developer P3; tester P3 | developer: `src/domain/`, `src/schema/`; tester: `tests/domain/`, `tests/schema/` | Semantic Table 1/2 model and preflight. No selector/UI/export. | CodeGraph init after first scaffold → variable-header/merged/schema-drift/lineage tests pass. |
| P2 selector / P1 | developer P3; tester P3 | developer: `src/files/`; tester: `tests/files/` | Unicode selector plus semantic content-stage validation. No implicit version default. | Stage/month contract approved → leading-zero/boundary/`6а`/`6a`/case/`~$`/misleading filename/conflicting content/zero/multiple tests pass. |
| P3 baseline rules + calculation / P1,P2 | developer P4; tester P3 | developer: `src/rules/`, `src/calc/`; tester: `tests/rules/`, `tests/calc/` | M01–M14 registry, candidates, Decimal/lineage. No feedback/UI/export. | M04/M05 include sets approved → positive/cross-category/exclusion, includes/excludes/suffix/M13-M14/Decimal/order/golden/unit/J-L tests pass. |
| P4 feedback memory / P3 | developer P4; tester P3; database-engineer P4 read-only consult | developer: `src/feedback/`, `src/storage/`; tester: `tests/feedback/`; database-engineer: no write scope | Compact canonical SQLite entities, IDs/FKs/hashes, deduplicated raw strings, active snapshot + append-only audit. No online learning/category generalization/audit deletion. | Reuse policy approved → reuse/isolation/conflict/rollback/drift/duplicate, no-duplicate-string, storage-growth, retrieval-latency and compaction-equivalence tests pass. |
| P5 review surfaces / P2,P3,P4 | developer P3; tester P3; designer P4 read-only spec | developer: `src/review/`, `src/cli/`, `src/site/api/`, `src/site/state/`, `src/site/components/`, `src/site/styles/`, `src/model_gateway/`; tester: `tests/review/`, `tests/model_gateway/`; designer: no write scope | Exactly two uploads, CLI args, month/stage UI, one-table candidate checkboxes/comments/live totals, direct unit-group selection and model modes disabled/CLI/manual-app/optional-API. Designer supplies read-only visual spec because templating/site code belongs to developer; no shared ownership. | Candidate API stable → matching/single-alternative/multiple-unit subtotals, no cross-unit sum, all-checked-row cost, `0/0` no-match, checkbox/comment/live-recalculation, uploads, month/stage, manual/model-gateway, token and export-block tests pass. |
| P6 export + verify / P3,P5 | developer P4; tester P3 | developer: `src/export/`, `src/verify/`; tester: `tests/export/` | Dual-view cached-value flattening, month pair, one standalone Table-2 XLSX, atomic save/reopen/internal manifest. No source overwrite, copied formula or external link. | Review resolution available → `formula_count=0`, `external_link_count=0`, exactly one delivered file, cached-value parity, styles/merged/filter/comment/color, original hashes and internal-manifest tests pass. |
| P7 hardening/release / P1–P6 | tester P3; documentation-agent P1; devops P3; reviewer/security-reviewer P6 read-only | tester: `tests/e2e/`; documentation-agent: `docs/release/`; devops: `pyproject.toml`, `.github/workflows/`; reviewer/security-reviewer: no write scope | E2E corpus, release docs and packaging/CI evidence. No feature expansion. | All packages exit → E2E/manual/GPT-rejection/security audit pass; release gate. |

Before each package the orchestrator creates cards that split listed source and test scopes into non-overlapping exact paths; developer and tester never write the same path. P6 reviewer does one final read-only audit after the standard/critical work group.

## Cross-package acceptance corpus

1006 goldens above; schema fixtures 1004/0919/KITSO; upload/stage/month, misleading filenames, candidate sets, M04/M05, ambiguity, units, missing cached formula values, formula flattening, zero external links, duplicate rows, M13/M14, feedback and order independence. GPT tests prove strict rejection and no authority.

## Post-MVP adapters

После P7 и только по подтверждённой потребности отдельный package добавляет XLSB reader за тем же normalized-row контрактом. Entry: corpus unsupported XLSB + accepted-library/security decision. Exit: parity fixtures against trusted Excel values, no formula execution, same lineage/Decimal/export gates. RAR, cloud, auth и multi-user остаются вне scope до отдельного PRD.

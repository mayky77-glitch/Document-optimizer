---
type: orchestration
status: frozen
work_id: admin-verification-remediation-v2
objective: Make document verification numerically authoritative and close RA-001 through RA-018 without losing workbook data or publication safety.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ready
planning_parent_sha: dc2c32131face777f4cd3f4e121181e609154ed8
published_base_sha_source: exact planning commit containing this manifest and all Wave 1/2 cards
wave: 1
max_parallel: 3
max_spawns: 8
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-13T10:30:00+08:00
tags:
  - task/implementation
  - status/in-progress
  - domain/document-processing
  - capability/admin-panel
  - risk/high
links:
  - "[[admin-verification-accuracy-remediation|Master task]]"
  - "[[../errors/reconciliation-accuracy-findings|RA catalog]]"
---

# Verification accuracy remediation Gate 0

## Frozen owner contracts

- Numeric verdict follows [[../DECISIONS#DO-017: «Проверка документов» получает числовой oracle (2026-08-13)|DO-017]]:
  authorized rows aggregate per physical target row through existing `calculate_matches()` and
  `writer_calculations()`; equality is exact after existing target quantization. No extra epsilon,
  implicit conversion or classification-only `passed`.
- Target stage follows [[../DECISIONS#DO-018: этап цели выбирается без скрытого значения (2026-08-13)|DO-018]]:
  omitted stage auto-selects only one valid candidate; zero/multiple candidates fail before any row
  verdict. UI asks only when multiple choices exist.
- Source recognition remains universal across variable hierarchical multi-row headers. It uses
  structural anchors, column paths, adjacency and semantic data rows. No closed wording allowlist or
  narrow PropExtract normalization is allowed.
- Inputs are immutable. Git excludes private workbooks, generated results, screenshots and the
  unrelated untracked drawing-card UX specification.

## Dependency waves

Wave 1 runs three independent write streams:

1. [[admin-verification-remediation-source-target|source-target]] — RA-001/002/003/011/016 and
   target-stage discovery primitives.
2. [[admin-verification-remediation-group-state|group-state]] — RA-004/005/013.
3. [[admin-verification-remediation-artifact|artifact]] — RA-015/018.

After all three accepted merges and focused/full gates, Wave 2 runs:

1. [[admin-verification-remediation-numeric|numeric]] — numerical verdict and duplicate target
   category/exact-once safeguards.
2. [[admin-verification-remediation-stage-ui|stage-ui]] — optional stage API and minimal selector.
3. [[admin-verification-remediation-target-writer|target-writer]] — RA-007/008 target publication
   policy and ownership-safe cleanup.

Remaining RA-006/009/010/012 lifecycle/transaction work is frozen into a new work ID only after
Wave 2 integration because it shares service/execution paths. One P6 read-only review follows all
production waves and representative private shadow checks.

## Shared contracts

- `UniversalReconciliationSource-2.0`: enumerate coherent layouts; one unambiguous structural
  candidate; semantic detail onset; formula/value dual projection; controlled ambiguity/cache issue.
- `VerificationNumericOracle-2.0`: authorization selects category/mode only; calculation and target
  writer scale determine expected J/K; exact equality after quantization determines pass/fail.
- `TargetStageSelection-2.0`: `auto_selected | selection_required | not_found`, never silent `13.1`.
- `VerificationArtifact-2.0`: byte-preserving red styles, unique owned temp artifacts,
  `publish_no_clobber`, unchanged source digest and same-suffix XLSM support.
- `SafeGrouping-2.0`: safe quantity packages require one known exact normalized unit; dangling
  constraints fail closed; restart restore is atomic for all decision scopes.

## Baseline and acceptance

- Base full suite: `uv run --extra dev pytest -q` — `1667 passed, 25 skipped`.
- Each card has exact focused pytest, Ruff, format and diff checks.
- Each integration wave runs the complete reconciliation profile and full suite.
- Release needs a de-identified private comparison against original workbooks, source/target SHA
  preservation, formula/value/style delta allowlist and one downloadable artifact.
- Code Graph was attempted before edits and returned `Transport closed`; direct source/tests are the
  authoritative fallback until the MCP server recovers.

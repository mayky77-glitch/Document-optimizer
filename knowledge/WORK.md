---
type: work
tags:
  - knowledge/component
  - domain/document-processing
  - status/review
last_verified: 2026-08-16
updated: 2026-08-16
---

# Work

## Current

- [[tasks/reconciliation-real-release-audit|The real-layout release audit]] is accepted at product
  checkpoint `4294c15`. The private low-load shadow reached manual review without producing or
  applying an output; nine inputs were usable and three remained controlled ambiguities. All input
  workbooks stayed byte-identical.
- [[tasks/reconciliation-source-region-implementation|Region-local source discovery]] is accepted.
  It uses physical metric regions, exact merged ancestry, the shared schema resolver, interval-local
  detail validation, formula/cache pairing, and bounded sparse work. Styled empty cells do not
  consume the semantic coordinate budget.
- [[tasks/reconciliation-zip-local-flags|ZIP flag preservation]] is accepted. Period insertion now
  validates local and central flags by compression method and preserves allowed source metadata;
  LZMA requires its EOS flag.
- Reporting-period preview/apply, semantic identity v2, manifest v4, threaded comments, monetary
  scope semantics, namespace-safe writing, and [[tasks/reconciliation-period-ui|the reconcile-only
  period UI/API]] are integrated.

## Accepted release evidence

- Private shadow: 12 sources, one target, one uniquely selected stage, 2,787 source rows, 984 review
  rows, three continuable ambiguities, no output, no apply, all 13 inputs unchanged.
- Focused release gate: `581 passed, 1 skipped`.
- Full suite: `2225 passed, 25 skipped` in `28.07s`; skips are explicit real-data/model/performance
  opt-ins.
- Ruff check, Ruff format check, and `git diff --check` passed.
- Independent source and service reviewers reported `MERGE YES` with no P0/P1 findings.

## Next executable step

Publish the knowledge checkpoint, push `main`, and verify remote CI. Do not weaken controlled
ambiguity or remove adversarial tests merely to reduce the test count.

## Completed context

- [[tasks/reconciliation-max-accuracy-audit-v1|Maximum-accuracy audit]] established the original
  evidence catalog without production changes.
- [[tasks/reconciliation-writer-namespace-v3|Writer v3]] established descriptor-bound ZIP/XML
  validation, formula materialization, hashing, and no-clobber publication.
- [[tasks/reconciliation-global-batch-review-v5-final|Global batch review v5]] established
  authoritative row/group/package decisions and verified XLSX publication.

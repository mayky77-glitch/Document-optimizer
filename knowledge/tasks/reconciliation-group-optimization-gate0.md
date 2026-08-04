---
type: task
status: draft
card_id: reconciliation-group-optimization-gate0
version: 1
supersedes: null
work_id: reconciliation-group-optimization-v1
task_id: gate0
purpose: Freeze canonical state, private aggregate baseline, safety contracts, owners, scopes and acceptance before implementation.
role: worker
agent_role: orchestrator
owner: integration-owner
card_path: knowledge/tasks/reconciliation-group-optimization-gate0.md
card_commit_sha_ref: planning-commit
base_sha: 10eb20f00a63d6eb44714cc5a624d43809dfb665
dependency_shas:
  - 10eb20f00a63d6eb44714cc5a624d43809dfb665
branch: codex/reconciliation-group-optimization-v1
branch_base_sha: 10eb20f00a63d6eb44714cc5a624d43809dfb665
profile: L3
routing_grade: P6
progress_revision: 1
state_fingerprint: "sha256:2caea02058b30caf45067646da3c24018b9f8a93581091028de808e7f271a42d"
no_progress_count: 0
circuit_state: closed
routing_reason: Cross-component safety, privacy, canonical history and financial XLSX acceptance gate.
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: planned
actual_model: ""
actual_reasoning_effort: ""
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope: []
source_paths:
  - docs/RECONCILIATION_GROUP_OPTIMIZATION_PLAN.md
  - src/report_processor/reconciliation_grouping
  - src/report_processor/reconciliation_review
  - src/report_processor/admin_panel/reconciliation_execution.py
  - src/report_processor/stage_rag
forbidden_paths:
  - src
  - tests
  - pyproject.toml
  - uv.lock
  - .env
  - cache
  - logs
  - output
contract_versions:
  canonicalization: TermCanonicalization-2.0
  ontology: DomainOntology-1.0
  typed_slots: TypedSlots-1.0
  pattern_candidate: PatternCandidate-1.0
  pattern_registry: PatternRegistry-1.0
  feedback_graph: FeedbackGraph-1.0
  replay: GroupingReplay-1.0
  package_target: DecisionPackage-2.0
acceptance_commands:
  - "uv run pytest -q tests/contract/test_reconciliation_grouping_contract.py tests/unit/reconciliation_grouping tests/unit/admin_panel/test_reconciliation_execution.py tests/unit/admin_panel/test_reconciliation_batch_state.py tests/unit/admin_panel/test_reconciliation_state.py tests/integration/test_reconciliation_authoritative_flow.py tests/integration/test_reconciliation_batch_api.py tests/integration/test_reconciliation_real_data.py"
  - "uv run pytest -q tests/contract/test_dense_rag_contract.py tests/integration/test_dense_rag_drawing_card.py tests/unit/stage_rag"
  - "uv run ruff check src/report_processor/reconciliation_grouping src/report_processor/reconciliation_review src/report_processor/stage_rag tests/contract/test_reconciliation_grouping_contract.py tests/contract/test_dense_rag_contract.py tests/unit/reconciliation_grouping tests/unit/stage_rag"
  - "uv run ruff format --check src/report_processor/reconciliation_grouping src/report_processor/reconciliation_review src/report_processor/stage_rag tests/contract/test_reconciliation_grouping_contract.py tests/contract/test_dense_rag_contract.py tests/unit/reconciliation_grouping tests/unit/stage_rag"
  - "git diff --check"
tags:
  - task/implementation
  - status/planned
  - domain/document-processing
  - domain/rag
  - risk/high
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Reconciliation group optimization — Gate 0

## Purpose

Read-only canonicalization and baseline capture for the external master plan.
No production implementation is authorized while Gate 0 is STOP.

## Verified base and ancestry

- Canonical integration branch: `codex/reconciliation-group-optimization-v1`.
- Branch point: `codex/drawing-card-summary-v1` at the verified base below.
- Canonical HEAD: `10eb20f00a63d6eb44714cc5a624d43809dfb665`.
- Adopted Dense RAG range: `648d3c9..10eb20f`; this range is already present in HEAD.
- Plan source: `docs/RECONCILIATION_GROUP_OPTIMIZATION_PLAN.md`.
- Working tree was clean at initial inspection; current changes are Gate 0 metadata only.

## Stop/go decision

**PILOT GO for bounded development and shadow verification; production STOP.**
The user explicitly replaced historical recovery with a new three-source pilot
on 2026-08-03. The historical private source manifest remains unrecoverable and
the new pilot is deliberately not historically comparable. A deterministic,
ignored `ReconciliationPilotBaseline-1.0` aggregate now exists, repeats
byte-identically and reconciles manual taxonomy. It is sufficient to start
isolated Wave 1 development under frozen compatibility contracts. Production
activation remains forbidden until an independent representative holdout and
activation owners approve it.

## Owner boundary

The user approved the three-source pilot and allowed source-path disclosure in
the live task. Source paths remain excluded from this knowledge copy and Git.
Category/unit/pattern semantics, promotion/rollback, independent holdout and
Qdrant operational ownership are still required before production activation.

## Privacy and routing

Data classification is restricted. Do not record source terms, file names, local
paths, workbook contents, credentials, or raw prompts. CodeGraph-first lookup is
required. Local-AI triage route is `Codex`; external/local providers are skipped.

## Planned dependency waves

Gate 0 → Wave 0 Dense RAG verification → Wave 1 canonicalization/ontology/unit
contract → Wave 2 typed slots/semantic skeleton → Wave 3 profiler and candidate
miner → Wave 4 pattern registry and feedback graph → Wave 5 offline replay and
promotion gates → Wave 6 hybrid retrieval → Wave 7 constrained clustering and
package optimizer → Wave 8 active-learning UI → Wave 9 acceptance and shadow/
rollout gates.

## Wave 0 verification evidence

- Dense/grouping focused suite: 92 passed.
- Reconciliation/XLSX safety suite: 33 passed, 2 expected opt-in skips.
- Offline local RuBERT suite: 5 passed.
- Full suite: 928 passed, 24 skipped, 2 unrelated known failures outside the
  adopted Dense RAG range.
- Scoped Ruff, format and diff checks passed. Full-tree checks retain unrelated
  pre-existing debt.
- A disposable Qdrant 1.18.3 instance passed collection/index/snapshot restore
  smoke without reading or mutating the existing local instance.
- CodeGraph impact and dependency checks confirm Dense RAG remains explicitly
  injected and assistive; authoritative grouping/XLSX does not consume its
  scores or embeddings.

Authoritative XLSX output was not written during Gate 0. Input workbook digests
were unchanged before/after each pilot run.

## Shared-path ownership

Integration owner exclusively owns `knowledge/`, shared manifests, and release
contracts. Each implementation wave must reserve disjoint `src/` and `tests/`
subtrees. No task may write `.env*`, cache, logs, output, or spreadsheet
artifacts. Shared contracts require an exact dependency SHA before downstream
work starts.

Reserved next-wave scopes after Gate 0 GO:

- Wave 1: new `src/report_processor/work_semantics/` canonicalization, ontology
  and unit-contract modules/resources plus isolated tests. Existing exact group
  IDs and feedback keys remain unchanged.
- Wave 2: typed-slot and semantic-skeleton modules in the same package plus
  isolated tests, depending on the accepted Wave 1 commit SHA.
- Integration owner alone may later connect these contracts to existing
  reconciliation, drawing-card, admin or persistence paths.

## Contracts and acceptance

Frozen target contracts are `TermCanonicalization-2.0`, `DomainOntology-1.0`,
`TypedSlots-1.0`, `PatternCandidate-1.0`, `PatternRegistry-1.0`,
`FeedbackGraph-1.0`, `GroupingReplay-1.0` and `DecisionPackage-2.0`.
Legacy exact group IDs, five-position package keys and Dense Retriever 1.0
constructors remain compatible until replay proves a safe migration. Wave 0 must
repeat the adopted Dense RAG focused tests, full regression, opt-in model check,
Qdrant smoke, and prove authoritative XLSX equivalence. Exact private-baseline
commands and thresholds remain blocked pending owner approval.

## Pilot baseline (aggregate only)

`ReconciliationPilotBaseline-1.0` selects three readable sources by ascending
SHA-256 with distinct document indexes. The ignored aggregate is stored only at
`.codex/orchestration/reconciliation-pilot-baseline-v1/aggregate.json`, mode
`0600`; it is never staged or committed.

- source rows: 798; visible: 326; hidden zero-activity: 472;
- exact groups: 174; families: 143; packages: 143;
- safe packages: 3; manual packages: 140;
- unresolved rows: 326; unresolved groups: 174;
- primary manual taxonomy: category missing/ambiguous 134; unknown action 3;
  unknown object 3; sum 140 = manual packages;
- double membership: 0; source issues: 0; semantic assist disabled;
- aggregate SHA-256: `2caea02058b30caf45067646da3c24018b9f8a93581091028de808e7f271a42d`.

Two explicit runs produced byte-identical aggregate JSON. This pilot is a
development regression fixture, not a representative production benchmark.

## Recovery result and controlled fallback

Repository/history search found no historical source manifest or corpus
fingerprint. Multiple coherent local 12-workbook collections and row-count
subsets failed exact aggregate reproduction. They remain rejected.

Historical recovery was superseded by the user's three-source pilot decision.
Before production activation, the bounded follow-up remains
`RepresentativeCorpusSplit-1.0`: an owner-declared complete private universe,
digest-sealed manifest outside Git, deterministic schema-stratified split, zero
source overlap, a sealed holdout, repeatability and owner approvals.

## Handoff evidence

Current evidence is the verified branch/HEAD, adopted range, Wave 0 results,
recovery audit and reproducible pilot above. Wave 1 may begin only in its new
isolated scope and must preserve exact IDs, five-position package keys and
authoritative XLSX behavior. Production activation remains blocked as described.

---
type: task
status: superseded
work_id: reconciliation-wave3-closure-v1
role: worker
agent_role: developer
owner: "wave3-closure-core"
profile: L2
routing_grade: P4
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Final P6 probes isolated parameter-near ngram privacy and CLI classification defects"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-04
updated: 2026-08-04
write_scope:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "scripts/profile_reconciliation_corpus.py"
  - "scripts/mine_reconciliation_patterns.py"
  - "scripts/evaluate_reconciliation_patterns.py"
source_paths:
  - "src/report_processor/reconciliation_patterns/offline.py"
  - "scripts/profile_reconciliation_corpus.py"
  - "scripts/mine_reconciliation_patterns.py"
  - "scripts/evaluate_reconciliation_patterns.py"
depends_on:
  - "reconciliation-wave3-final-audit"
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 closure production fixes

## Goal

Close the four exact residual P6 probes: typed parameter-near matching,
source-adjacent uncovered n-grams, complete privacy deny-list, and stable CLI/schema errors.

## Scope and instructions

- Modify only `write_scope` paths.
- Build n-grams from original adjacent windows; keep only fully uncovered windows.
- Compare typed parameter variants without exposing raw quantity fragments.
- Block filenames, row coordinates, provenance/source-digest and quantity fragments.
- Map internal invariants to exit 5 and candidate schema failures to candidate-specific code.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths:
  - `src/report_processor/reconciliation_patterns/offline.py`
  - `scripts/profile_reconciliation_corpus.py`
  - `scripts/mine_reconciliation_patterns.py`
  - `scripts/evaluate_reconciliation_patterns.py`
- Commands and tests run:
  - `.venv/bin/ruff format --check` and `.venv/bin/ruff check` on Wave 3
    core plus assigned focused regression files: passed.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/reconciliation_patterns
    tests/contract/test_profile_reconciliation_corpus_contract.py
    tests/contract/test_mine_reconciliation_patterns_contract.py
    tests/contract/test_evaluate_reconciliation_patterns_contract.py`:
    `35 passed`.
  - `PYTHONPATH=src .venv/bin/pytest -q tests/unit/work_semantics
    tests/contract/test_work_semantics_contract.py
    tests/contract/test_work_semantics_wave2_contract.py
    tests/unit/reconciliation_grouping tests/unit/reconciliation_review`:
    `121 passed`.
- Result:
  - Typed parameter variants are described by shared structure and opaque slot
    signatures, never raw dimensions; original-token n-gram windows require
    every adjacent token to be uncovered.
  - The privacy projection blocks archive names, row coordinates, provenance,
    source-digest text, and raw parameter fragments without removing those rows
    from aggregate denominators.
  - Every CLI reports invariant failures as `INVARIANT_VIOLATION: ...` with
    exit 5; argparse usage remains exit 2. Candidate header/top-level/nested
    validation consistently returns `CANDIDATE_INPUT_INVALID`.
- Risks or follow-up:
  - Parameter values remain available only as private internal evidence and
    salted opaque signatures. This deliberately favors suppression over a
    potentially identifiable descriptive value.

## Handoff

Leave this card in `review` until orchestration accepts the result.

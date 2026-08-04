---
type: task
status: blocked
work_id: reconciliation-wave1-v1
role: worker
agent_role: developer
owner: "wave1-core"
profile: L1
routing_grade: P3
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "Bounded new-package implementation with frozen contracts maps to P3."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: inherited
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: "Executed through the inherited developer route; no separate runtime confirmation was exposed."
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope:
  - "src/report_processor/work_semantics"
source_paths:
  - "src/report_processor/work_semantics"
depends_on: []
tags:
  - "task/implementation"
  - "status/review"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 1 canonicalization ontology and unit contract

## Goal

Create an isolated, versioned shared semantics package for canonicalization,
multi-label domain ontology and unit identity/compatibility without changing any
existing reconciliation or drawing-card execution path.

## Scope and instructions

- Modify only `write_scope` paths.
- Contract versions: `TermCanonicalization-2.0`, `DomainOntology-1.0`,
  `UnitOntology-1.0`.
- Preserve audit text separately from semantic normalization.
- Cover NFKC, `ё/е`, whitespace, dash/quote variants, scoped homographs,
  conservative long-token typo repair, inflection stems and scoped aliases.
- Return primary/secondary actions and objects plus explicit conflicts.
- Unit identity must include canonical unit, physical family and scale; unknown
  units are exact-only and cannot broadly merge.
- Do not alter legacy exact IDs, feedback keys, existing package tuple shape or
  any current production integration.
- Do not stage, commit or push anything.
- `assigned_model` is only a requested route. Before `review` or `done`, record `launch_status: confirmed` with matching actual model/effort, or `inherited` with actual model/effort and a fallback reason.

## Completion evidence

- Changed paths: `src/report_processor/work_semantics/__init__.py`,
  `canonicalization.py`, `ontology.py`, and
  `resources/{__init__.py,domain_ontology.json}`.
- Commands and tests run: `uv run ruff format --check
  src/report_processor/work_semantics`; `uv run ruff check
  src/report_processor/work_semantics`; focused import/smoke assertions for
  audit-vs-semantic identity, multi-label conflicts, scale-compatible units and
  exact-only unknown units; `git diff --check -- src/report_processor/work_semantics`.
- Result: all checks passed. The package is isolated and does not modify or
  import legacy reconciliation/drawing-card execution paths.
- Remediation: replaced the broad action-label incompatibility set with explicit
  reviewed action conflict pairs. `supply + installation` is now multi-label
  evidence without a conflict; `installation + dismantling` remains explicit.
  Focused Wave 1 suite: `36 passed`.
- Risks or follow-up: JSON resource packaging should be covered by the Wave 1
  contract tests when a built wheel is introduced; this repository's existing
  package-data declaration currently names only legacy resource packages.

## Handoff

Superseded by `reconciliation-wave1-remediation-core` after final audit found
substantive semantics/resource gaps.

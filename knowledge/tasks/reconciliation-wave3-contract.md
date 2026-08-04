---
type: task
status: done
work_id: reconciliation-wave3-design-v1
role: worker
agent_role: architect
owner: "wave3-contract"
profile: L3
routing_grade: P6
progress_revision: 1
state_fingerprint: ""
no_progress_count: 0
circuit_state: closed
routing_reason: "L3 compatibility profile maps to P6."
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-sol
reasoning_effort: high
launch_status: confirmed
actual_model: gpt-5.6-sol
actual_reasoning_effort: high
fallback_reason: ""
model_fallback: false
last_verified: 2026-08-03
updated: 2026-08-03
write_scope: []
source_paths:
  - docs/RECONCILIATION_GROUP_OPTIMIZATION_PLAN.md
  - src/report_processor/work_semantics
  - src/report_processor/reconciliation_grouping
  - src/report_processor/reconciliation_review
depends_on:
  - reconciliation-wave2-remediation-core
  - reconciliation-wave2-remediation-tests
tags:
  - "task/architecture"
  - "status/draft"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Wave 3 offline profiler and candidate contract

## Goal

Freeze minimal deterministic, privacy-safe input/output and CLI contracts for
the three Wave 3 offline scripts before implementation.

## Scope and instructions

- Read-only architecture; do not edit files or use Git.
- Define one canonical versioned JSON/JSONL input model reusable by all scripts.
- Cover every profiler metric and candidate kind required by the master plan.
- Deduplicate support by semantic identity and independent document-set identity.
- Only confirmed outcomes may support candidates; suggestions remain inert.
- No XLSX writes, network, Qdrant mutation, external AI, or legacy integration.
- Specify deterministic ordering, fingerprints, error behavior, privacy output,
  exact CLI shape and acceptance tests.

## Completion evidence

- Changed paths: none; read-only architecture.
- Commands and tests run: read-only master-plan, Wave 1/2, grouping, review,
  serialization and CLI contract inspection.
- Result: frozen `ReconciliationCorpus-1.0`, `PatternCandidate-1.0`, profiler,
  miner, descriptive evaluator and three thin CLI contracts.
- Risks or follow-up: a trusted post-apply corpus exporter is still required;
  current feedback SQLite is not authoritative confirmed-outcome evidence.

## Frozen contract

### Boundary and files

Wave 3 produces only offline corpus descriptions and inert `proposed`
candidates. It never changes grouping/review, reads or writes XLSX, applies a
decision, activates a pattern, runs holdout/replay, mutates Qdrant, calls a
network or uses AI. Wave 5 owns replay, holdout, equivalence and promotion.

Production scope:

```text
src/report_processor/reconciliation_patterns/__init__.py
src/report_processor/reconciliation_patterns/offline.py
scripts/profile_reconciliation_corpus.py
scripts/mine_reconciliation_patterns.py
scripts/evaluate_reconciliation_patterns.py
```

`__init__.py` is empty and has no re-export. Tests:

```text
tests/unit/reconciliation_patterns/test_offline.py
tests/contract/test_profile_reconciliation_corpus_contract.py
tests/contract/test_mine_reconciliation_patterns_contract.py
tests/contract/test_evaluate_reconciliation_patterns_contract.py
```

No `pyproject.toml` or existing public API change.

### Versions and public API

```python
CORPUS_SCHEMA_VERSION = "ReconciliationCorpus-1.0"
CONFIRMED_OUTCOME_VERSION = "ConfirmedOutcome-1.0"
PROFILE_SCHEMA_VERSION = "ReconciliationCorpusProfile-1.0"
PATTERN_CANDIDATE_VERSION = "PatternCandidate-1.0"
CANDIDATE_SET_VERSION = "PatternCandidateSet-1.0"
CANDIDATE_EVALUATION_VERSION = "PatternCandidateEvaluation-1.0"

DEFAULT_PROFILE_TOP = 100
DEFAULT_MIN_SUPPORT_ATOMS = 2
MAX_SUPPORT_REFS = 10

load_corpus_jsonl(path: Path) -> CorpusSnapshot
load_candidate_jsonl(path: Path) -> CandidateSet
profile_corpus(corpus: CorpusSnapshot, *, top: int = 100) -> CorpusProfile
mine_candidates(corpus: CorpusSnapshot, *, min_support_atoms: int = 2) -> CandidateSet
evaluate_candidates(corpus: CorpusSnapshot, candidates: CandidateSet) -> CandidateEvaluationReport
canonical_json_bytes(value: object) -> bytes
fingerprint(value: object) -> str
```

Public models are frozen/slotted dataclasses and collections are tuple or
frozenset. Required models: `CorpusVersions`, `ConfirmedOutcome`,
`CorpusRecord`, `CorpusSnapshot`, `OutcomeSignature`, `PatternScope`,
`SupportSummary`, the seven typed proposal models, `PatternCandidate`,
`CandidateSet`, `CandidateEvaluation`, `CandidateEvaluationReport` and
`CorpusProfile`.

Candidate kinds are exactly:

```text
synonym_abbreviation
slot_template
include_exclude
split_merge
critical_modifier
must_link_cannot_link
category_specific_normalization
```

### Canonical corpus JSONL

UTF-8 without BOM, LF, exactly one header followed by rows. Unknown fields,
JSON float/NaN/Infinity, duplicate record IDs and invalid fingerprints are
rejected. Canonical compact JSON uses sorted keys and rows sorted by
`record_id`.

Header fields are exactly `record_type=header`, `schema_version`,
`corpus_fingerprint`, sorted unique `rule_ids`, and `versions` containing:

```text
term_canonicalization = TermCanonicalization-2.0
domain_ontology = DomainOntology-1.0
unit_ontology = UnitOntology-1.0
typed_slots = TypedSlots-1.0
semantic_skeleton = SemanticSkeleton-1.0
category_catalog = <non-empty>
rule_catalog = <non-empty>
outcome_export = ConfirmedOutcome-1.0
```

Each row has exactly:

```text
record_type=row
record_id=sha256:<64 lowercase hex>
record_fingerprint=sha256:<64 lowercase hex>
document_set_id=sha256:<64 lowercase hex>
document_type=<controlled string|null>
audit_text=<private local text>
unit=<private local unit|null>
category=<controlled category|null>
mode=quantity_cost|cost_only|null
object_kind=<controlled string|null>
eligibility=review_relevant|excluded_hazard|zero_ephemeral|unsupported
resolution=confirmed|manual_unresolved|exact_resolved|not_applicable
manual_action_id=sha256:<64>|null
matched_rule_ids=<sorted unique subset of header rule_ids>
outcome=<ConfirmedOutcome|null>
```

Confirmed outcome fields: version, `kind=confirmed_authoritative`,
`action=accept|reject`, mode, target_category, apply_fingerprint and
result_fingerprint. Confirmed requires outcome and forbids manual action;
manual unresolved requires review-relevant eligibility and manual action;
other resolutions forbid both. Accept requires mode/category; reject forbids
them. `document_set_id` is supplied by a trusted exporter from a logical
source+period+object identity and never contains a path/name.

### Semantic identity, confirmed evidence and dedup

Wave 3 builds facts through accepted `canonicalize_term`, `DEFAULT_ONTOLOGY`,
`unit_identity` and `build_semantic_skeleton`. Semantic identity fingerprints
semantic text, skeleton, canonical unit/exact-only state, non-display slots and
Wave 1/2 versions; it excludes outcome/category/mode and all record/document IDs.

A support atom is `(semantic_identity, document_set_id)`. One semantic identity
inside one document set counts once; two independent sets count twice. Only
`resolution=confirmed` supports mining. If one atom has different confirmed
`(action, mode-or-empty, target_category-or-empty)` signatures, it is
contradictory and supports none. Autosave, journal, RAG and unresolved evidence
never support a candidate.

### Profile

Canonical JSON always contains: `corpus_counts`, `uncovered_tokens`,
`uncovered_ngrams`, `unknown_actions`, `unknown_objects`, `unknown_units`,
`near_name_pairs`, `same_outcome_variant_sets`, `manual_action_drivers`,
`ontology_coverage`, `rule_coverage`.

Frequency items expose occurrence, support-atom, semantic-identity and
document-set counts. Ratios use numerator/denominator only. Manual drivers count
unique action IDs. Rule coverage includes zero-match rules. Ranked values sort
by descending support, descending occurrence, normalized value and item
fingerprint. `--top` truncates each ranked section independently and reports
`total_distinct`/`truncated`.

### Candidate eligibility

- synonym/abbreviation: conservative lexical-near variants, complete scope and
  uniform outcome;
- slot template: one skeleton, at least two slot signatures, uniform outcome;
- include/exclude: token/ngram/skeleton with uniform accept or reject;
- split/merge: near variants with same outcome, or one skeleton partitioned by
  different outcomes;
- critical modifier: forms differ by exactly one uncovered token and outcomes
  partition; proposal remains `hard_boundary_review` only;
- must-link/cannot-link: same outcome or different outcomes respectively;
- category-specific normalization: rewrite within one accepted target category
  and uniform outcome.

Lexical-near is punctuation-only, one differing token at equal token length,
an unambiguous abbreviation/initialism, or edit-distance-one for tokens of at
least eight characters. Incomplete scope, unknown unit, parse warning or
semantic conflict adds stable risk codes and prevents downstream promotion but
does not hide descriptive evidence.

Candidate ID fingerprints only version+kind+scope+proposal; evidence fingerprint
also includes support and risks. Support refs are at most ten sorted salted
support-atom hashes, never raw IDs. Every candidate has state `proposed`,
`descriptive_only=true`, `requires_owner_review=true`. Candidate-set JSONL has
one versioned header, then candidates sorted by kind, canonical scope and ID.

### Descriptive evaluator

Evaluator requires candidate source-corpus fingerprint equality, reapplies the
exact predicate on that same corpus and reports matched/support/contradiction/
unresolved/hard-boundary/parse-warning counts plus rational agreement and risks.
It always returns `evaluation_mode=descriptive_same_corpus` and
`promotion_eligible=false`; it has no holdout flag and never emits Wave 5
precision, forbidden-merge, before/after or equivalence metrics.

### CLI, errors and safe writes

```text
python scripts/profile_reconciliation_corpus.py --input CORPUS.jsonl --output PROFILE.json [--top 100] [--overwrite]
python scripts/mine_reconciliation_patterns.py --input CORPUS.jsonl --output CANDIDATES.jsonl [--min-support-atoms 2] [--overwrite]
python scripts/evaluate_reconciliation_patterns.py --input CORPUS.jsonl --candidates CANDIDATES.jsonl --output EVALUATION.json [--overwrite]
```

Success stdout is `OK <schema-version> <sha256 fingerprint>` and contains no
term or path. Exit codes: 0 success, 2 usage, 3 input/schema/version/fingerprint,
4 unsafe/existing/output I/O, 5 internal invariant. Stderr is a stable code and
controlled message without values, paths or traceback. Codes:

```text
INPUT_NOT_FOUND INPUT_NOT_REGULAR INPUT_INVALID_UTF8 INPUT_INVALID_JSON
INPUT_SCHEMA_INVALID INPUT_VERSION_UNSUPPORTED INPUT_FINGERPRINT_MISMATCH
CANDIDATE_INPUT_INVALID OUTPUT_EXISTS OUTPUT_UNSAFE OUTPUT_IO_ERROR
INVARIANT_VIOLATION
```

Outputs are canonical compact JSON/JSONL with final LF, no timestamp/hostname/
absolute path/random ID, mode 0600, same-directory temporary regular file,
fsync and atomic replace. Existing outputs require `--overwrite`; symlink output
or temp target is forbidden; parent is not auto-created; failure preserves old
output and deletes partials. Inputs are byte-identical after each run and no
cache or other file is created.

### Privacy allowlist and acceptance

Output may contain normalized tokens/ngrams/skeletons/templates, controlled
labels, aggregates, proposals and opaque salted fingerprints. It must never
contain audit text, record/document/action/apply/result IDs, filenames/paths,
sheet/cell/row coordinates, formulas/comments, provenance, quantity/cost,
source/target digests or workbook bytes. Outputs are private local artifacts and
must not be added to Git or project knowledge.

Acceptance covers strict schemas/versions/fingerprints, shuffled-input byte
identity, support/document-set dedup, contradictory atom exclusion,
confirmed-only evidence, all profile sections and seven candidate kinds, unique
manual actions, zero-coverage rules, same-corpus evaluator, mismatch rejection,
absence of Wave 5 verdicts and forbidden privacy fields, mode 0600/symlink/
overwrite safety, byte-identical inputs, no network/Qdrant/openpyxl/AI calls,
no legacy import/integration, focused tests and Ruff/format.

### Known prerequisite

Current feedback storage lacks authoritative apply/result fingerprints and an
independent document-set identity, so Wave 3 must not read it directly. A trusted
post-apply exporter is a later prerequisite; until then use synthetic fixtures
or a private manually produced snapshot. Per-rule match IDs likewise come from
the trusted snapshot producer because current ontology does not expose them.

## Handoff

Leave this card in `review` until orchestration accepts the result.

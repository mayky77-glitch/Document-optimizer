# Reconciliation global batch review v5

Accepted master product and implementation plan. Not a frozen ORDA launch card.
Gate 0 must derive bounded task cards, exact scopes, branches, contract versions
and acceptance commands from this document.

## 1. Problem

The authoritative reconciliation flow now works, but the real private acceptance
set produces 2,953 non-filtered source rows and 500 global name/unit cards. Five
hundred decisions are not a usable workflow. Adding ordinary UI filters over the
same 500 cards would treat the symptom only.

The next version must preserve current authoritative row decisions while adding a
second grouping level: a small set of safe decision packages. The operator should
normally complete the review in 5-20 meaningful actions, with doubtful rows kept as
visible exceptions.

## 2. Verified starting point

Starting feature branch: `codex/drawing-card-summary-v1`.

Verified implementation baseline before this plan: `a351a0b`.

Current accepted behavior:

- 12 of 12 real private source workbooks are usable.
- 2,953 rows produce 500 normalized name/unit groups and 15 categories.
- Group and row decisions change the calculation and verified XLSX.
- `quantity_cost` and `cost_only` are direct two-position controls.
- Explicit decisions persist as private feedback.
- One broken source does not suppress usable groups.
- Public row IDs are opaque.
- The public payload excludes paths, sheets, formulas, coordinates, raw warnings,
  provenance and evidence.
- Quantity and cost display with two decimal places.
- Desktop/mobile and light/dark work without horizontal overflow.
- `app.py` is near the hard project limit and must not absorb new contracts.

Source code and focused tests remain authoritative. This baseline must be rechecked
at Gate 0; vault text alone is not evidence.

## 3. Product decisions from the conversation

### 3.1 Review hierarchy

```text
All relevant rows
  Global decision package
    Semantic family
      Existing normalized name/unit group
        Source rows and row exceptions
```

The current 500 groups remain the exact membership boundary underneath the new
layer. They are not deleted or made inaccessible.

### 3.2 Authoritative behavior

- Accepting a package expands to a frozen list of exact group and row IDs.
- Package decisions affect classification, calculation and output XLSX.
- A semantic-family override wins over its package.
- A group override wins over its package or family.
- A row override wins over every broader decision.
- A changed input digest makes the old package version stale.
- Repeated apply of a ready result remains idempotent.
- Mass acceptance and equivalent sequential decisions must produce the same XLSX.

### 3.3 Zero-activity rows

A row is hidden only when both effective values are exactly zero after Decimal
normalization:

```text
quantity = 0.00
cost = 0.00
```

Contract:

- Do not show the row in cards or package counts.
- Do not count it as unresolved.
- Do not include it in semantic clustering or package decisions.
- Do not persist accept, reject, negative feedback or a permanent exclusion rule.
- Keep it in the current job data with an internal ephemeral `zero_activity` state.
- Recompute the predicate for every upload.
- If either value becomes non-zero in a later document, classify and show the row
  normally.
- Quantity zero with non-zero cost remains visible.
- Cost zero with non-zero quantity remains visible.
- Hiding a zero row must not change other calculations or target cells.

### 3.4 Safety and privacy

- Do not expose paths, sheet names, formulas, cell coordinates, provenance,
  evidence, source digests or model prompts.
- A controlled source issue may show only safe basename, short Russian comment and
  repair instruction.
- Never send private repository code, workbook content, names or personal data to a
  public model.
- Local model output is assistive, never authoritative.

## 4. Target user experience

### 4.1 Three queues

Show three operator queues instead of one long list:

1. `Можно принять пакетом`.
2. `Нужны уточнения`.
3. `Новые виды работ`.

Default queue: safe packages.

### 4.2 User-facing summary

Use short Russian product language:

- `24 пакета можно принять`.
- `7 пакетов требуют проверки`.
- `18 строк являются исключениями`.

Do not show raw confidence, internal rule IDs or English metrics.

### 4.3 Package card

Each card contains:

- short semantic family name;
- proposed target category;
- direct `Количество + стоимость` / `Только стоимость` switch;
- number of families, groups, relevant rows and exceptions;
- aggregated quantity and cost with two decimals;
- one short human reason;
- `Принять пакет` and `Отклонить`;
- expandable families and exact member rows.

No modal for routine decisions. No dropdown for the two-state mode. No duplicate
confirmation buttons.

### 4.4 Filters

Primary product filters:

- `Можно принять пакетом`;
- `Есть расхождения`;
- `Новые формулировки`;
- `Уже знакомые`;
- `Только стоимость`;
- `Подозрительные значения`.

Secondary controls:

- fuzzy search by work name;
- category;
- accounting mode;
- compatible unit family;
- package size;
- has exceptions;
- ready for mass acceptance;
- manually changed.

### 4.5 Sorting

Default order:

1. Packages covering the most rows.
2. Packages with the largest absolute cost impact.
3. Safest agreement.
4. Packages with exceptions.
5. Unknown work families.

### 4.6 Comfort features

- `Принять все безопасные` applies only conflict-free packages.
- Show a concise preview before mass apply.
- Keep the card position stable after a decision; move it to `Готово` after a
  short confirmation state.
- Provide `Отменить` for the last package or mass action without rereading
  workbooks.
- Autosave every decision and restore progress after refresh.
- Restore decisions only when all version/digest checks still pass.
- Show only differences and exceptions by default; full membership stays
  expandable.
- Optional desktop shortcuts: `A`, `R`, `1`, `2`, `J`, `K`, `U`.
- Keep keyboard controls additive; visible controls remain complete and accessible.

### 4.7 Human explanations

Allowed examples:

- `Совпадает с ранее подтверждёнными строками`.
- `Отличается только диаметром`.
- `Есть конфликт единиц`.
- `Найден признак слаботочного кабеля`.
- `Раньше похожая строка была отклонена`.

The explanation is presentation only and never changes classification.

## 5. Feature extraction

Build a deterministic, versioned feature contract before adding model assistance.

### 5.1 Safe normalization

- Unicode normalization and case folding.
- Russian `ё/е` normalization where appropriate.
- Whitespace and punctuation normalization.
- Unit alias normalization.
- Morphological normalization for common construction verbs and nouns.
- Typo-tolerant character n-grams.
- Versioned abbreviation dictionary.

### 5.2 Semantic fields

Extract separately:

- action: installation, laying, welding, concreting, supply, testing, dismantling;
- object: cable, pipeline, metal structure, foundation, equipment;
- critical modifiers: power, low-current, reinforced-concrete, diameter, voltage;
- negative/exclusion markers: testing, price/cost, dismantling, supervision;
- typed numeric modifiers;
- compatible unit family;
- proposed category and mode;
- positive and negative feedback matches.

### 5.3 Typed numbers

Do not remove every number. Classify its role:

- diameter such as `DN 50`;
- voltage such as `10 кВ`;
- mass threshold;
- length;
- stage/index context;
- non-semantic document or drawing identifier.

Typed modifiers may split a family even when the main action/object match.

## 6. Hard constraints

Hard constraints always outrank model similarity. Never create a safe package that
mixes:

- installation and price/cost;
- work and testing;
- power and low-current cable;
- installation and dismantling;
- incompatible units;
- quantity-bearing and cost-only semantics when modes differ;
- a category unavailable for any member source index;
- an explicit negative feedback pair;
- any domain exclusion already captured by the accepted reconciliation rules.

Known critical modifiers include power, low-current, reinforced-concrete,
dismantling, testing, cost, supply, fabrication and supervision. This list is
versioned and expanded only through tested rule changes.

## 7. Decision hierarchy and matching

Priority order:

1. Exact valid feedback.
2. Tested deterministic domain rules.
3. Versioned synonym and abbreviation rules.
4. Normalized action/object family.
5. Embedding similarity.
6. Optional local generative analysis for unresolved cases.

The model cannot override accepted feedback or hard constraints.

## 8. Semantic clustering

### 8.1 Package key

Initial package boundary:

```text
target category + accounting mode + compatible unit family + action + object
```

Run semantic clustering only inside this boundary.

### 8.2 Clustering method

Prefer category-aware hierarchical clustering with a bounded maximum distance or
complete-linkage rule. Avoid naive transitive union-find: a chain of partly similar
names can merge unrelated work.

The number of clusters must emerge from calibrated thresholds, not a hard-coded
package count.

### 8.3 Exceptions

Keep a row/group as an exception when:

- a critical modifier differs;
- its embedding is an outlier relative to the package;
- unit or mode differs;
- a negative rule applies;
- historical feedback disagrees;
- category availability differs;
- deterministic and model signals conflict.

An exception does not destroy the safe remainder of a package.

## 9. Local model plan

### 9.1 Runtime discovery

Do not assume a model name from this plan. Gate 0 must inspect existing code,
configuration and local runtime. The project already references a pinned local
`cointegrated/rubert-tiny2` embedding model; verify whether it fits this workflow.
Also check whether a local Ollama model is installed and permitted by
`$local-ai-pipeline`.

No installation, public upload or new external service without a separate product
decision.

### 9.2 Allowed model jobs

- Create embeddings for unknown normalized work names.
- Retrieve similar positive and negative feedback examples.
- Extract action, object, critical modifiers and exclusions into strict JSON.
- Detect semantic outliers inside a deterministic package.
- Suggest a concise package label.
- Draft one short Russian explanation.
- Mine repeated confirmations, rejections, synonyms and split patterns offline.
- Prioritize ambiguous examples that would provide the most useful operator
  feedback.

### 9.3 Forbidden model jobs

- Applying an operator decision.
- Calculating quantity or cost.
- Determining unit compatibility alone.
- Writing XLSX.
- Changing production rules automatically.
- Seeing private paths, sheets, formulas, provenance or raw repository code through
  an external provider.
- Becoming a required dependency for the site.

### 9.4 Model contract

Use a strict bounded schema similar to:

```json
{
  "action": "монтаж",
  "object": "металлоконструкция",
  "modifiers": ["фундамент"],
  "negative_markers": [],
  "suggested_category": "Монтаж металлоконструкций"
}
```

Reject invalid JSON, unknown category IDs, overlong values and unsupported fields.
Cache by normalized input, unit, model revision, feature-contract version and rule
version. Add timeout, bounded batch size and deterministic fallback.

### 9.5 Reliability

Do not trust model self-confidence. Package safety comes from measured historical
accuracy, nearest-neighbor margin, agreement with deterministic signals and absence
of hard conflicts.

Use agreement between:

- hard rules;
- valid feedback;
- deterministic feature family;
- embedding retrieval;
- optional generative structured analysis.

Any consequential disagreement moves the package to `Нужны уточнения`.

### 9.6 Rule optimization

The local model may propose:

- a new synonym;
- a new abbreviation;
- a critical modifier;
- a negative pair;
- a split rule;
- a merge rule.

Every proposal must run against historical decisions and forbidden-pair tests.
Promote it only when the measured objective improves without breaking safety gates.
Store rule version and rollback metadata. Never mutate rules directly from model
output.

## 10. Script and module architecture

Preferred new package:

```text
src/report_processor/reconciliation_grouping/
  models.py
  features.py
  zero_activity.py
  constraints.py
  deterministic.py
  semantic_model.py
  clustering.py
  packages.py
  optimizer.py
```

Admin boundary additions:

```text
src/report_processor/admin_panel/reconciliation_batch_state.py
src/report_processor/admin_panel/reconciliation_batch_presentation.py
src/report_processor/admin_panel/assets/reconciliation-batches.js
```

Final file names may change after exploration, but responsibilities must remain
separate. Do not add new independent domains to `app.py`. Review `service.py` for
decomposition before adding lifecycle logic; it is already above the 500-line
review signal.

Pipeline:

```text
upload validation
source extraction
normalization
zero-activity view filter
hard constraints
valid feedback
deterministic match
optional local semantic assistance
semantic families
global decision packages
operator decision overlay
authoritative calculation
verified XLSX publication
private feedback persistence
```

Each stage should accept immutable input and return a typed result. Presentation
filtering must never mutate source rows or calculation data.

## 11. Persistence and versioning

- Autosave job-local package, family, group and row decisions.
- Persist reusable feedback only after verified authoritative apply.
- Do not persist `zero_activity` as a negative decision.
- Package feedback contains semantic signature plus hard constraints, not source
  provenance.
- Exact feedback has priority over learned generalization.
- Rejection creates a negative example or split constraint, not a broad permanent
  ban without evidence.
- Include input digests, category catalog version, rules version, feature-contract
  version and model revision in optimistic concurrency/version hashes.
- A stale package decision must be rejected before calculation.

## 12. Performance

- Run deterministic rules first.
- Send only unresolved/ambiguous normalized text to the local model.
- Compute each embedding once per versioned cache key.
- Use bounded batches and timeout.
- Keep a full deterministic fallback.
- Avoid blocking the page on model explanations when safe deterministic packages
  are already available.
- Preserve current 1-32 file input limit and fail-soft workbook behavior.

## 13. Required tests and invariants

### 13.1 Zero activity

- `0.00 + 0.00` is absent from review and unresolved counts.
- It creates no feedback or permanent rule.
- The same semantic row with a later non-zero value appears normally.
- One non-zero dimension keeps the row visible.
- Hiding zero rows does not change other calculations.

### 13.2 Package membership

- Every relevant row belongs to exactly one visible package/family path.
- No duplicate membership.
- Every existing group remains expandable.
- Hard-conflict pairs never enter the same safe package.
- Outliers become explicit exceptions.
- Identical input produces identical packages and ordering.

### 13.3 Decisions

- Package decision fans out exactly once.
- Family, group and row precedence is deterministic.
- Undo restores the prior effective decisions.
- Autosave restores only a compatible version.
- Mass and sequential acceptance produce identical effective decisions and XLSX.
- Invalid category availability is rejected before apply.

### 13.4 Model fallback

- Timeout, invalid JSON and unavailable model leave deterministic packages usable.
- Model output cannot bypass hard constraints.
- Cache invalidates when model/rule/feature versions change.
- Negative feedback prevents a rejected semantic match from appearing as safe.
- No private field enters the model prompt or public payload.

### 13.5 UI

- One direct two-position mode control.
- One accept/reject action pair per scope.
- Keyboard and pointer flows.
- Focus management and accessible names.
- Stable position after decisions.
- Desktop and 390 px mobile, light and dark, no overflow.
- No console errors.
- Every displayed number has two decimal places.

### 13.6 Output

- Same decisions preserve current calculation semantics.
- Source rubles use the accepted coefficient/routing and target adapter rules.
- Quantity and million-RUB output round half-up to two decimals.
- Result reopens successfully.
- Inputs remain byte-identical.
- Ready-result replay stays idempotent.

## 14. Acceptance targets

Use the current real private set as baseline, without recording private paths or
basenames in tests or knowledge.

- Reduce 500 top-level review cards by at least 80%.
- Target 20-50 top-level packages on the current set, but never force unsafe merges
  to hit this range.
- Keep 100% of non-zero relevant rows accessible.
- Produce zero known forbidden-pair merges.
- Preserve exact calculation equivalence for equivalent decisions.
- Require materially fewer actions on a second similar document set.
- Keep local model optional and fully local.
- Keep public payload privacy contract.

Compression is subordinate to safety. If 50 packages cannot be reached without
unsafe merges, ship a higher count and report the evidence.

## 15. ORDA execution plan

Operating mode: `standard`, promoted to architecture-grade review where needed.
User explicitly requests a high-reasoning GPT owner and ORDA orchestration.

Root/integration owner route:

```text
P5/P6 -> orchestrator/integration owner -> gpt-5.6-sol -> high
```

Use persistent roles and their pinned model/effort. Do not manually claim an
unconfirmed subagent model. Maximum three independent write streams.

### Gate 0

The new task must:

1. Read `AGENTS.md`, `$adaptive-model-routing`, `$orda`, `$local-ai-pipeline`,
   `knowledge/INDEX.md`, `knowledge/ORCHESTRATION.md`, this plan and the accepted v4
   final card.
2. Confirm canonical repository, branch/HEAD, clean worktree and published base.
3. Check `.codegraph/`; use CodeGraph first only if it exists.
4. Inspect current grouping, review state, presentation, feedback, calculation and
   local-model adapters against source and tests.
5. Run one bounded local-model triage only when useful and allowed. Do not send
   private repository content to Gemini or any public model.
6. Freeze shared contracts, task cards, exact non-overlapping scopes, acceptance
   commands and ORDA state before implementation.
7. Commit and publish Gate 0 before launching write tasks.

### Suggested dependency waves

Wave 1: contracts and deterministic core.

- Architect/explorer: read-only execution map and frozen contracts.
- Developer: feature extraction, zero-activity predicate, hard constraints,
  deterministic families and package models.
- Tester: tests/fixtures only after the contract is frozen; no production edits.

Wave 2: authoritative lifecycle and presentation contract.

- Developer: package state, precedence, autosave/versioning and service integration.
- Designer: dedicated non-overlapping UI structure and responsive/accessibility
  scope.
- Tester: focused API/state/presentation regressions.

Wave 3: local semantic assistance and optimization.

- Developer: local model adapter, strict JSON, embedding/cache/timeout/fallback.
- Developer or data-focused worker: offline rule-proposal scorer in a disjoint scope.
- Tester: model fallback, privacy and deterministic-equivalence tests.

Wave 4: integration acceptance.

- Integrate in dependency order with ORDA `merge --no-ff` rules.
- Run focused unit/integration, Ruff/format, Node and browser smoke only; do not run
  the full suite unless scope/risk or a failing contract requires a new decision.
- Run real private 12-file package-count, membership, interaction and XLSX smoke.
- Run one final P6 read-only correctness/privacy review.
- Remediate only substantive findings under loop/recovery limits.
- Update knowledge once after acceptance.
- Restart the local non-production application.
- Commit and push final changes.

Wave scopes are suggestions, not launch authority. Gate 0 must adapt them to the
actual code graph and reserve exact paths before any write agent starts.

## 16. Explicit non-goals

- No ordinary filter-only redesign that leaves 500 top-level decisions.
- No auto-approval based only on a model score.
- No second calculation engine.
- No public AI service for private workbook classification.
- No model-written production rules without measured regression gates.
- No hidden deletion of rows.
- No permanent rejection of zero-activity rows.
- No new monolith in `app.py`, `service.py` or one oversized frontend file.
- No full-suite run by default.

## 17. Completion report

Final report must state:

- real top-level package count before/after;
- visible relevant row membership and exception count;
- zero-row behavior across repeated documents;
- exact actions exercised in browser;
- calculation/XLSX evidence;
- local model actually used, its local revision/runtime and fallback behavior;
- focused test counts;
- responsive/theme evidence;
- reviewer findings and remediation;
- final commit, pushed branch and running local URL.

Never include private paths, sheet names, formulas, coordinates or real basenames.

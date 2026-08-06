---
type: task
status: frozen
card_id: drawing-card-ux-wave3-feedback-ledger
version: 1
supersedes: null
work_id: drawing-card-ux-wave3-v1
task_id: feedback-ledger
purpose: Implement a private append-only atomic feedback ledger and exact safe lookup contract.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave3-feedback-ledger.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 432753ce1f65b8b75e90040899de2227f276b9ae
branch: codex/drawing-card-ux-wave3-feedback-ledger
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/review/feedback.py
  - tests/unit/drawing_card/test_feedback_store.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/review/clusters.py
  - knowledge
  - docs
contract_versions:
  input: DrawingCardReviewDecision-1.0
  output: DrawingCardFeedback-2.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_feedback_store.py
  - uv run ruff check src/report_processor/drawing_card/review/feedback.py tests/unit/drawing_card/test_feedback_store.py
  - uv run ruff format --check src/report_processor/drawing_card/review/feedback.py tests/unit/drawing_card/test_feedback_store.py
  - git diff --check
---

# Feedback ledger

Create a fixed-schema private JSONL ledger. Every decision entry contains tenant/project scope,
normalized work and SHA-256 work fingerprint, proposed and selected category, contract position,
match mode, normalized source unit, unit policy, action (`confirm`, `reject`, `reclassify`,
`exclude`), sorted input SHA-256 hashes, model/rules versions, author, UTC time, subject type
(`row`/`packet`), exact member IDs, validity and optional superseded event ID.

Required public Python contract:

- immutable `FeedbackContext` and `FeedbackEntry` dataclasses;
- `FeedbackStore(path).append_page(entries)` that commits all-or-nothing using a same-directory
  temporary file, flush, file `fsync`, `os.replace`, directory `fsync` where supported and `0600`;
- deterministic duplicate-event idempotency; conflicting duplicate IDs fail the whole page;
- `lookup_exact(context)` returns only the latest valid non-hazard entry when every context field,
  version and hash matches exactly;
- `invalidate(event_id, author, created_at, reason)` appends a complete invalid decision clone that
  supersedes the target and makes later lookup miss without deleting audit history;
- bounded reads and fixed validation; no absolute paths or source workbook metadata.

Tests must cover atomic page rollback, tenant/project isolation, every exact-key dimension, version
invalidation, explicit invalidation, hazards, conflicting duplicates, permissions and retained
audit history. Similar text must never be an exact hit.

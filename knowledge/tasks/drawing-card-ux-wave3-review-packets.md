---
type: task
status: frozen
card_id: drawing-card-ux-wave3-review-packets
version: 1
supersedes: drawing-card-review-clusters-1
work_id: drawing-card-ux-wave3-v1
task_id: review-packets
purpose: Strengthen review clusters into conservative exact packets and add explicit review metrics.
role: developer
card_path: knowledge/tasks/drawing-card-ux-wave3-review-packets.md
card_commit_sha_source: launch envelope containing the exact frozen card
base_sha_source: same planning commit supplied in the launch envelope
dependency_shas:
  - 432753ce1f65b8b75e90040899de2227f276b9ae
branch: codex/drawing-card-ux-wave3-review-packets
branch_base_sha_source: same exact planning commit supplied in the launch envelope
write_scope:
  - src/report_processor/drawing_card/review/clusters.py
  - src/report_processor/drawing_card/audit/review_metrics.py
  - tests/unit/drawing_card/test_review_clusters.py
  - tests/unit/drawing_card/test_review_metrics.py
forbidden_paths:
  - src/report_processor/admin_panel
  - src/report_processor/drawing_card/workflow.py
  - src/report_processor/drawing_card/models.py
  - src/report_processor/drawing_card/review/feedback.py
  - knowledge
  - docs
contract_versions:
  input: DrawingCardReviewCluster-1.0
  output: DrawingCardReviewPacket-2.0+DrawingCardReviewMetrics-1.0
acceptance_commands:
  - uv run pytest -q tests/unit/drawing_card/test_review_clusters.py tests/unit/drawing_card/test_review_metrics.py
  - uv run ruff check src/report_processor/drawing_card/review/clusters.py src/report_processor/drawing_card/audit/review_metrics.py tests/unit/drawing_card/test_review_clusters.py tests/unit/drawing_card/test_review_metrics.py
  - uv run ruff format --check src/report_processor/drawing_card/review/clusters.py src/report_processor/drawing_card/audit/review_metrics.py tests/unit/drawing_card/test_review_clusters.py tests/unit/drawing_card/test_review_metrics.py
  - git diff --check
---

# Conservative review packets

Add immutable `ReviewPacketContext` and extend `ReviewCluster` additively with pivot ID,
packet eligibility, match mode, unit compatibility class, rules version and controlled difference
fields. When strict contexts are supplied, a multi-row packet is allowed only for exact equality of
tenant, project, normalized work, source type, review reason, proposed category, match mode, unit
compatibility class, transactional row role, rules version and quantity/cost resolution mode.

Hazard rows are always singleton and visibly marked. `UNIT_MISMATCH` rows share a packet only for
the same resolution mode. `MULTIPLE_CATEGORY_MATCHES` may share only by exact normalized work and
the other exact fields, never semantic similarity. Packet identity includes sorted members so a
changed set is stale. Keep the old no-context behavior for internal compatibility, but the strict
path must fail closed on missing context.

Add a small `ReviewMetrics` contract with explicit counters and safe rates for review candidates,
queued review rows, packets, singleton share, opened cards, feedback hits/rate, packet exclusions,
overrides, review applies and post-review errors/rate. Counters must be incremented explicitly and
serialize to primitive values.

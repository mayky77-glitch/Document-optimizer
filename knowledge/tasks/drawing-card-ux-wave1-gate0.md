---
type: orchestration
status: frozen
work_id: drawing-card-ux-wave1-v1
objective: Make drawing-card source recognition fail closed and expose a complete, explainable row funnel without changing valid matching decisions.
project_root: /Users/x/Documents/Сооотношение документов/Document-optimizer-ux-wave1
planning_parent_sha: 8f8d35c680cdb4b2ff437ab564048615a557c24f
published_base_sha_source: planning commit containing this manifest and both frozen task cards
wave: 1
max_parallel: 2
max_spawns: 4
max_retries: 1
merge_method: merge-no-ff
shared_paths_owner: integration
data_classification: restricted
created_at: 2026-08-06T14:00:00+08:00
---

# Gate 0: drawing-card UX Wave 1

## Precedence and compatibility

The source code and passing tests are the compatibility baseline. Confirmed corrections from
the current user session override conflicting historical notes or specification examples:

- column discovery is semantic and tolerant of case, punctuation, line breaks, `е/ё`,
  abbreviations and multi-row parent/leaf headers;
- weak or ambiguous discovery is never silently published;
- position hierarchy may be used only when an explicit semantic position header is recognized;
  content-only position inference cannot hide rows;
- contract and performed values must describe comparable cumulative periods;
- the authoritative residual is an explicitly identified contract-residual block; an
  intermediate monthly slice must not be substituted;
- when the source schema establishes `whole-period performed + explicit residual`, the full
  contract basis is derived from those comparable values, not from a partial contract slice.

No user workbook, generated workbook, absolute source path, workbook content or untracked master
specification is added to Git. Synthetic tests must encode the structural cases without copying
private source data.

## Dependency graph

1. Parallel task `schema-safety` owns source schema recognition and comparable-period extraction.
2. Parallel task `funnel-audit` owns exhaustive row dispositions, exclusion audit and anomaly
   safety. It does not change column resolution.
3. Integration owner merges both with `--no-ff`, resolves shared public wiring, and freezes a
   downstream presentation/test card only against the accepted merge SHA.
4. A P6 read-only review closes the wave after focused and full validation.

## Shared contracts

- `DrawingCardSchemaRecognition-1.0`: `recognized | uncertain | unsupported`, with controlled
  reason codes and confidence.
- `DrawingCardComparablePeriod-1.0`: explicit residual plus whole-period performed; no partial
  slice substitution.
- `DrawingCardRowDisposition-1.0`: every extracted row has exactly one terminal disposition and
  an audit-safe reason/rule/context record.
- `DrawingCardFunnel-1.0`: counts conserve from extracted rows through exclusions, classified,
  manual review and output contribution; `unclassified` is explicit.

## Baseline

- `uv run pytest -q tests/unit/drawing_card tests/unit/admin_panel/test_drawing_card_service.py tests/integration/test_drawing_card_admin.py tests/integration/test_drawing_card_ui_contract.py` — 170 passed, 2 skipped.
- `uv run ruff check src/report_processor/drawing_card src/report_processor/hierarchy src/report_processor/admin_panel tests/unit/drawing_card tests/unit/admin_panel` — passed.
- Existing hierarchy-focused baseline — 37 passed.

## Release acceptance

- Ambiguous aliases, content-only position inference, conflicting roles and suspicious repaired
  metrics become `uncertain` or `unsupported` and block strict publication.
- Header variants resolve through normalized aliases and multi-row context without fixed-column
  fallback.
- Contract/performed comparison uses a verified comparable cumulative basis.
- Funnel counts conserve and every hierarchy/resource/manual-review exclusion carries a
  controlled reason, rule and source-row context in the private audit.
- An anomalous exclusion share cannot silently publish.
- Existing public payload remains additive and path-safe; later presentation may expose only
  safe basenames and controlled sheet/row context explicitly authorized by this work.


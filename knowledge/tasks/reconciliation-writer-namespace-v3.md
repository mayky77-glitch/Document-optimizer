---
type: orda_task
status: accepted
card_id: reconciliation-writer-namespace-v3
version: 3.1
work_id: reconciliation-writer-namespace-v3a
task_id: writer-namespace-v3
purpose: Finish namespace-safe writing with a compact immutable index and same-handle ZIP admission.
role: developer
route: P5 -> developer / inherited runtime; reason: byte-offset XML parsing, archive safety and writer hot path.
launch_status: accepted
accepted_feature_sha: d71b7f43c72493ef7c77de9a278f27ad453274da
accepted_orda_integration_sha: 206fcbbb1d3a0e9b90d8a0c1ae341c0f6a7c0ddb
published_main_integration_sha: fee01c420bc3a838a34cb38490b4741c8a51e14f
accepted_at: 2026-08-15
card_path: knowledge/tasks/reconciliation-writer-namespace-v3.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: 2b616c3220961e9c0c1e9cba119836fce4f8cd7d
implementation_seed_sha: 251808cba90a72485448f83e027a1c9a716dcf10
branch: codex/reconciliation-writer-namespace-v3
branch_base_sha_source: exact planning commit containing this card
write_scope:
  - src/report_processor/excel_writer/ooxml.py
  - src/report_processor/excel_writer/engine.py
  - src/report_processor/excel_writer/formula_materialization.py
  - tests/unit/excel_writer/test_ooxml.py
  - tests/unit/excel_writer/test_engine.py
  - tests/unit/excel_writer/test_formula_materialization.py
  - tests/unit/excel_writer/test_period_insertion.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/excel_writer/period_insertion.py
  - src/report_processor/excel_writer/row_annotations.py
  - src/report_processor/admin_panel
  - src/report_processor/calculation
  - src/report_processor/target_report
  - knowledge
  - docs
contract_versions:
  input: ExcelWriterEngine-15.1+ReconciliationPeriodInsertion-1.0
  output: ExcelWriterNamespaceLexeme-3.0
acceptance_commands:
  - nice -n 10 uv run --extra dev pytest -q tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/unit/excel_writer/test_row_annotations.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff check src/report_processor/excel_writer/ooxml.py src/report_processor/excel_writer/engine.py src/report_processor/excel_writer/formula_materialization.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff format --check src/report_processor/excel_writer/ooxml.py src/report_processor/excel_writer/engine.py src/report_processor/excel_writer/formula_materialization.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Namespace-aware writer v3: immutable, single-scan and resource-bounded

Accepted. Dual independent review returned `MERGE YES` for feature `d71b7f4`; the exact frozen
profile passed `159` tests on both the feature and main-based integration. The implementation binds
raw ZIP admission and later consumption to one descriptor, keeps source/candidate identities
through publication, rejects non-UTF-8 worksheet bytes and unsafe/ambiguous XML topology, and
preserves operation-specific controlled errors without workbook-derived details.

Continue from generated seed `251808c`, but do not integrate it directly. Retain the accepted
namespace-aware exact-QName edits, DTD/entity rejection, foreign-namespace isolation, formula value
attribute preservation and historical apply/restart bridge.

Replace the generic mutable element graph with frozen slotted cell/direct-child span records and a
`MappingProxyType` coordinate map. Retain only evidence needed by the writer: exact byte spans,
unqualified cell attributes, direct `f`/`v` spans and formula count. Count every SpreadsheetML cell,
including invalid/missing references, and validate stored references as bounded Excel A1 coordinates.
Reject non-UTF-8 worksheet declarations, excessive nesting and main-namespace `f`/`v` outside a
direct main-namespace cell. No global cache, mutable returned structure or retained workbook data
beyond the request.

Engine planning must build one index per worksheet part and bulk-inspect through it. Batch
replacement must consume the same immutable source index. Verification constructs expected bytes
from one source index and proves candidate equality plus existing package reopen; it must not parse
the candidate again. Generated 1,000-coordinate tests exercise the real `_build_write_plan` and
`verify_temp_package` paths and prove exactly one namespace scan per changed part in each path.

Use inclusive resource ceilings: 256 MiB input file, 4,096 archive entries, 256 MiB per member,
512 MiB aggregate inflated size, compression ratio 100, 128 MiB worksheet XML, 500,000 worksheet
cells, 2,100,000 element starts and nesting depth 64. Reject only values strictly above a ceiling.
The element budget admits the measured 500,000 one-cell-per-row formula topology (~2,000,002
starts); tests prove boundary and boundary+1 without constructing a private or oversized workbook.

Every `excel_writer` package path must validate file size and the same open `ZipFile` central
directory before `read()`, `open()` or `testzip()`: entry count, exact duplicate names, nonnegative
sizes, nonempty member with zero compressed size, member/aggregate/ratio limits, encryption and
signatures. Worksheet `ZipInfo.file_size` is checked before decompression. Formula coordinate and
LibreOffice recalculated-value reads use this validated same-handle API; resource failures map to
the operation's existing controlled error code and never include member names, sheet names,
coordinates, formulas or values. Spies must prove no read/testzip occurs before failed admission.

Preserve source immutability, no-clobber publication, exact unrelated archive-member bytes,
calculation-chain cleanup, formula materialization semantics and canonical service restart. Do not
modify target-report or row-annotation behavior in this wave; their separate readers remain a later
bounded compatibility audit.

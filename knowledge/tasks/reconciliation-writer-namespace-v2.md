---
type: orda_task
status: frozen
card_id: reconciliation-writer-namespace-v2
version: 2
work_id: reconciliation-writer-namespace-v2
task_id: writer-namespace-v2
purpose: Complete namespace-safe writing with one immutable worksheet index per part and bounded ZIP/XML resources.
role: developer
route: P5 -> developer / inherited runtime; reason: byte-offset XML parsing, archive safety and writer hot path.
launch_status: ready
card_path: knowledge/tasks/reconciliation-writer-namespace-v2.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: e5ef1f9c36b7b22874ee9d044b2d0a6f7571fe91
implementation_seed_sha: 669b64a8765a5678f7780d77486b91ba82ad1ccc
branch: codex/reconciliation-writer-namespace-v2
branch_base_sha_source: exact planning commit containing this card
write_scope:
  - src/report_processor/excel_writer/ooxml.py
  - src/report_processor/excel_writer/engine.py
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
  - knowledge
  - docs
contract_versions:
  input: ExcelWriterEngine-15.1+ReconciliationPeriodInsertion-1.0
  output: ExcelWriterNamespaceLexeme-2.0
acceptance_commands:
  - nice -n 10 uv run --extra dev pytest -q tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/unit/excel_writer/test_row_annotations.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff check src/report_processor/excel_writer/ooxml.py src/report_processor/excel_writer/engine.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff format --check src/report_processor/excel_writer/ooxml.py src/report_processor/excel_writer/engine.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Namespace-aware writer v2: indexed and bounded

Continue from the generated-test seed `669b64a`, but do not integrate it directly. Retain its
request-local Expat namespace expansion, exact QName edits, DTD/entity rejection, foreign-namespace
isolation and historical apply/restart bridges.

Replace the per-coordinate full worksheet parse with one request-local immutable index per worksheet
part. The writer plan and verifier must bulk-inspect all requested coordinates through that index;
batch replacement must reuse the same parsed evidence where safe. Do not add a global cache, retain
worksheet bytes beyond the request, or expose workbook-derived values. A generated 1,000-coordinate
regression must prove one namespace scan per part in plan validation and one in verification. The
accepted 0.7 MB/100-call reproduction must no longer scale linearly by reparsing the whole sheet.

Formula materialization must preserve the exact opening QName and every unrelated attribute when a
self-closing value node is expanded. Duplicate coordinates/value/formula nodes, nested numeric
markup, malformed XML, DTDs and entities fail closed with operation-specific writer errors.

Before decompression or full member reads, validate bounded central-directory facts: entry count,
per-member and aggregate uncompressed sizes, and compression ratio. Bound worksheet XML bytes and
parser element events independently. Limits must admit the repository's 500,000-cell target
contract while preventing unbounded allocation; tests exercise each boundary and a small highly
compressible synthetic worksheet. Do not log member contents, worksheet names, formulas or values.

Preserve the existing no-clobber publication, source immutability, exact unrelated archive-member
bytes, formula materialization contract, and generated historical service apply/restart proof.

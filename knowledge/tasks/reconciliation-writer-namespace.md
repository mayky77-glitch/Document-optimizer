---
type: orda_task
status: frozen
card_id: reconciliation-writer-namespace
version: 1
work_id: reconciliation-writer-namespace-v1
task_id: writer-namespace
purpose: Make the byte-preserving Excel writer accept legal SpreadsheetML namespace prefixes.
role: developer
route: P5 -> developer / inherited runtime; reason: byte-offset XML parsing and writer integrity.
launch_status: ready-after-service-review
card_path: knowledge/tasks/reconciliation-writer-namespace.md
card_commit_sha_source: exact planning commit containing this card
base_sha_source: 6d2bed7205e0f4b10acdae8394a9ce7b3d8a9ddb
branch: codex/reconciliation-writer-namespace
branch_base_sha_source: exact planning commit containing this card
write_scope:
  - src/report_processor/excel_writer/ooxml.py
  - tests/unit/excel_writer/test_ooxml.py
  - tests/unit/excel_writer/test_engine.py
  - tests/unit/excel_writer/test_period_insertion.py
  - tests/integration/test_reconciliation_authoritative_flow.py
forbidden_paths:
  - src/report_processor/excel_writer/period_insertion.py
  - src/report_processor/excel_writer/engine.py
  - src/report_processor/excel_writer/row_annotations.py
  - src/report_processor/admin_panel
  - src/report_processor/calculation
  - knowledge
  - docs
contract_versions:
  input: ExcelWriterEngine-15.1+ReconciliationPeriodInsertion-1.0
  output: ExcelWriterNamespaceLexeme-1.0
acceptance_commands:
  - nice -n 10 uv run --extra dev pytest -q tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_formula_materialization.py tests/unit/excel_writer/test_period_insertion.py tests/unit/excel_writer/test_row_annotations.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff check src/report_processor/excel_writer/ooxml.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - nice -n 10 uv run --extra dev ruff format --check src/report_processor/excel_writer/ooxml.py tests/unit/excel_writer/test_ooxml.py tests/unit/excel_writer/test_engine.py tests/unit/excel_writer/test_period_insertion.py tests/integration/test_reconciliation_authoritative_flow.py
  - git diff --check
---

# Namespace-aware worksheet lexemes

Historical period insertion is structurally correct but serializes worksheet elements with a legal
SpreadsheetML prefix such as `s:c`. The accepted byte-preserving writer currently recognizes only
unprefixed `c`, `f` and `v` elements, so a real actionable period apply fails closed before writing.

Implement a request-local, byte-offset worksheet scanner with stdlib Expat namespace expansion.
Recognize only the transitional SpreadsheetML namespace and exact local names while accepting a
default namespace or any legal prefix and ignoring foreign lookalikes. Do not mutate the global
ElementTree namespace registry and do not serialize the XML tree.

Update inspection, replacement, formula counting/coordinates, numeric formula extraction and
formula materialization. Preserve exact qualified names when expanding self-closing cells or value
nodes, replace only value-content/removal spans, validate unqualified cell attributes, and reject
malformed/ambiguous structures through existing controlled writer errors. All unrelated worksheet
bytes and archive members remain identical.

Generated tests must cover default, `s`, `ns0` and arbitrary prefixes; foreign lookalikes;
self-closing cells/values; formulas/materialization; concurrent distinct-prefix calls without global
namespace mutation; the real insertion-to-writer bridge; and a service-level historical actionable
apply followed by restart recovery. No private workbook data may enter tests or evidence.

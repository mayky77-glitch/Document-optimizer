---
type: task
status: done
work_id: doc-reconciliation-prd-2026-07-27
role: worker
agent_role: developer
owner: "developer"
profile: L1
routing_grade: P3
progress_revision: 2
state_fingerprint: "sha256:1ec5e6dad27260bc6d7b0bbec4c8be3a82020ab1ec9eac799a9fab1e5e34eab0"
no_progress_count: 0
circuit_state: closed
routing_reason: "Содержательная переработка нескольких связанных проектных документов после P6 FAIL-аудита"
luna_benchmark_evidence: ""
exception_evidence: ""
assigned_model: gpt-5.6-terra
reasoning_effort: medium
launch_status: confirmed
actual_model: gpt-5.6-terra
actual_reasoning_effort: medium
fallback_reason: ""
model_fallback: false
last_verified: 2026-07-28
updated: 2026-07-28
write_scope:
  - "docs/PRD.md"
  - "docs/BUSINESS_RULES.md"
  - "docs/ARCHITECTURE.md"
  - "docs/ROADMAP.md"
  - "knowledge/components/document-reconciliation.md"
  - "knowledge/INDEX.md"
  - "knowledge/maps/architecture.md"
  - "knowledge/DECISIONS.md"
  - "knowledge/tasks/remediate-plan-documents.md"
source_paths:
  - "knowledge/tasks/audit-plan-documents.md"
  - "knowledge/tasks/orchestrate-discovery-prd.md"
depends_on:
  - "audit-plan-documents"
tags:
  - "task/implementation"
  - "status/done"
  - "domain/document-reconciliation"
  - "risk/high"
links:
  - "[[../ORCHESTRATION|Orchestration]]"
---

# Исправление плановых документов после P6-аудита

## Goal

Устранить все findings аудита и подготовить полное глобальное ТЗ, пригодное для передачи оркестратору, без реализации кода.

## Scope and instructions

- Изменять только `write_scope`.
- Не менять Excel, код и runtime-конфигурацию.
- Исправить определения Таблиц 1/2 и сохранить все 14 пользовательских правил отдельно.
- Описать Gate 0, детерминированные расчёты, UX проверки, экспорт, GPT trust boundary и CodeGraph gate.
- Добавить версионируемую память обратной связи: решения пользователя становятся контекстными правилами, но не автоматическим дообучением модели.
- Дать roadmap с ролями, P-маршрутами, непересекающимися write scopes, зависимостями, deliverables, tests и gates.

## Completion evidence

- Changed paths: `docs/PRD.md`, `docs/BUSINESS_RULES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `knowledge/components/document-reconciliation.md`, `knowledge/INDEX.md`, `knowledge/maps/architecture.md`, `knowledge/DECISIONS.md`, this card.
- Checks: exact-phrase requirement search; roadmap ownership inspection; Markdown structural inspection; knowledge validator (global result is recorded after run).
- Result: remediation revision 2 addresses the re-audit findings: exclusive roadmap ownership, M04/M05 candidate-only contract, content-proven stage, exact two upload zones, explicit CLI inputs and month/current-period preservation.
- Risks: this card is in review, not PASS. No implementation is authorised before owner approves every Gate 0 decision. M02/M06 literals are fixed; M04/M05 include sets, M13/M14, suffix/supporting-work and month semantics remain unresolved.

## Handoff

Final independent P6 re-audit revision 3 passed; task closed as `done`.

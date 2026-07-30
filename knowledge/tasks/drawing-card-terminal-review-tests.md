---
type: task
card_id: drawing-card-terminal-review-tests
status: frozen
version: 1
supersedes: null
work_id: drawing-card-terminal-review
task_id: terminal-review-tests
purpose: "Проверить массовые и поштучные решения terminal review"
role: worker
agent_role: tester
profile: L1
routing_grade: P3
routing_reason: "Independent deterministic CLI and review-contract verification."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
card_path: knowledge/tasks/drawing-card-terminal-review-tests.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-terminal-review-tests
worktree: "/Users/x/Documents/Сооотношение документов/report-processor-drawing-card-tests"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - report_processor_drawing_card_cli/tests
forbidden_paths:
  - report_processor_drawing_card_cli/src
  - report_processor_drawing_card_cli/docs
  - report_processor_drawing_card_cli/pyproject.toml
  - report_processor_drawing_card_cli/uv.lock
  - knowledge
  - "**/*.xlsx"
  - "**/*.xlsb"
contract_versions:
  input: WorkflowResult-0.9.1
  output: ReviewApprovalJSON-0.9.1
acceptance_commands:
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m ruff check tests"
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m ruff format --check tests"
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m pytest -q tests"
---

# Terminal review tests

Добавить unit-тесты для четырёх верхнеуровневых действий, поштучного
approve/reject, выбора категории при отсутствии предложения, быстрых решений
для оставшихся строк, повторного запроса при неверном вводе и cancel без
публикации. Проверить round-trip JSON существующим импортёром.

Добавить тест ограниченного агрегированного вывода warnings и интеграционный
тест повторного workflow после решения. Исправить четыре исходные ошибки
сортировки импортов в существующих тестах, не меняя их поведение.

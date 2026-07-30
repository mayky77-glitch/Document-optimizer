---
type: task
card_id: drawing-card-terminal-review-production
status: done
version: 1
supersedes: null
work_id: drawing-card-terminal-review
task_id: terminal-review-production
purpose: "Реализовать интерактивное подтверждение спорных строк и повторный выпуск карточки"
role: worker
agent_role: developer
profile: L1
routing_grade: P3
routing_reason: "Bounded CLI implementation over the existing review JSON contract."
assigned_model: gpt-5.6-terra
reasoning_effort: medium
card_path: knowledge/tasks/drawing-card-terminal-review-production.md
card_commit_sha_ref: launch-envelope
base_sha_ref: card_commit_sha_ref
dependency_shas: []
branch: codex/drawing-card-terminal-review-production
worktree: "/Users/x/Documents/Сооотношение документов/report-processor-drawing-card-production"
branch_base_sha_ref: card_commit_sha_ref
write_scope:
  - report_processor_drawing_card_cli/src/report_processor/cli.py
  - report_processor_drawing_card_cli/src/report_processor/terminal_ui.py
  - report_processor_drawing_card_cli/src/report_processor/terminal_review.py
forbidden_paths:
  - report_processor_drawing_card_cli/tests
  - report_processor_drawing_card_cli/src/report_processor/drawing_card
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
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m ruff check src/report_processor/cli.py src/report_processor/terminal_ui.py src/report_processor/terminal_review.py"
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m ruff format --check src/report_processor/cli.py src/report_processor/terminal_ui.py src/report_processor/terminal_review.py"
  - "/Users/x/Downloads/report_processor_drawing_card_cli/.venv/bin/python -m compileall -q src/report_processor"
---

# Terminal review production

Добавить opt-in флаг интерактивного review для встроенного terminal UI.
После строгой блокировки показать четыре действия: отклонить все спорные строки,
одобрить доступные предложения, решить строки по одной или отменить выпуск.

Для строки показать объект, файл/лист/номер, шифр, работу, единицу, количество,
стоимость, предложенную категорию и причину. Одобрение без категории запрещено:
пользователь выбирает одну из восьми категорий. Поддержать быстрые команды для
оставшихся строк. Решения атомарно сохранить в JSON-аудит и выполнить ровно один
повторный workflow. Оставшиеся blockers не скрывать; частичный выпуск требовать
отдельного подтверждения. Обычный CLI без opt-in не должен запрашивать ввод.

Вывод предупреждений агрегировать по кодам и ограничить, не печатать десятки
тысяч повторов.

## Результат

- Feature commit: `ed3a475b5a3861171cc978b73e5166be9a7a5cbb`.
- Integration commit: `7458cc8f58b3ed2fa5276214a29ebb3f21c32c38`.
- Интерактивный review, атомарный JSON и один повторный workflow реализованы.

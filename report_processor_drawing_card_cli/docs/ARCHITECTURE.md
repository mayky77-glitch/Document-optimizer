# Архитектура

```text
Inputs
→ Manifest
→ metadata preselection
→ WorkbookReader (OpenXML XML-stream / XLSB pyxlsb)
→ SourceSchema
→ DrawingSourceRow
→ Deterministic Rules
→ Confirmed Dictionary
→ Lexical Retrieval
→ Tiny Model suggestion
→ Manual Review
→ Quantity/Cost Aggregation
→ Layout Planner
→ Template Writer
→ Output Validation
→ Audit
```

## Границы ответственности

- `sources/` не выполняет бизнес-классификацию;
- `matching/` не читает Excel и не агрегирует числа;
- `aggregation/` не выбирает файлы и не пишет Excel;
- `output/` получает только готовые строки карточки;
- `workflow.py` связывает компоненты и создаёт аудит;
- `cli.py` только проверяет аргументы и вызывает workflow.

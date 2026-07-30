# Руководство CLI и терминального меню

## 1. Установка на macOS

```bash
cd ~/Downloads/report_processor_drawing_card_cli
bash scripts/setup_mac_linux.sh
```

Скрипт создаёт `.venv`, устанавливает зависимости и выводит справку.

## 2. Пошаговый интерфейс

Запустите:

```bash
source .venv/bin/activate
python run_cli.py
```

Или:

```bash
./start.command
```

Меню содержит:

```text
1. Создать итоговую карточку
2. Дополнить существующую карточку
3. Безопасный dry-run без записи карточки
4. Проверить и описать источники
5. Подготовить файл ручной проверки
6. Импортировать заполненную ручную проверку
7. Проверить готовую карточку
0. Выход
```

Путь к ZIP, папке, карточке или Excel можно перетащить мышью в окно Terminal. Кавычки и экранированные пробелы удаляются автоматически.

## 3. Первый рабочий запуск

### Шаг 1 — инспекция

Выберите пункт 4, затем ZIP или папку. В терминале будут показаны:

- определённый индекс объекта;
- подходящий лист;
- найденные логические колонки;
- источники, требующие внимания.

Подробный JSON сохраняется в `output/source_inspection.json`.

### Шаг 2 — dry-run

Выберите пункт 3. Рекомендуемые ответы:

```text
Период: 2026-07
RAG: off — устанавливается меню автоматически
Строгая проверка: Да
Шаблон: templates/default_drawing_card_template.xlsx
```

Итоговый Excel не создаётся. Аудит появится в `work/<run_id>/`.

### Шаг 3 — проверка review

Основные артефакты:

```text
processing_summary.json
source_selections.json
extracted_rows.jsonl
classification_decisions.jsonl
aggregated_results.jsonl
manual_review.xlsx
layout_plan.json
source_hashes_before.json
source_hashes_after.json
```

`manual_review.xlsx` теперь проходит внутреннюю ZIP/XML-проверку и повторное открытие. В столбце «Решение пользователя» доступен список:

```text
approve
reject
change_category
quantity_only
cost_only
skip
```

### Шаг 4 — создание карточки

Выберите пункт 1. В поле сохранения можно указать полный путь к `.xlsx` **или существующую папку**. При выборе папки программа автоматически добавит имя `карточка_остатков.xlsx`.

Результат по умолчанию:

```text
output/карточка_остатков.xlsx
```

### Шаг 5 — валидация

Выберите пункт 7 и перетащите созданную карточку. Отчёт сохранится в `output/card_validation.json`.

## 4. Ручные команды без меню

### Инспекция ZIP

Одной строкой:

```bash
python run_cli.py inspect-drawing-sources --archive "/путь/данные.zip" --output output/source_inspection.json
```

### Dry-run

```bash
python run_cli.py build-drawing-card --archive "/путь/данные.zip" --period 2026-07 --template templates/default_drawing_card_template.xlsx --mode create --rag-mode off --strict --dry-run --work-dir work
```

### Создание

```bash
python run_cli.py build-drawing-card --archive "/путь/данные.zip" --period 2026-07 --template templates/default_drawing_card_template.xlsx --output output/карточка_остатков.xlsx --mode create --rag-mode off --strict --work-dir work
```

### Явно выбранные файлы

```bash
python run_cli.py build-drawing-card --inputs "/data/0906.xlsx" "/data/0907.xlsb" --template templates/default_drawing_card_template.xlsx --output output/result.xlsx --mode create --rag-mode off --strict --work-dir work
```

### Обновление существующей карточки

```bash
python run_cli.py build-drawing-card --inputs "/data/new.xlsx" --existing-card output/карточка_остатков.xlsx --output output/карточка_остатков_обновленная.xlsx --mode update --update-policy fill_empty_only --rag-mode off --strict --work-dir work
```

Политики:

- `fill_empty_only` — заполняет только пустые значения;
- `overwrite` — приоритет новым непустым значениям;
- `keep_existing` — сохраняет существующие;
- `conflicts_to_review` — конфликт не перезаписывается молча.

### Импорт review

```bash
python run_cli.py apply-drawing-review --review "/путь/manual_review.xlsx" --output output/review_decisions.json
```

Повторный запуск с решениями:

```bash
python run_cli.py build-drawing-card --archive "/путь/данные.zip" --template templates/default_drawing_card_template.xlsx --output output/result_after_review.xlsx --review-decisions output/review_decisions.json --mode create --rag-mode off --strict --work-dir work
```

## 5. Почему раньше команды распадались

В zsh перенос строки работает только так:

```bash
команда \
  --параметр значение \
  --следующий значение
```

После `\` нельзя ставить пробелы или пустую строку. Иначе первая часть запускается отдельно, а zsh сообщает:

```text
zsh: command not found: --archive
```

Терминальное меню полностью устраняет эту проблему.

## 6. Правила безопасности

- Не задавайте одинаковые входной и выходной пути.
- Сначала используйте dry-run и `--strict`.
- При нескольких равноценных источниках передавайте проверенные файлы через `--inputs`.
- Пустое значение не равно нулю.
- Несовместимые единицы не суммируются.
- Неподтверждённые решения не записываются автоматически.
- Храните папку `work/<run_id>` вместе с результатом.
## 7. Новые проверки версии 0.9.0

Команда `validate-drawing-card` возвращает ошибку, если обнаружены:

- массовое совпадение ненулевых значений количества и стоимости;
- `м`, `щ`, `пес` или другой служебный маркер вместо шифра;
- бинарный числовой хвост в XML выходных quantity/cost-ячеек;
- неполный восьмистрочный блок или отсутствующее объединение заголовка.

При любой такой ошибке карточку нельзя использовать как окончательную.

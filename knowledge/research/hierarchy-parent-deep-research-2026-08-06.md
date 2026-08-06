
<!-- deep-research:managed:start -->
# Как безопасно определять родительские и ресурсные строки в КС-6а

- Research ID: `hierarchy-parent-deep-research-2026-08-06`
- Slug: `hierarchy-parent-deep-research-2026-08-06`
- As of: 2026-08-06T09:30:00+08:00
- Updated: 2026-08-06

## Overview
- Основной блокер был ошибкой schema detection, а не реальной проблемой 3 263 родительских итогов.
- Синтаксического parent-child недостаточно: некоторые non-leaf строки — реальные измеряемые работы, а их дочерние строки — материалы.
- Сверка сумм полезна как диагностика, но не должна ни определять role, ни блокировать карточку.
- После исправлений очередь состоит из 6 реальных review-строк; ложные карточки оборудования и «шт/шт не совпадает» удалены.

## Implications
- Распознавать «№ п/п» явно; content fallback не рассматривает fractional numerics, error/check, quantity и cost columns.
- Исключать section aggregate; кодированную work-строку с дочерними resources оставлять, resources исключать до matcher.
- Duplicate positions не скрывать молча: сохранять и отражать в аудите/отчёте.
- Cost reconciliation считать по measured descendants и показывать как non-blocking diagnostic, не как финансовое автоподтверждение.
- Exact feedback quantity повторно валидировать по текущей category-unit policy.

## Confidence and gaps
- Нет ручной ground-truth разметки всех типов строк; вывод о cost-type code подтверждён на четырёх загруженных книгах, но другие форматы могут потребовать отдельной policy.
- Число 6 относится к текущим source files, rules, feedback и machine-consensus на 2026-08-06.
- Внутренние файлы частные; публичные URL намеренно не использовались.

## Full reports
- Markdown: [report.md](../../research/hierarchy-parent-deep-research-2026-08-06/report.md)
- HTML: [report.html](../../research/hierarchy-parent-deep-research-2026-08-06/report.html)

## Significant updates
<!-- deep-research:history:start -->
- 2026-08-06: created from validated research report. <!-- deep-research:fingerprint:d5a112303dc6 -->
<!-- deep-research:history:end -->
<!-- deep-research:managed:end -->

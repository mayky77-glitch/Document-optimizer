"""Controlled, path-free presentation contract for drawing-card jobs."""

from __future__ import annotations

from collections.abc import Mapping

from report_processor.drawing_card.models import CATEGORY_DISPLAY_NAMES, CATEGORY_ORDER

from .drawing_card_service import DrawingCardJob

_ISSUE_TEXT: dict[str, tuple[str, str | None]] = {
    "MANUAL_REVIEW_REQUIRED": (
        "Есть строки, для которых нужно решение пользователя.",
        "Откройте шаг проверки и примените решение к каждой группе.",
    ),
    "UNIT_MISMATCH": (
        "В одну итоговую позицию попали разные единицы измерения.",
        "В ручной проверке оставьте количество только для совместимой единицы.",
    ),
    "FORMULA_NOT_AVAILABLE_FOR_BACKEND": (
        "В XLSB недоступен текст формул, но сохранённые Excel-значения прочитаны.",
        None,
    ),
    "FORMULA_WITHOUT_CACHED_VALUE": (
        "Формула не содержит сохранённого результа, поэтому число нельзя безопасно использовать.",
        "Откройте исходный файл в Excel, пересчитайте и сохраните его.",
    ),
    "HIERARCHY_COST_MISMATCH": (
        "Контрольная сумма секции не совпадает с суммой её измеряемых строк. "
        "Это диагностика и сама по себе не блокирует карточку.",
        "Проверьте суммы, если они используются для финансовой сверки.",
    ),
    "HIERARCHY_MISSING_DIRECT_CHILD_COST": (
        "У секции или одной из её измеряемых строк нет стоимости для контрольной сверки. "
        "Это не блокирует карточку.",
        "Заполните стоимость или исправьте иерархию в исходном документе.",
    ),
    "HIERARCHY_DUPLICATE_POSITION": (
        "Один и тот же номер позиции встречается несколько раз. "
        "Эти строки не скрываются по иерархии "
        "и обрабатываются как отдельные.",
        "Уточните нумерацию, если повторы не задуманы в исходном документе.",
    ),
    "HIERARCHY_POSITION_GAP": (
        "В нумерации позиций есть пропуск; это диагностика и сама по себе не блокирует карточку.",
        None,
    ),
    "POSSIBLE_DUPLICATE": (
        "Найдены вероятные дубли; повторные суммы не добавлялись.",
        "Проверьте исключённые дубли в отчёте.",
    ),
    "POSITION_COLUMN_FROM_CONTENT_DIAGNOSTIC": (
        "Похоже, в файле есть колонка номера позиции, но её заголовок не распознан.",
        "Уточните заголовок колонки. Строки не скрывались по этой предполагаемой иерархии.",
    ),
    "IGNORED_NON_DRAWING_CELL": (
        "Ячейки без признаков строки чертежа не включались в карточку.",
        None,
    ),
    "BINARY_FLOAT_ARTIFACT_NORMALIZED": (
        "Технические хвосты двоичных чисел нормализованы без изменения сумм.",
        None,
    ),
    "AMBIGUOUS_COLUMN": (
        "Для одного из полей найдено несколько похожих колонок.",
        "Проверьте заголовки колонок в исходном файле.",
    ),
    "SUSPICIOUS_QUANTITY_COST_PAIR": (
        "Найдено нетипичное сочетание количества и стоимости.",
        "Проверьте эту строку в отчёте.",
    ),
    "METRIC_COLUMNS_REPLACED": (
        "Колонки количества и стоимости уточнены по структуре данных.",
        None,
    ),
    "DRAWING_CODE_NOT_FOUND": (
        "Для части строк не найден шифр чертежа; эти строки не попали в карточку.",
        "Проверьте шифры чертежей в исходных строках.",
    ),
    "NO_CARD_ROWS": (
        "Не найдено строк, которые можно безопасно включить в карточку.",
        "Проверьте шифры чертежей, категории работ и обязательные поля в исходных файлах.",
    ),
    "OUTPUT_BASE_MISSING": (
        "Не найден шаблон или существующая карточка для записи результата.",
        "Проверьте комплект установки или загрузите существующую карточку повторно.",
    ),
    "INVALID_NUMBER": (
        "Часть числовых ячеек не удалось распознать.",
        "Проверьте формат количеств и стоимостей в исходном Excel-файле.",
    ),
    "SOURCE_INSPECTION_FAILED": (
        "Один из исходных файлов не удалось проверить.",
        "Откройте файл в Excel, пересохраните и загрузите его снова.",
    ),
    "SOURCE_EXTRACTION_FAILED": (
        "Из одного из исходных файлов не удалось извлечь строки.",
        "Проверьте целостность книги и её листов, затем загрузите снова.",
    ),
    "SOURCE_HASH_CHANGED": (
        "Исходный файл изменился во время обработки.",
        "Загрузите актуальные файлы ещё раз.",
    ),
    "PROCESSING_FAILED": (
        "Обработка завершилась технической ошибкой.",
        "Повторите запуск; если ошибка повторится, сохраните время запуска для диагностики.",
    ),
    "PERSISTENCE_FAILED": (
        "Локальная панель не смогла надёжно сохранить состояние задачи.",
        "Не закрывайте исходные файлы и повторите действие "
        "после проверки свободного места на диске.",
    ),
    "CANCELLED": (
        "Обработка отменена пользователем; частичный результат не опубликован.",
        "При необходимости запустите эту задачу повторно.",
    ),
    "WORKFLOW_BLOCKED": (
        "Карточка не прошла обязательные проверки безопасности.",
        "Исправьте указанные причины в исходных файлах и запустите обработку снова.",
    ),
    "REQUEST_VALIDATION_FAILED": (
        "Параметры запуска или выбранные файлы не прошли проверку.",
        "Проверьте формат файлов и выбранную операцию.",
    ),
    "FUNNEL_CONSERVATION_FAILED": (
        "Не удалось однозначно объяснить судьбу каждой извлечённой строки.",
        "Выпуск остановлен: проверьте аудит исключений и повторите обработку.",
    ),
    "FUNNEL_UNKNOWN_ROLE_POLICY": (
        "Обнаружена строка с ролью, для которой нет подтверждённого правила.",
        "Уточните структуру исходного листа или заголовки колонок.",
    ),
    "FUNNEL_ANOMALOUS_EXCLUSION_SHARE": (
        "Необычно большая доля строк была исключена по структуре документа.",
        "Выпуск остановлен, чтобы неизвестный формат не скрыл данные.",
    ),
}


def drawing_card_job_payload(job: DrawingCardJob) -> dict[str, object]:
    """Return only values safe to serialize through an admin endpoint."""
    review_required = job.status == "review_required"
    phase = str(getattr(job, "phase", "upload"))
    processed_files = int(getattr(job, "processed_files", 0))
    total_files = getattr(job, "total_files", None)
    processed_rows = int(getattr(job, "processed_rows", 0))
    total_rows = getattr(job, "total_rows", None)
    source_files = job.summary.get("source_files")
    if source_files is None:
        source_files = len(job.sources)
    issues = _job_issues(job)
    return {
        "job_id": job.job_id,
        "status": job.status,
        "phase": phase,
        "progress": {
            "processed_files": processed_files,
            "total_files": int(total_files) if total_files is not None else None,
            "processed_rows": processed_rows,
            "total_rows": int(total_rows) if total_rows is not None else None,
        },
        "started_at": getattr(job, "started_at", None),
        "updated_at": getattr(job, "updated_at", None),
        "terminal_cause": getattr(job, "terminal_cause", None),
        "attempt": int(getattr(job, "attempt", getattr(job, "run_count", 0))),
        "can_cancel": job.status in {"queued", "processing"},
        "can_retry": job.status in {"cancelled", "failed", "blocked"},
        "mode": job.mode,
        "period": job.period,
        "active_step": (
            "review" if review_required else "card" if job.result_available else "sources"
        ),
        "summary": {
            "source_files": int(source_files),
            "extracted_rows": int(job.summary.get("extracted_rows", 0)),
            "card_rows": int(job.summary.get("card_rows", 0)),
            "manual_review": int(job.summary.get("manual_review", 0)),
        },
        "funnel": dict(job.funnel),
        "schema_recognition": [dict(item) for item in job.schema_recognition],
        "exclusion_audit_url": (
            f"/api/drawing-card/jobs/{job.job_id}/audit/exclusions"
            if job.exclusion_audit is not None
            else None
        ),
        "warnings": list(job.warnings),
        "issues": issues,
        "blocking_reasons": [item for item in issues if item["blocking"]],
        "result_url": (
            f"/api/drawing-card/jobs/{job.job_id}/result" if job.result_available else None
        ),
        "review_url": f"/api/drawing-card/jobs/{job.job_id}/review" if review_required else None,
        "can_upload_review": review_required,
    }


def _job_issues(job: DrawingCardJob) -> list[dict[str, object]]:
    codes = list(dict.fromkeys((*job.blockers, *job.warnings, *job.errors)))
    if job.blockers:
        codes = [code for code in codes if code != "WORKFLOW_BLOCKED"]
    issues = []
    for code in codes[:50]:
        message, action = _ISSUE_TEXT.get(
            code,
            (f"Диагностика обработки: {code}.", None),
        )
        issues.append(
            {
                "code": code,
                "message": message,
                "action": action,
                "count": int(job.blocker_counts.get(code, job.warning_counts.get(code, 1))),
                "blocking": code in job.blockers or code in job.errors,
            }
        )
    return issues


def drawing_card_inline_review_payload(job: DrawingCardJob) -> dict[str, object]:
    """Return endpoint metadata without widening the stable job payload."""
    review_required = job.status == "review_required"
    return {
        "review_url": (
            f"/api/drawing-card/jobs/{job.job_id}/review/items" if review_required else None
        ),
        "can_apply": review_required and set(job.review_items) == set(job.inline_approvals),
    }


def drawing_card_category_options(job: DrawingCardJob) -> list[dict[str, str | None]]:
    """Return controlled category choices for the inline-review selector."""
    return [
        {
            "value": category.value,
            "label": CATEGORY_DISPLAY_NAMES[category],
            "target_unit": _first_category_unit(job.category_units, category.value),
        }
        for category in CATEGORY_ORDER
    ]


def drawing_card_inline_review_page(
    payload: Mapping[str, object], job: DrawingCardJob
) -> dict[str, object]:
    """Translate legacy row review data into the controlled public contract."""
    action_states = {
        "approve": "approved",
        "reject": "rejected",
        "cost_only": "cost_only",
        "change_category": "change_category",
        "quantity_only": "approved",
        "skip": "rejected",
    }
    categories = drawing_card_category_options(job)
    category_options = {str(item["value"]): item for item in categories}
    public_items = []
    for raw in payload.get("items", ()):
        if not isinstance(raw, Mapping):
            continue
        decision = raw.get("решение")
        action = decision.get("action") if isinstance(decision, Mapping) else None
        selected_category = decision.get("category") if isinstance(decision, Mapping) else None
        selected_option = category_options.get(str(selected_category))
        public_items.append(
            {
                "review_id": raw.get("review_id"),
                "work_name": raw.get("наименование"),
                "category": raw.get("предлагаемая_категория_id"),
                "category_label": raw.get("предлагаемая_категория_рус"),
                "proposed_category": raw.get("предлагаемая_категория_id"),
                "proposed_category_label": raw.get("предлагаемая_категория_рус"),
                "selected_category": selected_category,
                "selected_category_label": (
                    selected_option.get("label") if selected_option is not None else None
                ),
                "quantity": raw.get("количество"),
                "source_unit": raw.get("source_unit"),
                "target_unit": raw.get("target_unit"),
                "total_cost": raw.get("стоимость"),
                "confidence": raw.get("confidence"),
                "decision": action_states.get(str(action), "pending"),
            }
        )
    total = int(payload.get("total", len(public_items)))
    unresolved = int(payload.get("unresolved_count", total))
    return {
        "items": public_items,
        "page": payload.get("page", 1),
        "page_size": payload.get("page_size", 50),
        "total": total,
        "unresolved_count": unresolved,
        "can_apply": payload.get("can_apply", False),
        "categories": categories,
        "summary": {
            "Строк для проверки": total,
            "Осталось решений": unresolved,
        },
    }


def drawing_card_cluster_review_page(payload: Mapping[str, object]) -> dict[str, object]:
    """Expose both names during the additive transition to the cluster UI."""
    items = [_safe_packet(item) for item in payload.get("items", ()) if isinstance(item, Mapping)]
    categories = _review_categories(payload.get("review_categories"))
    total_packets = int(payload.get("total_packets", payload.get("total_clusters", 0)))
    unresolved_packets = int(
        payload.get("unresolved_packets", payload.get("unresolved_clusters", 0))
    )
    return {
        "items": items,
        "clusters": items,
        "packets": items,
        "page": payload.get("page", 1),
        "page_size": payload.get("page_size", 50),
        "total_clusters": total_packets,
        "total_packets": total_packets,
        "total_rows": payload.get("total_rows", 0),
        "unresolved_clusters": unresolved_packets,
        "unresolved_packets": unresolved_packets,
        "unresolved_rows": payload.get("unresolved_rows", 0),
        "can_apply": bool(payload.get("can_apply", False)),
        "review_categories": categories,
        "review_metrics": _primitive_mapping(payload.get("review_metrics")),
    }


def _review_categories(value: object) -> list[dict[str, object]]:
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            category_id = item.get("id", item.get("value"))
            label = item.get("label")
            units = item.get("units", ())
            if isinstance(category_id, str) and isinstance(label, str):
                result.append(
                    {
                        "id": category_id,
                        "label": label,
                        "units": [unit for unit in units if isinstance(unit, str)],
                    }
                )
        return result
    return [
        {
            "id": category.value,
            "label": CATEGORY_DISPLAY_NAMES[category],
            "units": [],
        }
        for category in CATEGORY_ORDER
    ]


def _primitive_mapping(value: object) -> dict[str, int | float | str | bool | None]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(item, (str, int, float, bool)) or item is None
    }


def _safe_packet(value: Mapping[str, object]) -> dict[str, object]:
    """Keep presentation additive while never forwarding private source metadata."""
    allowed = {
        "cluster_id",
        "packet_id",
        "version",
        "work_name",
        "source_unit",
        "target_unit",
        "member_count",
        "aggregate_total_cost",
        "proposed_category",
        "proposed_category_label",
        "selected_category",
        "selected_category_label",
        "confidence",
        "reason",
        "reason_label",
        "confidence_explanation",
        "packet_eligible",
        "singleton",
        "hazard",
        "match_mode",
        "unit_compatibility",
        "rules_version",
        "controlled_differences",
        "decision",
    }
    packet = {key: value[key] for key in allowed if key in value}
    members = value.get("members", ())
    packet["members"] = [
        _safe_packet_member(member) for member in members if isinstance(member, Mapping)
    ]
    return packet


def _safe_packet_member(value: Mapping[str, object]) -> dict[str, object]:
    allowed = (
        "review_id",
        "version",
        "safe_filename",
        "sheet_name",
        "row_number",
        "position",
        "drawing_code",
        "object_index",
        "work_name",
        "source_unit",
        "quantity",
        "total_cost",
        "confidence",
        "reason",
        "reason_label",
        "selected_category",
    )
    member = {key: value[key] for key in allowed if key in value}
    filename = member.get("safe_filename")
    if isinstance(filename, str):
        member["safe_filename"] = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return member


def _first_category_unit(category_units: dict[str, tuple[str, ...]], category: str) -> str | None:
    units = category_units.get(category, ())
    return units[0] if units else None

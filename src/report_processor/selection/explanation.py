from __future__ import annotations

from collections import Counter

from report_processor.selection.models import SourceCandidate, SourceSelectionResult


def build_selection_explanation(
    result: SourceSelectionResult,
) -> tuple[str, ...]:
    if result.selected is not None:
        return _successful_explanation(result.selected)
    if result.status == "MULTIPLE_TOP_CANDIDATES":
        return _ambiguity_explanation(result.candidates)
    if result.rejected:
        reason_counts = Counter(
            reason for candidate in result.rejected for reason in candidate.rejection_reasons
        )
        lines = [f"Источник не выбран: статус {result.status}."]
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"{reason}: отклонено файлов — {count}.")
        return tuple(lines)
    return (f"Источник не выбран: статус {result.status}.",)


def _successful_explanation(candidate: SourceCandidate) -> tuple[str, ...]:
    lines = [f"Выбран файл: {candidate.entry.filename}"]
    lines.extend(component.explanation for component in candidate.score_components)
    if not any(
        (
            candidate.entry.is_probable_copy,
            candidate.entry.is_draft,
            candidate.entry.is_probably_outdated,
        )
    ):
        lines.append("Файл не является копией, черновиком или устаревшим документом.")
    for warning in candidate.warnings:
        lines.append(f"Предупреждение: {warning}.")
    return tuple(lines)


def _ambiguity_explanation(candidates: tuple[SourceCandidate, ...]) -> tuple[str, ...]:
    if not candidates:
        return ("Найдены равноценные кандидаты; автоматический выбор запрещён.",)
    top = candidates[0]
    equal = [candidate for candidate in candidates if candidate.score == top.score]
    lines = [f"Найдено равноценных файлов: {len(equal)}."]
    entry = top.entry
    if entry.document_index is not None:
        lines.append(f"Индекс совпадает: {entry.document_index.normalized}.")
    if entry.document_period is not None:
        lines.append(f"Период совпадает: {entry.document_period.normalized}.")
    revision = entry.document_revision
    revision_text = (
        f" и редакцию {revision.number}" if revision and revision.number is not None else ""
    )
    lines.append(f"Кандидаты имеют тип {entry.document_type}{revision_text}.")
    lines.append("Различия только технические; автоматический выбор запрещён.")
    return tuple(lines)

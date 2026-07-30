from __future__ import annotations

from dataclasses import replace

from report_processor.selection.models import (
    ScoreComponent,
    SourceCandidate,
    SourceScoringConfig,
    SourceSelectionRequest,
)


def score_source_candidate(
    candidate: SourceCandidate,
    request: SourceSelectionRequest,
    config: SourceScoringConfig,
) -> SourceCandidate:
    if not candidate.accepted:
        return candidate
    components: list[ScoreComponent] = [
        ScoreComponent(
            code="EXACT_INDEX_MATCH",
            points=config.exact_index_match,
            explanation=(f"Индекс полностью совпал: {request.target_index.normalized}."),
        )
    ]
    warnings: list[str] = []
    _add_period_component(components, warnings, candidate, request, config)
    _add_type_component(components, candidate, request, config)
    _add_revision_components(components, warnings, candidate, config)
    _add_file_status_components(components, candidate, config)
    return replace(
        candidate,
        score=sum(component.points for component in components),
        score_components=tuple(components),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def score_source_candidates(
    candidates: tuple[SourceCandidate, ...],
    request: SourceSelectionRequest,
    config: SourceScoringConfig,
) -> tuple[SourceCandidate, ...]:
    return tuple(score_source_candidate(candidate, request, config) for candidate in candidates)


def preferred_type_points(candidate: SourceCandidate) -> int:
    return sum(
        component.points
        for component in candidate.score_components
        if component.code == "PREFERRED_DOCUMENT_TYPE"
    )


def has_exact_period_component(candidate: SourceCandidate) -> bool:
    return any(component.code == "EXACT_PERIOD_MATCH" for component in candidate.score_components)


def _add_period_component(
    components: list[ScoreComponent],
    warnings: list[str],
    candidate: SourceCandidate,
    request: SourceSelectionRequest,
    config: SourceScoringConfig,
) -> None:
    target = request.target_period
    if target is None:
        return
    actual = candidate.entry.document_period
    if actual == target:
        components.append(
            ScoreComponent(
                code="EXACT_PERIOD_MATCH",
                points=config.exact_period_match,
                explanation=f"Период полностью совпал: {target.normalized}.",
            )
        )
    elif actual is None:
        components.append(
            ScoreComponent(
                code="UNKNOWN_PERIOD",
                points=config.unknown_period,
                explanation="Период файла не определён.",
            )
        )
        warnings.append("UNKNOWN_PERIOD")
    else:
        components.append(
            ScoreComponent(
                code="PERIOD_MISMATCH",
                points=config.period_mismatch,
                explanation=(
                    f"Период файла {actual.normalized} отличается от "
                    f"запрошенного {target.normalized}."
                ),
            )
        )
        warnings.append("PERIOD_MISMATCH")


def _add_type_component(
    components: list[ScoreComponent],
    candidate: SourceCandidate,
    request: SourceSelectionRequest,
    config: SourceScoringConfig,
) -> None:
    document_type = candidate.entry.document_type.lower()
    try:
        position = request.preferred_document_types.index(document_type)
    except ValueError:
        components.append(
            ScoreComponent(
                code="ALLOWED_DOCUMENT_TYPE",
                points=0,
                explanation=f"Тип {document_type} разрешён, но не имеет приоритета.",
            )
        )
        return
    points = max(config.preferred_type_first - position * config.preferred_type_step, 0)
    components.append(
        ScoreComponent(
            code="PREFERRED_DOCUMENT_TYPE",
            points=points,
            explanation=f"Тип {document_type} имеет приоритет №{position + 1}.",
        )
    )


def _add_revision_components(
    components: list[ScoreComponent],
    warnings: list[str],
    candidate: SourceCandidate,
    config: SourceScoringConfig,
) -> None:
    revision = candidate.entry.document_revision
    if revision is None:
        return
    if revision.number is not None:
        raw_points = revision.number * config.numeric_revision_step
        points = min(raw_points, config.numeric_revision_max_bonus)
        explanation = f"Указана числовая редакция {revision.number}."
        if points != raw_points:
            explanation += f" Бонус ограничен значением {points}."
        components.append(
            ScoreComponent(
                code="NUMERIC_REVISION",
                points=points,
                explanation=explanation,
            )
        )
    conflict = revision.is_draft and (revision.is_final or revision.is_approved)
    if conflict:
        warnings.append("CONFLICTING_VERSION_MARKERS")
        return
    if revision.is_final:
        components.append(
            ScoreComponent(
                code="FINAL_VERSION",
                points=config.final_version,
                explanation="Файл помечен как финальный.",
            )
        )
    if revision.is_approved:
        components.append(
            ScoreComponent(
                code="APPROVED_VERSION",
                points=config.approved_version,
                explanation="Файл помечен как согласованный.",
            )
        )


def _add_file_status_components(
    components: list[ScoreComponent],
    candidate: SourceCandidate,
    config: SourceScoringConfig,
) -> None:
    entry = candidate.entry
    if entry.is_probable_copy:
        components.append(
            ScoreComponent(
                code="PROBABLE_COPY",
                points=config.probable_copy,
                explanation="Файл выглядит как копия.",
            )
        )
    if entry.is_probably_outdated:
        components.append(
            ScoreComponent(
                code="OUTDATED",
                points=config.outdated,
                explanation="Файл выглядит устаревшим.",
            )
        )
    if entry.is_draft:
        components.append(
            ScoreComponent(
                code="DRAFT",
                points=config.draft,
                explanation="Файл помечен как черновик.",
            )
        )

"""One-pass global reconciliation orchestration with injectable I/O boundaries."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from report_processor.business_rules import ValidatedRuleSet
from report_processor.calculation import CalculationResult, calculate_matches
from report_processor.matching import MatchResult, MatchStatus, match_rows
from report_processor.normalization import NormalizedSourceRow
from report_processor.quality_control import (
    QualityControlReport,
    WriteDecision,
    evaluate_quality_control,
)
from report_processor.reconciliation_review import (
    AppliedOverride,
    ReviewDecision,
    ReviewGroup,
    ReviewRow,
    apply_overrides,
    build_review_groups,
)
from report_processor.target_report import TargetReportRow


@dataclass(frozen=True, slots=True)
class ReconciliationArtifacts:
    """Private core artifacts for the integration layer, never a presentation payload."""

    normalized_rows: tuple[NormalizedSourceRow, ...]
    review_rows: tuple[ReviewRow, ...]
    review_groups: tuple[ReviewGroup, ...]
    overrides: tuple[AppliedOverride, ...]
    matches: tuple[MatchResult, ...]
    calculations: tuple[CalculationResult, ...]
    quality_control: QualityControlReport
    write_result: object | None


def execute_reconciliation(
    source_workbooks: Iterable[object],
    target_workbook: object,
    rule_set: ValidatedRuleSet,
    *,
    inspect_target: Callable[[object], Iterable[TargetReportRow]],
    normalize_source: Callable[[object], Iterable[NormalizedSourceRow]],
    target_source_id: str,
    target_fingerprint: str,
    decisions: Iterable[ReviewDecision] = (),
    write: Callable[[object, tuple[CalculationResult, ...]], object] | None = None,
) -> ReconciliationArtifacts:
    """Inspect the original target once, calculate globally, and write it at most once.

    I/O stays injected so this core neither opens workbooks nor leaks source paths.
    Without decisions the matching result follows the legacy singleton selection path.
    """
    target_rows = tuple(inspect_target(target_workbook))
    normalized_rows = tuple(
        row for workbook in source_workbooks for row in normalize_source(workbook)
    )
    initial_matches = match_rows(
        normalized_rows,
        target_rows,
        rule_set,
        target_source_id=target_source_id,
        target_fingerprint=target_fingerprint,
    )
    review_rows = _review_rows(normalized_rows)
    review_groups = build_review_groups(review_rows)
    decision_snapshot = tuple(decisions)
    overrides = (
        apply_overrides(review_rows, review_groups, decision_snapshot) if decision_snapshot else {}
    )
    matches = _apply_overrides(initial_matches, overrides) if decision_snapshot else initial_matches
    inclusions = _candidate_inclusions(matches, overrides)
    calculations = calculate_matches(matches, rule_set, inclusions)
    quality_control = evaluate_quality_control(matches, calculations, rule_set)
    write_result = None
    if write is not None and quality_control.decision is WriteDecision.ALLOW_WRITE:
        write_result = write(target_workbook, calculations)
    return ReconciliationArtifacts(
        normalized_rows=tuple(sorted(normalized_rows, key=lambda row: row.source_row_id)),
        review_rows=review_rows,
        review_groups=review_groups,
        overrides=tuple(sorted(overrides.values(), key=lambda item: item.row_id)),
        matches=matches,
        calculations=calculations,
        quality_control=quality_control,
        write_result=write_result,
    )


def _review_rows(rows: Iterable[NormalizedSourceRow]) -> tuple[ReviewRow, ...]:
    return tuple(
        ReviewRow(
            row_id=row.source_row_id,
            display_name=row.work_name,
            unit=row.unit,
            quantity=row.source_row.period_quantity,
            cost=row.source_row.period_cost,
        )
        for row in sorted(rows, key=lambda item: item.source_row_id)
    )


def _apply_overrides(
    matches: Iterable[MatchResult], overrides: dict[str, AppliedOverride]
) -> tuple[MatchResult, ...]:
    return tuple(
        _effective_match(match, overrides)
        for match in sorted(matches, key=lambda item: item.target_row_id)
    )


def _effective_match(match: MatchResult, overrides: dict[str, AppliedOverride]) -> MatchResult:
    selected = tuple(
        candidate
        for candidate in match.candidates
        if (override := overrides.get(candidate.source_row_id)) is not None
        and override.target_category == match.target_row_id
    )
    return MatchResult(
        result_id=match.result_id,
        target_row_id=match.target_row_id,
        target_row=match.target_row,
        status=MatchStatus.MATCHED if selected else MatchStatus.UNMATCHED,
        selected_candidate=None,
        candidates=match.candidates,
        warnings=match.warnings,
        explanation=(*match.explanation, "global_review_selection"),
        selected_candidates=selected,
    )


def _candidate_inclusions(
    matches: Iterable[MatchResult], overrides: dict[str, AppliedOverride]
) -> dict[str, tuple[bool, bool]]:
    return {
        candidate.candidate_id: override.candidate_inclusion
        for match in matches
        for candidate in match.effective_selected_candidates
        if (override := overrides.get(candidate.source_row_id)) is not None
    }

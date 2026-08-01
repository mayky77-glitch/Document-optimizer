"""One-pass global reconciliation orchestration with injectable I/O boundaries."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from report_processor.business_rules import ValidatedRuleSet
from report_processor.calculation import CalculationResult, calculate_matches
from report_processor.matching import (
    MatchCandidate,
    MatchResult,
    MatchStatus,
    MatchStrategy,
    match_rows,
)
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
    review_rows = _review_rows(normalized_rows, initial_matches)
    review_groups = build_review_groups(review_rows)
    decision_snapshot = tuple(decisions)
    overrides = (
        apply_overrides(review_rows, review_groups, decision_snapshot) if decision_snapshot else {}
    )
    matches = (
        _apply_overrides(initial_matches, normalized_rows, overrides, target_source_id)
        if decision_snapshot
        else initial_matches
    )
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


def _review_rows(
    rows: Iterable[NormalizedSourceRow], matches: Iterable[MatchResult]
) -> tuple[ReviewRow, ...]:
    proposed_categories = {
        candidate.source_row_id: match.target_row_id
        for match in sorted(matches, key=lambda item: item.target_row_id)
        for candidate in match.effective_selected_candidates
    }
    return tuple(
        ReviewRow(
            row_id=row.source_row_id,
            display_name=row.work_name,
            unit=row.unit,
            quantity=row.source_row.period_quantity,
            cost=row.source_row.period_cost,
            proposed_category=proposed_categories.get(row.source_row_id),
        )
        for row in sorted(rows, key=lambda item: item.source_row_id)
    )


def _apply_overrides(
    matches: Iterable[MatchResult],
    source_rows: Iterable[NormalizedSourceRow],
    overrides: dict[str, AppliedOverride],
    target_source_id: str,
) -> tuple[MatchResult, ...]:
    sources = {row.source_row_id: row for row in source_rows}
    return tuple(
        _effective_match(match, sources, overrides, target_source_id)
        for match in sorted(matches, key=lambda item: item.target_row_id)
    )


def _effective_match(
    match: MatchResult,
    sources: dict[str, NormalizedSourceRow],
    overrides: dict[str, AppliedOverride],
    target_source_id: str,
) -> MatchResult:
    candidates = list(match.candidates)
    candidate_by_source = {item.source_row_id: item for item in candidates}
    selected: list[MatchCandidate] = []
    for source_row_id, override in sorted(overrides.items()):
        if override.target_category != match.target_row_id:
            continue
        candidate = candidate_by_source.get(source_row_id)
        if candidate is None:
            source = sources.get(source_row_id)
            if source is None:
                raise ValueError("override references an unavailable normalized source row")
            candidate = _authoritative_candidate(match, source, target_source_id)
            candidates.append(candidate)
            candidate_by_source[source_row_id] = candidate
        selected.append(candidate)
    return MatchResult(
        result_id=match.result_id,
        target_row_id=match.target_row_id,
        target_row=match.target_row,
        status=MatchStatus.MATCHED if selected else MatchStatus.UNMATCHED,
        selected_candidate=None,
        candidates=tuple(candidates),
        warnings=match.warnings,
        explanation=(*match.explanation, "global_review_selection"),
        selected_candidates=tuple(selected),
    )


def _authoritative_candidate(
    match: MatchResult, source: NormalizedSourceRow, target_source_id: str
) -> MatchCandidate:
    """Build an explicit human-selected candidate without claiming a fuzzy match."""
    target = match.target_row
    return MatchCandidate(
        candidate_id=_identity(
            "authoritative-review-candidate",
            match.result_id,
            match.target_row_id,
            source.source_row_id,
        ),
        target_row_id=match.target_row_id,
        source_row_id=source.source_row_id,
        source_row=source,
        strategies=(MatchStrategy.AUTHORITATIVE_REVIEW,),
        confidence=Decimal("1"),
        rule_ids=(),
        explanation=("authoritative_review_decision",),
        source_provenance=dict(source.provenance),
        target_provenance={
            "target_source_id": target_source_id,
            "sheet_name": target.sheet_name,
            "row_number": target.row_number,
            "target_row_id": match.target_row_id,
        },
        auto_selectable=False,
    )


def _identity(*parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _candidate_inclusions(
    matches: Iterable[MatchResult], overrides: dict[str, AppliedOverride]
) -> dict[str, tuple[bool, bool]]:
    return {
        candidate.candidate_id: override.candidate_inclusion
        for match in matches
        for candidate in match.effective_selected_candidates
        if (override := overrides.get(candidate.source_row_id)) is not None
    }

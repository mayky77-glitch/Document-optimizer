"""Pure deterministic implementation of the MatchingEngine-12.0 cascade."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from hashlib import sha256

from report_processor.business_rules import RuleAction, RuleMatchKind, ValidatedRuleSet
from report_processor.identifiers import extract_document_index
from report_processor.normalization.models import NormalizedSourceRow, TypoDictionaries
from report_processor.normalization.normalizers import (
    normalize_code,
    normalize_name,
    normalize_unit,
)
from report_processor.target_report.models import TargetReportRow

from .exceptions import MatchingInputError
from .models import (
    MATCHING_CONTRACT_VERSION,
    MatchCandidate,
    MatchingPolicy,
    MatchResult,
    MatchStatus,
    MatchStrategy,
    strategy_ordinal,
)

_CONFIDENCE = {
    MatchStrategy.EXACT_BUSINESS_KEY: Decimal("1.000000"),
    MatchStrategy.INDEX_POSITION: Decimal("0.980000"),
    MatchStrategy.OBJECT_SUBOBJECT_POSITION: Decimal("0.960000"),
    MatchStrategy.NORMALIZED_NAME_UNIT: Decimal("0.920000"),
    MatchStrategy.NORMALIZED_NAME_CONTEXT: Decimal("0.880000"),
    MatchStrategy.CONFIGURATION_RULE: Decimal("0.750000"),
    MatchStrategy.FUZZY_REVIEW: Decimal("0.750000"),
}
_RULE_CONFIDENCE = {
    RuleMatchKind.EXACT: Decimal("0.850000"),
    RuleMatchKind.PREFIX: Decimal("0.800000"),
    RuleMatchKind.CONTAINS: Decimal("0.750000"),
}


@dataclass(frozen=True, slots=True)
class _TargetValues:
    row: TargetReportRow
    row_id: str
    target_source_id: str
    object_code: str | None
    subobject_code: str | None
    position_code: str | None
    work_name: str | None
    unit: str | None
    document_index: str | None

    @property
    def provenance(self) -> dict[str, str | int]:
        return {
            "target_source_id": self.target_source_id,
            "sheet_name": self.row.sheet_name,
            "row_number": self.row.row_number,
            "target_row_id": self.row_id,
        }


def match_rows(
    source_rows: Iterable[NormalizedSourceRow],
    target_rows: Iterable[TargetReportRow],
    rule_set: ValidatedRuleSet,
    *,
    target_source_id: str,
    target_fingerprint: str,
    policy: MatchingPolicy = MatchingPolicy(),  # noqa: B008
) -> tuple[MatchResult, ...]:
    """Match immutable rows without calculations, persistence, or workbook writes."""

    _validate_public_inputs(rule_set, target_source_id, target_fingerprint, policy)
    sources = _ordered_sources(source_rows)
    targets = _ordered_targets(target_rows, target_source_id, target_fingerprint)
    return tuple(
        _result_for_target(target, sources, rule_set, target_source_id, target_fingerprint, policy)
        for target in targets
    )


def _validate_public_inputs(
    rule_set: ValidatedRuleSet,
    target_source_id: str,
    target_fingerprint: str,
    policy: MatchingPolicy,
) -> None:
    if not isinstance(rule_set, ValidatedRuleSet):
        raise MatchingInputError("INVALID_RULE_SET", "rule_set должен быть ValidatedRuleSet")
    if not isinstance(target_source_id, str) or not target_source_id.strip():
        raise MatchingInputError(
            "INVALID_TARGET_SOURCE_ID", "target_source_id должен быть непустой строкой"
        )
    if not isinstance(target_fingerprint, str) or not target_fingerprint.strip():
        raise MatchingInputError(
            "INVALID_TARGET_FINGERPRINT", "target_fingerprint должен быть непустой строкой"
        )
    if not isinstance(policy, MatchingPolicy):
        raise MatchingInputError("INVALID_POLICY", "policy должен быть MatchingPolicy")


def _ordered_sources(rows: Iterable[NormalizedSourceRow]) -> tuple[NormalizedSourceRow, ...]:
    collected = tuple(rows)
    if any(not isinstance(row, NormalizedSourceRow) for row in collected):
        raise MatchingInputError(
            "INVALID_SOURCE_ROW", "source_rows содержит не NormalizedSourceRow"
        )
    duplicates = _duplicates(row.source_row_id for row in collected)
    if duplicates:
        raise MatchingInputError("DUPLICATE_SOURCE_ROW_ID", ",".join(duplicates))
    return tuple(sorted(collected, key=lambda row: row.source_row_id))


def _ordered_targets(
    rows: Iterable[TargetReportRow], target_source_id: str, target_fingerprint: str
) -> tuple[_TargetValues, ...]:
    collected = tuple(rows)
    if any(not isinstance(row, TargetReportRow) for row in collected):
        raise MatchingInputError("INVALID_TARGET_ROW", "target_rows содержит не TargetReportRow")
    locations = _duplicates(f"{row.sheet_name}\x1f{row.row_number}" for row in collected)
    if locations:
        raise MatchingInputError("DUPLICATE_TARGET_LOCATION", ",".join(locations))
    dictionaries = TypoDictionaries()
    values = tuple(
        _TargetValues(
            row=row,
            row_id=_target_row_id(target_source_id, target_fingerprint, row),
            target_source_id=target_source_id,
            object_code=normalize_code(row.object_code, dictionaries),
            subobject_code=normalize_code(row.subobject_code, dictionaries),
            position_code=normalize_code(row.position_code, dictionaries),
            work_name=normalize_name(row.work_name, dictionaries),
            unit=normalize_unit(row.unit, dictionaries),
            document_index=_document_index(row.document_index_normalized or row.document_index_raw),
        )
        for row in collected
    )
    return tuple(
        sorted(
            values, key=lambda item: (target_source_id, item.row.sheet_name, item.row.row_number)
        )
    )


def _result_for_target(
    target: _TargetValues,
    sources: tuple[NormalizedSourceRow, ...],
    rule_set: ValidatedRuleSet,
    target_source_id: str,
    target_fingerprint: str,
    policy: MatchingPolicy,
) -> MatchResult:
    candidates = tuple(
        candidate
        for source in sources
        if (candidate := _candidate_for_pair(source, target, rule_set, policy)) is not None
    )
    eligible = tuple(item for item in candidates if item.auto_selectable)
    selected, status, warnings, explanation = _selection(eligible, candidates)
    result_id = _hash(
        "result",
        MATCHING_CONTRACT_VERSION,
        target.row_id,
        rule_set.content_hash,
        target_source_id,
        target_fingerprint,
    )
    return MatchResult(
        result_id=result_id,
        target_row_id=target.row_id,
        target_row=target.row,
        status=status,
        selected_candidate=selected,
        candidates=candidates,
        warnings=warnings,
        explanation=explanation,
    )


def _candidate_for_pair(
    source: NormalizedSourceRow,
    target: _TargetValues,
    rule_set: ValidatedRuleSet,
    policy: MatchingPolicy,
) -> MatchCandidate | None:
    strategies: list[MatchStrategy] = []
    explanations: list[str] = []
    if _exact_business_key(source, target):
        strategies.append(MatchStrategy.EXACT_BUSINESS_KEY)
        explanations.append("exact_business_key")
    if _index_position(source, target):
        strategies.append(MatchStrategy.INDEX_POSITION)
        explanations.append("index_position")
    if _object_subobject_position(source, target):
        strategies.append(MatchStrategy.OBJECT_SUBOBJECT_POSITION)
        explanations.append("object_subobject_position")
    if _name_unit(source, target):
        strategies.append(MatchStrategy.NORMALIZED_NAME_UNIT)
        explanations.append("normalized_name_unit")
    if _name_context(source, target):
        strategies.append(MatchStrategy.NORMALIZED_NAME_CONTEXT)
        explanations.append("normalized_name_context")
    rule_ids, blockers, manual, rule_confidence = _rule_effects(source, target, rule_set)
    if rule_ids:
        strategies.append(MatchStrategy.CONFIGURATION_RULE)
        explanations.append("configuration_rule:" + ",".join(rule_ids))
    fuzzy_confidence = _fuzzy_similarity(source.work_name, target.work_name)
    if fuzzy_confidence is not None and fuzzy_confidence >= policy.fuzzy_threshold:
        strategies.append(MatchStrategy.FUZZY_REVIEW)
        explanations.append("fuzzy_review")
        manual = True
    if not strategies:
        return None
    ordered = tuple(sorted(set(strategies), key=strategy_ordinal))
    primary = ordered[0]
    confidence = (
        rule_confidence if primary is MatchStrategy.CONFIGURATION_RULE else _CONFIDENCE[primary]
    )
    if MatchStrategy.FUZZY_REVIEW in ordered and len(ordered) == 1:
        confidence = fuzzy_confidence
    auto_selectable = not blockers and not manual
    candidate_id = _hash(
        "candidate",
        MATCHING_CONTRACT_VERSION,
        target.row_id,
        source.source_row_id,
        rule_set.content_hash,
    )
    return MatchCandidate(
        candidate_id=candidate_id,
        target_row_id=target.row_id,
        source_row_id=source.source_row_id,
        source_row=source,
        strategies=ordered,
        confidence=confidence,
        rule_ids=rule_ids,
        explanation=tuple(explanations),
        source_provenance=dict(source.provenance),
        target_provenance=target.provenance,
        blockers=blockers,
        auto_selectable=auto_selectable,
    )


def _selection(
    eligible: tuple[MatchCandidate, ...], candidates: tuple[MatchCandidate, ...]
) -> tuple[MatchCandidate | None, MatchStatus, tuple[str, ...], tuple[str, ...]]:
    if not eligible:
        if candidates:
            if any(not candidate.blockers for candidate in candidates):
                return (
                    None,
                    MatchStatus.AMBIGUOUS,
                    ("MANUAL_REVIEW_REQUIRED",),
                    ("only manual candidates matched",),
                )
            return (
                None,
                MatchStatus.UNMATCHED,
                ("NO_ELIGIBLE_CANDIDATE",),
                ("all candidates blocked",),
            )
        return None, MatchStatus.UNMATCHED, ("NO_CANDIDATES",), ("no strategy matched",)
    best_ordinal = min(item.strategy_ordinal for item in eligible)
    best = tuple(item for item in eligible if item.strategy_ordinal == best_ordinal)
    if len(best) != 1:
        return None, MatchStatus.AMBIGUOUS, ("MULTIPLE_BEST_CANDIDATES",), ("strategy ordinal tie",)
    selected = best[0]
    return selected, MatchStatus.MATCHED, (), (f"selected:{selected.strategy.value}",)


def _exact_business_key(source: NormalizedSourceRow, target: _TargetValues) -> bool:
    pairs = (
        (source.object_code, target.object_code),
        (source.subobject_code, target.subobject_code),
        (source.position_code, target.position_code),
        (source.work_name, target.work_name),
        (source.unit, target.unit),
    )
    return all(left is not None and left == right for left, right in pairs)


def _index_position(source: NormalizedSourceRow, target: _TargetValues) -> bool:
    source_index = _document_index(source.source_filename) or _document_index(source.source_file_id)
    complete = all(
        (source_index, target.document_index, source.position_code, target.position_code)
    )
    return complete and (
        source_index == target.document_index and source.position_code == target.position_code
    )


def _object_subobject_position(source: NormalizedSourceRow, target: _TargetValues) -> bool:
    pairs = (
        (source.object_code, target.object_code),
        (source.subobject_code, target.subobject_code),
        (source.position_code, target.position_code),
    )
    return all(left is not None and left == right for left, right in pairs)


def _name_unit(source: NormalizedSourceRow, target: _TargetValues) -> bool:
    return all((source.work_name, target.work_name, source.unit, target.unit)) and (
        source.work_name == target.work_name and source.unit == target.unit
    )


def _name_context(source: NormalizedSourceRow, target: _TargetValues) -> bool:
    if source.work_name is None or source.work_name != target.work_name:
        return False
    context = (
        (source.object_code, target.object_code),
        (source.subobject_code, target.subobject_code),
    )
    return any(left is not None and left == right for left, right in context)


def _rule_effects(
    source: NormalizedSourceRow, target: _TargetValues, rule_set: ValidatedRuleSet
) -> tuple[tuple[str, ...], tuple[str, ...], bool, Decimal]:
    matched: list[str] = []
    blockers: list[str] = []
    manual = False
    confidence = _CONFIDENCE[MatchStrategy.CONFIGURATION_RULE]
    for rule in sorted(rule_set.rules, key=lambda item: item.rule_id):
        if not rule.owner_approved or rule.status != "approved":
            continue
        if not _scope_matches(rule.scope, source, target):
            continue
        for clause in rule.clauses:
            if not _clause_matches(clause, source.work_name, source.unit):
                continue
            matched.append(rule.rule_id)
            confidence = max(confidence, _RULE_CONFIDENCE[clause.match_kind])
            if clause.action is RuleAction.EXCLUDE:
                blockers.append(f"EXCLUDE:{rule.rule_id}")
            elif clause.action is RuleAction.REVIEW:
                manual = True
    return tuple(sorted(set(matched))), tuple(sorted(set(blockers))), manual, confidence


def _scope_matches(scope, source: NormalizedSourceRow, target: _TargetValues) -> bool:
    return (
        _in_scope(target.object_code, scope.object_scopes, normalize_code)
        and _in_scope(target.row.stage, scope.stages, normalize_name)
        and _in_scope(target.work_name, scope.target_processes, normalize_name)
        and _in_scope(source.unit, scope.source_units, normalize_unit)
    )


def _in_scope(value: str | None, allowed: tuple[str, ...], normalizer) -> bool:
    if not allowed:
        return True
    dictionaries = TypoDictionaries()
    normalized = tuple(item for raw in allowed if (item := normalizer(raw, dictionaries)))
    return value is not None and value in normalized


def _clause_matches(clause, source_name: str | None, source_unit_raw: str | None) -> bool:
    if source_name is None:
        return False
    literal = normalize_name(clause.literal, TypoDictionaries())
    if literal is None:
        return False
    if clause.match_kind is RuleMatchKind.EXACT:
        matches = source_name == literal
    elif clause.match_kind is RuleMatchKind.PREFIX:
        matches = source_name.startswith(literal)
    else:
        matches = literal in source_name
    source_unit = normalize_unit(source_unit_raw, TypoDictionaries())
    allowed_units = tuple(
        item for raw in clause.source_units if (item := normalize_unit(raw, TypoDictionaries()))
    )
    excluded_units = tuple(
        item for raw in clause.excluded_units if (item := normalize_unit(raw, TypoDictionaries()))
    )
    required = tuple(
        item
        for raw in clause.required_substrings
        if (item := normalize_name(raw, TypoDictionaries()))
    )
    forbidden = tuple(
        item
        for raw in clause.forbidden_substrings
        if (item := normalize_name(raw, TypoDictionaries()))
    )
    return (
        matches
        and (not allowed_units or source_unit in allowed_units)
        and source_unit not in excluded_units
        and all(token in source_name for token in required)
        and not any(token in source_name for token in forbidden)
    )


def _fuzzy_similarity(source_name: str | None, target_name: str | None) -> Decimal | None:
    if not source_name or not target_name or source_name == target_name:
        return None
    matcher = SequenceMatcher(None, source_name, target_name, autojunk=False)
    matched_characters = sum(block.size for block in matcher.get_matching_blocks())
    total_characters = len(source_name) + len(target_name)
    if total_characters == 0:
        return None
    return (Decimal(2 * matched_characters) / Decimal(total_characters)).quantize(
        Decimal("0.000001")
    )


def _document_index(value: object) -> str | None:
    result = extract_document_index(value)
    return result.value.normalized if result.value is not None else None


def _target_row_id(target_source_id: str, target_fingerprint: str, row: TargetReportRow) -> str:
    return _hash(
        "target",
        MATCHING_CONTRACT_VERSION,
        target_source_id,
        target_fingerprint,
        row.sheet_name,
        row.row_number,
    )


def _hash(*parts: object) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    counts: defaultdict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return tuple(sorted(value for value, count in counts.items() if count > 1))

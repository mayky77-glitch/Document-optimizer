"""Cascaded deterministic, dictionary, retrieval and tiny-model matcher."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from ..config import CategoryRule, RulesConfig
from ..models import DrawingSourceRow, MatchDecision, TargetWorkCategory
from ..sources.normalization import normalize_text, normalize_unit
from ..statuses import Status
from .examples import (
    ConfirmedExample,
    LexicalExampleRetriever,
    exact_example_match,
    has_exact_example_conflict,
)
from .masks import contains_mask, has_all_masks, has_any_mask
from .semantic import SemanticExampleRetriever

if TYPE_CHECKING:
    from ..autopilot import MachineConsensusStore
    from .tiny_model import OpenAICompatibleTinyModel


@dataclass(frozen=True, slots=True)
class ModelClassificationRequest:
    source_text: str
    normalized_text: str
    unit: str | None
    drawing_code: str | None
    source_type: str | None
    negative_rules: tuple[str, ...]
    retrieved_examples: tuple[ConfirmedExample, ...]


@dataclass(frozen=True, slots=True)
class ReviewApproval:
    row_id: str
    action: str
    category: TargetWorkCategory | None


_TARGET_CUES = (
    "свайн",
    "буроопускн",
    "буронабивн",
    "бетон",
    "монолит",
    "железобетон",
    "ростверк",
    "металлоконструк",
    "м/к",
    "трубопровод",
    "зра",
    "запорн",
    "кабел",
    "сети связи",
    "системы связи",
    "волс",
)

_CONFIRMED_NEGATIVE_PHRASES = (
    "испытание свай",
    "статическое испытание",
    "динамическое испытание",
    "контроль свай",
    "обследование свай",
    "испытание бетона",
    "лабораторный контроль",
    "демонтаж бетона",
    "демонтаж металлоконструкций",
    "испытание трубопровод",
    "изоляция трубопровод",
    "окраска трубопровод",
    "промывка трубопровод",
    "продувка трубопровод",
    "демонтаж трубопровод",
    "ремонт арматуры",
    "испытание арматуры",
    "ревизия арматуры",
    "демонтаж арматуры",
    "подключение жил",
    "разводка по устройствам",
)

_CONFIRMED_NEGATIVE_ALL = (
    ("испытан", "сва"),
    ("контрол", "сва"),
    ("обследован", "сва"),
    ("геодез", "сва"),
    ("изыскан", "сва"),
    ("контрол", "трубопровод"),
    ("изоляц", "трубопровод"),
    ("испытан", "трубопровод"),
    ("окраск", "трубопровод"),
    ("промывк", "трубопровод"),
    ("продувк", "трубопровод"),
    ("сварк", "трубопровод"),
    ("рк", "трубопровод"),
    ("узк", "трубопровод"),
    ("капиллярн", "трубопровод"),
    ("опорн", "трубопровод"),
    ("поддержк", "трубопровод"),
    ("креплен", "трубопровод"),
    ("мачт", "молниеотвод"),
    ("антенн", "мачт"),
    ("изготовлен", "емкост"),
    ("изготовлен", "резервуар"),
    ("подключен", "жил"),
)

_UNRESOLVED_FORMULA_WARNINGS = frozenset({Status.FORMULA_WITHOUT_CACHED_VALUE, Status.EXCEL_ERROR})
_CABLE_COUPLING_PREFIX_RE = re.compile(r"^установка муфт соединительных\b", re.IGNORECASE)


@lru_cache(maxsize=256)
def _exact_token_pattern(phrase: str) -> re.Pattern[str]:
    """Compatibility helper for exact token masks; cache remains strictly bounded."""
    return re.compile(rf"(?<![\w/]){re.escape(normalize_text(phrase))}(?![\w/])", re.IGNORECASE)


def _contains_phrase(text: str, phrase: str) -> bool:
    return contains_mask(text, phrase)


def _has_target_cue(text: str) -> bool:
    if any(_contains_phrase(text, token) for token in _TARGET_CUES):
        return True
    cable_context = _has_any(text, ("кабел", "провод", "прокладк", "сет"))
    electrical_context = _has_any(text, ("силов", "слаботоч", "кип", "автоматик"))
    return cable_context and electrical_context


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return has_any_mask(text, phrases)


def _has_confirmed_negative(text: str) -> bool:
    if _has_any(text, _CONFIRMED_NEGATIVE_PHRASES):
        return True
    return any(has_all_masks(text, group) for group in _CONFIRMED_NEGATIVE_ALL)


def _rule_matches(text: str, rule: CategoryRule) -> bool:
    if _has_any(text, rule.exclude_any):
        return False
    exact_groups = any(has_all_masks(text, group) for group in rule.include_all)
    return exact_groups or _has_any(text, rule.include_any)


def _strong_rule_matches(text: str, rule: CategoryRule) -> bool:
    """Mismatch automation needs a composite rule, never a broad one-token cue."""
    if _has_any(text, rule.exclude_any):
        return False
    if any(has_all_masks(text, group) for group in rule.include_all):
        return True
    return any(
        len(normalize_text(cue).split()) > 1 and _contains_phrase(text, cue)
        for cue in rule.include_any
    )


def _unit_is_compatible(unit: str | None, rule: CategoryRule) -> bool:
    normalized = normalize_unit(unit)
    expected = {normalize_unit(item) for item in rule.expected_units}
    return normalized is None or not expected or normalized in expected


class DrawingRowMatcher:
    def __init__(
        self,
        rules: RulesConfig,
        examples: tuple[ConfirmedExample, ...],
        *,
        rag_mode: str,
        tiny_model: OpenAICompatibleTinyModel | None = None,
        approvals: dict[str, ReviewApproval] | None = None,
        machine_consensus: MachineConsensusStore | None = None,
    ) -> None:
        self.rules = rules
        self.examples = examples
        self.retriever = LexicalExampleRetriever(examples)
        self.semantic_retriever = (
            SemanticExampleRetriever(examples) if rag_mode == "semantic" else None
        )
        self.rag_mode = rag_mode
        self.tiny_model = tiny_model
        self.approvals = approvals or {}
        self.machine_consensus = machine_consensus
        self.model_calls = 0

    def _approved_decision(self, row: DrawingSourceRow) -> MatchDecision | None:
        approval = self.approvals.get(row.row_id)
        if approval is None:
            return None
        if approval.action in {"reject", "skip"}:
            return MatchDecision(
                row_id=row.row_id,
                category=None,
                quantity_decision="exclude",
                cost_decision="exclude",
                quantity_rule_id="manual-review",
                cost_rule_id="manual-review",
                quantity_confidence=1.0,
                cost_confidence=1.0,
                matching_strategy="manual_review",
                evidence_ids=(),
                reason="Imported manual review decision explicitly excludes this row",
                requires_manual_review=False,
                status=Status.OK,
                warnings=(),
            )
        if approval.category is None:
            return None
        quantity = (
            "include"
            if approval.action in {"approve", "quantity_only", "change_category"}
            else "exclude"
        )
        cost = (
            "include"
            if approval.action in {"approve", "cost_only", "change_category"}
            else "exclude"
        )
        return MatchDecision(
            row_id=row.row_id,
            category=approval.category,
            quantity_decision=quantity,
            cost_decision=cost,
            quantity_rule_id="manual-review",
            cost_rule_id="manual-review",
            quantity_confidence=1.0,
            cost_confidence=1.0,
            matching_strategy="manual_review",
            evidence_ids=(),
            reason="Imported and explicitly approved manual review decision",
            requires_manual_review=False,
            status=Status.OK,
            warnings=(),
        )

    def match(self, row: DrawingSourceRow) -> MatchDecision:
        approved = self._approved_decision(row)
        if approved is not None:
            return approved
        text = normalize_text(row.work_name_raw)
        if self._has_unresolved_formula(row):
            return self._review(
                row,
                reason="Formula value is unresolved; automatic no-impact exclusion is unsafe",
                warnings=tuple(
                    str(item) for item in row.warnings if str(item).startswith("FORMULA_")
                ),
            )
        if self._is_no_impact(row, text):
            return self._exclude_no_impact(row)
        if has_exact_example_conflict(text, self.examples, unit=row.unit_raw):
            return self._review(
                row,
                reason="Conflicting exact feedback requires manual review",
                warnings=(Status.CONFLICT_REQUIRES_REVIEW,),
            )
        exact = exact_example_match(
            text,
            self.examples,
            unit=row.unit_raw,
            source_type=row.source_document_type,
        )
        if exact is not None:
            if (
                exact.category is None
                or exact.unit is None
                or exact.unit == normalize_unit(row.unit_raw)
            ):
                return MatchDecision(
                    row_id=row.row_id,
                    category=exact.category,
                    quantity_decision=exact.quantity_decision,
                    cost_decision=exact.cost_decision,
                    quantity_rule_id=f"example:{exact.example_id}",
                    cost_rule_id=f"example:{exact.example_id}",
                    quantity_confidence=1.0,
                    cost_confidence=1.0,
                    matching_strategy="confirmed_dictionary",
                    evidence_ids=(exact.example_id,),
                    reason="Exact confirmed example",
                    requires_manual_review=False,
                    status=Status.OK,
                    warnings=(),
                )
            return self._review(
                row,
                category=exact.category,
                reason="Exact confirmed example has an incompatible unit",
                warnings=(Status.UNIT_MISMATCH,),
                evidence_ids=(exact.example_id,),
            )
        if _has_confirmed_negative(text):
            return self._exclude_negative(row)
        coupling = self._safe_cable_coupling(row, text)
        if coupling is not None:
            return coupling
        if self.machine_consensus and self.machine_consensus.requires_manual_review(
            row, self.rules.version
        ):
            return self._review(
                row,
                reason="Machine consensus is stale or conflicting",
                warnings=(Status.CONFLICT_REQUIRES_REVIEW,),
            )
        machine = (
            self.machine_consensus.lookup(row, self.rules.version)
            if self.machine_consensus
            else None
        )
        if machine is not None:
            rule = next(
                (item for item in self.rules.categories if item.category == machine.category), None
            )
            if (
                machine.quantity_decision == "include"
                and rule is not None
                and not _unit_is_compatible(row.unit_raw, rule)
            ):
                return self._review(
                    row,
                    category=machine.category,
                    reason="Machine consensus cannot include quantity across a unit mismatch",
                    warnings=(Status.UNIT_MISMATCH,),
                )
            return MatchDecision(
                row_id=row.row_id,
                category=machine.category,
                quantity_decision=machine.quantity_decision,
                cost_decision=machine.cost_decision,
                quantity_rule_id=f"machine-consensus:{machine.fingerprint}",
                cost_rule_id=f"machine-consensus:{machine.fingerprint}",
                quantity_confidence=1.0 if machine.quantity_decision == "include" else None,
                cost_confidence=1.0 if machine.cost_decision == "include" else None,
                matching_strategy="machine_consensus_exact",
                evidence_ids=(machine.fingerprint,),
                reason="Exact private machine consensus",
                requires_manual_review=False,
                status=Status.OK,
                warnings=(),
            )
        matched = [rule for rule in self.rules.categories if _rule_matches(text, rule)]
        compatible = [rule for rule in matched if _unit_is_compatible(row.unit_raw, rule)]
        if len(compatible) == 1:
            return self._deterministic(row, text, compatible[0])
        if len(compatible) > 1:
            return self._review(
                row,
                reason="Several deterministic categories matched",
                warnings=("MULTIPLE_CATEGORY_MATCHES",),
            )
        if len(matched) == 1:
            strong = [rule for rule in self.rules.categories if _strong_rule_matches(text, rule)]
            if (
                len(strong) == 1
                and row.remaining_total_cost not in (None, 0)
                and not _unit_is_compatible(row.unit_raw, strong[0])
                and _has_any(text, strong[0].cost_only_any)
            ):
                return self._strong_cost_only(row, strong[0])
            return self._review(
                row,
                category=matched[0].category,
                reason="Deterministic category has an incompatible unit",
                warnings=(Status.UNIT_MISMATCH,),
            )
        if not _has_target_cue(text):
            return MatchDecision(
                row_id=row.row_id,
                category=None,
                quantity_decision="exclude",
                cost_decision="exclude",
                quantity_rule_id="rules:irrelevant-no-target-cue",
                cost_rule_id="rules:irrelevant-no-target-cue",
                quantity_confidence=0.99,
                cost_confidence=0.99,
                matching_strategy="deterministic_irrelevant",
                evidence_ids=(),
                reason="No target-category signals",
                requires_manual_review=False,
                status=Status.OK,
                warnings=(),
            )
        retrieved = self.retriever.search(
            text,
            source_type=row.source_document_type,
            unit=row.unit_raw,
            top_k=self.rules.top_k_examples,
        )
        if self.semantic_retriever is not None:
            semantic = self.semantic_retriever.search(text, top_k=self.rules.top_k_examples)
            proposed = next((item for item in semantic if item.example.category is not None), None)
            if proposed is not None:
                margin = proposed.score - (semantic[1].score if len(semantic) > 1 else 0.0)
                return self._review(
                    row,
                    category=proposed.example.category,
                    reason=(
                        "Локальная RuBERT-подсказка требует ручного подтверждения "
                        f"(score={proposed.score:.3f}, margin={margin:.3f})"
                    ),
                    warnings=("SEMANTIC_SUGGESTION_NOT_APPLIED",),
                    evidence_ids=tuple(item.example.example_id for item in semantic),
                    confidence=proposed.score,
                )
        if self.rag_mode != "off" and self.tiny_model is not None and retrieved:
            try:
                self.model_calls += 1
                model = self.tiny_model.classify(
                    ModelClassificationRequest(
                        source_text=row.work_name_raw or "",
                        normalized_text=text,
                        unit=row.unit_raw,
                        drawing_code=row.drawing_code_raw,
                        source_type=row.source_document_type,
                        negative_rules=tuple(
                            phrase
                            for rule in self.rules.categories
                            for phrase in rule.exclude_any
                            if normalize_text(phrase) in text
                        ),
                        retrieved_examples=retrieved,
                    )
                )
                return MatchDecision(
                    row_id=row.row_id,
                    category=model.category,
                    quantity_decision="review",
                    cost_decision="review",
                    quantity_rule_id=None,
                    cost_rule_id=None,
                    quantity_confidence=model.confidence,
                    cost_confidence=model.confidence,
                    matching_strategy="tiny_model_suggestion",
                    evidence_ids=model.evidence_ids,
                    reason=model.reason,
                    requires_manual_review=True,
                    status=Status.UNCONFIRMED_CLASSIFICATION,
                    warnings=("MODEL_SUGGESTION_NOT_APPLIED",),
                )
            except (ValueError, KeyError, TypeError) as error:
                return self._review(
                    row,
                    reason=f"Tiny-model response rejected: {error}",
                    warnings=(Status.MODEL_DECISION_INVALID,),
                    evidence_ids=tuple(item.example.example_id for item in retrieved),
                )
        return self._review(
            row,
            reason="No confirmed automatic classification",
            warnings=(Status.UNCONFIRMED_CLASSIFICATION,),
            evidence_ids=tuple(item.example.example_id for item in retrieved),
        )

    def _safe_cable_coupling(self, row: DrawingSourceRow, text: str) -> MatchDecision | None:
        """Include only a proven leading cable-coupling phrase as cost-only.

        This deliberately bypasses broad dictionary masks: an inner ``муфт``
        substring must never classify a row, and quantity is never inferred.
        Formula hazards, human feedback conflicts and negative rules are handled
        by the earlier cascade stages.
        """
        if not _CABLE_COUPLING_PREFIX_RE.match(text):
            return None
        if row.remaining_total_cost is None or row.remaining_total_cost <= 0:
            return self._review(
                row,
                category=TargetWorkCategory.POWER_CABLE,
                reason="Cable-coupling cost is missing or non-positive; manual review required",
                warnings=(),
            )
        rule_id = f"rules:{self.rules.version}:power_cable"
        return MatchDecision(
            row_id=row.row_id,
            category=TargetWorkCategory.POWER_CABLE,
            quantity_decision="exclude",
            cost_decision="include",
            quantity_rule_id=None,
            cost_rule_id=rule_id,
            quantity_confidence=None,
            cost_confidence=0.99,
            matching_strategy="deterministic_cable_coupling_cost_only",
            evidence_ids=(),
            reason="Anchored cable-coupling rule: cost only",
            requires_manual_review=False,
            status=Status.OK,
            warnings=(),
        )

    def _strong_cost_only(self, row: DrawingSourceRow, rule: CategoryRule) -> MatchDecision:
        rule_id = f"rules:{self.rules.version}:{rule.category.value}"
        return MatchDecision(
            row_id=row.row_id,
            category=rule.category,
            quantity_decision="exclude",
            cost_decision="include",
            quantity_rule_id=None,
            cost_rule_id=rule_id,
            quantity_confidence=None,
            cost_confidence=0.99,
            matching_strategy="deterministic_strong_rule_cost_only",
            evidence_ids=(),
            reason="Strong unique rule with unit mismatch: cost only",
            requires_manual_review=False,
            status=Status.OK,
            warnings=(Status.UNIT_MISMATCH,),
        )

    @staticmethod
    def _has_unresolved_formula(row: DrawingSourceRow) -> bool:
        return any(item in _UNRESOLVED_FORMULA_WARNINGS for item in row.warnings)

    @staticmethod
    def _is_no_impact(row: DrawingSourceRow, text: str) -> bool:
        return not text or (
            row.remaining_quantity in (None, 0) and row.remaining_total_cost in (None, 0)
        )

    @staticmethod
    def _exclude_no_impact(row: DrawingSourceRow) -> MatchDecision:
        return MatchDecision(
            row_id=row.row_id,
            category=None,
            quantity_decision="exclude",
            cost_decision="exclude",
            quantity_rule_id="rules:no-impact",
            cost_rule_id="rules:no-impact",
            quantity_confidence=1.0,
            cost_confidence=1.0,
            matching_strategy="deterministic_no_impact",
            evidence_ids=(),
            reason="Blank work name or both remaining values are absent/zero",
            requires_manual_review=False,
            status=Status.OK,
            warnings=(),
        )

    @staticmethod
    def _exclude_negative(row: DrawingSourceRow) -> MatchDecision:
        return MatchDecision(
            row_id=row.row_id,
            category=None,
            quantity_decision="exclude",
            cost_decision="exclude",
            quantity_rule_id="rules:confirmed-negative",
            cost_rule_id="rules:confirmed-negative",
            quantity_confidence=0.99,
            cost_confidence=0.99,
            matching_strategy="deterministic_negative",
            evidence_ids=(),
            reason="Confirmed negative category rule",
            requires_manual_review=False,
            status=Status.OK,
            warnings=(),
        )

    def _deterministic(self, row: DrawingSourceRow, text: str, rule: CategoryRule) -> MatchDecision:
        cost_only = _has_any(text, rule.cost_only_any)
        quantity_only = _has_any(text, rule.quantity_only_any)
        compatible = _unit_is_compatible(row.unit_raw, rule)
        warnings: list[str] = []
        quantity = (
            "include" if row.remaining_quantity not in (None, 0) and not cost_only else "exclude"
        )
        if quantity == "include" and not compatible:
            quantity = "review"
            warnings.append(Status.UNIT_MISMATCH)
        cost = (
            "include"
            if row.remaining_total_cost not in (None, 0) and not quantity_only
            else "exclude"
        )
        review = quantity == "review"
        rule_id = f"rules:{self.rules.version}:{rule.category.value}"
        return MatchDecision(
            row_id=row.row_id,
            category=rule.category,
            quantity_decision=quantity,
            cost_decision=cost,
            quantity_rule_id=rule_id if quantity != "exclude" else None,
            cost_rule_id=rule_id if cost != "exclude" else None,
            quantity_confidence=0.99 if quantity == "include" else (0.5 if review else None),
            cost_confidence=0.99 if cost == "include" else None,
            matching_strategy="deterministic_rules",
            evidence_ids=(),
            reason="Confirmed deterministic include/exclude rules",
            requires_manual_review=review,
            status=Status.UNIT_MISMATCH if review else Status.OK,
            warnings=tuple(str(item) for item in warnings),
        )

    @staticmethod
    def _review(
        row: DrawingSourceRow,
        *,
        category: TargetWorkCategory | None = None,
        reason: str,
        warnings: tuple[str, ...],
        evidence_ids: tuple[str, ...] = (),
        confidence: float | None = None,
    ) -> MatchDecision:
        return MatchDecision(
            row_id=row.row_id,
            category=category,
            quantity_decision="review",
            cost_decision="review",
            quantity_rule_id=None,
            cost_rule_id=None,
            quantity_confidence=confidence,
            cost_confidence=confidence,
            matching_strategy="review",
            evidence_ids=evidence_ids,
            reason=reason,
            requires_manual_review=True,
            status=Status.UNCONFIRMED_CLASSIFICATION,
            warnings=tuple(str(item) for item in warnings),
        )

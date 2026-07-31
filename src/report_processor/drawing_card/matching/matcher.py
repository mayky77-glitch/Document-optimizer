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
)
from .semantic import SemanticExampleRetriever

if TYPE_CHECKING:
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
    "ростверк",
    "металлоконструк",
    "м/к",
    "тсг",
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
    "срезка тсг",
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
    "кабельный лоток",
    "кабельных лотков",
    "кабельных коробов",
    "кабельных стоек",
    "заземляющ",
    "под кабельную продукцию",
    "опорных конструкций для крепления трубопроводов",
)

_CONFIRMED_NEGATIVE_ALL = (
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
)

_EXACT_TOKEN_PHRASES = {
    "зра",
    "тсг",
    "волс",
    "кип",
    "м/к",
    "монтаж",
    "устройство",
    "испытание",
    "контроль",
    "обследование",
    "извлечение",
    "ремонт",
    "ревизия",
}


@lru_cache(maxsize=256)
def _exact_token_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w/]){re.escape(phrase)}(?![\w/])", re.IGNORECASE)


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized = normalize_text(phrase)
    if not normalized:
        return False
    if normalized in _EXACT_TOKEN_PHRASES:
        return _exact_token_pattern(normalized).search(text) is not None
    return normalized in text


def _has_target_cue(text: str) -> bool:
    if any(_contains_phrase(text, token) for token in _TARGET_CUES):
        return True
    cable_context = _has_any(text, ("кабел", "провод", "прокладк", "сет"))
    electrical_context = _has_any(text, ("силов", "слаботоч", "кип", "автоматик"))
    return cable_context and electrical_context


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _has_confirmed_negative(text: str) -> bool:
    if _has_any(text, _CONFIRMED_NEGATIVE_PHRASES):
        return True
    return any(
        all(_contains_phrase(text, token) for token in group) for group in _CONFIRMED_NEGATIVE_ALL
    )


def _rule_matches(text: str, rule: CategoryRule) -> bool:
    if _has_any(text, rule.exclude_any):
        return False
    exact_groups = any(
        all(_contains_phrase(text, token) for token in group) for group in rule.include_all
    )
    return exact_groups or _has_any(text, rule.include_any)


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
        matched = [rule for rule in self.rules.categories if _rule_matches(text, rule)]
        if len(matched) == 1:
            return self._deterministic(row, text, matched[0])
        if len(matched) > 1:
            return self._review(
                row,
                reason="Several deterministic categories matched",
                warnings=("MULTIPLE_CATEGORY_MATCHES",),
            )
        exact = exact_example_match(
            text,
            self.examples,
            unit=row.unit_raw,
            source_type=row.source_document_type,
        )
        if exact is not None:
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
        if _has_confirmed_negative(text):
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

    def _deterministic(self, row: DrawingSourceRow, text: str, rule: CategoryRule) -> MatchDecision:
        cost_only = _has_any(text, rule.cost_only_any)
        quantity_only = _has_any(text, rule.quantity_only_any)
        compatible = _unit_is_compatible(row.unit_raw, rule)
        warnings: list[str] = []
        quantity = "include" if row.remaining_quantity is not None and not cost_only else "exclude"
        if quantity == "include" and not compatible:
            quantity = "review"
            warnings.append(Status.UNIT_MISMATCH)
        cost = (
            "include" if row.remaining_total_cost is not None and not quantity_only else "exclude"
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
    ) -> MatchDecision:
        return MatchDecision(
            row_id=row.row_id,
            category=category,
            quantity_decision="review",
            cost_decision="review",
            quantity_rule_id=None,
            cost_rule_id=None,
            quantity_confidence=None,
            cost_confidence=None,
            matching_strategy="review",
            evidence_ids=evidence_ids,
            reason=reason,
            requires_manual_review=True,
            status=Status.UNCONFIRMED_CLASSIFICATION,
            warnings=tuple(str(item) for item in warnings),
        )

"""Deterministic, private, offline descriptions of reconciliation evidence.

This module deliberately has no dependency on the reconciliation pipeline.  A
trusted exporter produces the small JSONL input; Wave 3 only describes it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from contextlib import suppress
from dataclasses import asdict, dataclass, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from report_processor.work_semantics import DEFAULT_ONTOLOGY, canonicalize_term
from report_processor.work_semantics.semantic_skeleton import build_semantic_skeleton

CORPUS_SCHEMA_VERSION = "ReconciliationCorpus-1.0"
CONFIRMED_OUTCOME_VERSION = "ConfirmedOutcome-1.0"
PROFILE_SCHEMA_VERSION = "ReconciliationCorpusProfile-1.0"
PATTERN_CANDIDATE_VERSION = "PatternCandidate-1.0"
CANDIDATE_SET_VERSION = "PatternCandidateSet-1.0"
CANDIDATE_EVALUATION_VERSION = "PatternCandidateEvaluation-1.0"
DEFAULT_PROFILE_TOP = 100
DEFAULT_MIN_SUPPORT_ATOMS = 2
MAX_SUPPORT_REFS = 10
_SHA = re.compile(r"sha256:[0-9a-f]{64}\Z")


class CandidateKind(StrEnum):
    SYNONYM_ABBREVIATION = "synonym_abbreviation"
    SLOT_TEMPLATE = "slot_template"
    INCLUDE_EXCLUDE = "include_exclude"
    SPLIT_MERGE = "split_merge"
    CRITICAL_MODIFIER = "critical_modifier"
    MUST_LINK_CANNOT_LINK = "must_link_cannot_link"
    CATEGORY_SPECIFIC_NORMALIZATION = "category_specific_normalization"


_KINDS = tuple(member.value for member in CandidateKind)
_PRIVATE = {
    "audit_text",
    "record_id",
    "document_set_id",
    "manual_action_id",
    "apply_fingerprint",
    "result_fingerprint",
    "unit",
}
_PRIVATE_KEY_PARTS = frozenset(
    {
        "path",
        "filename",
        "file_name",
        "extension",
        "formula",
        "cell",
        "coordinate",
        "comment",
        "fragment",
        "provenance",
        "quantity",
        "cost",
        "workbook",
        "source_digest",
        "target_digest",
    }
)
_FILENAME = re.compile(r"(?u)(?:^|[\s\"'(])[^\s/\\]+\.[\w]{1,12}(?:$|[\s\"'),;:])")
_VERSION_TOKEN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*-\d+\.\d+$")
_CELL_COORDINATE = re.compile(r"(?<![A-Za-z0-9])(?:\$?[A-Z]{1,3}\$?\d+|R\d+C\d+)(?![A-Za-z0-9])")
_FORMULA = re.compile(r"(?i)(?:^\s*=|\b(?:sum|if|vlookup|xlookup|сумм|если)\s*\()")
_COMMENT_FRAGMENT = re.compile(
    r"(?i)(?:<!--|/\*|\*/|//|#\s|\bcomment\b|\bfragment\b|\bкомментар\w*\b|\bфрагмент\w*\b)"
)
_ROW_COORDINATE = re.compile(r"(?i)\b(?:row|строка)\s*(?:[:#№]|no\.?|n)?\s*\d+\b")
_PROVENANCE = re.compile(r"(?i)(?:\bprovenance\b|\bsource[ _-]?digest\b|\bисточник\w*\b)")
_RAW_PARAMETER = re.compile(r"(?i)(?<![\w.])\d+\s*[xх×]\s*\d+(?:[.,]\d+)?(?![\w.])")


class OfflineContractError(ValueError):
    """Stable contract failure, deliberately without untrusted values."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CorpusVersions:
    term_canonicalization: str
    domain_ontology: str
    unit_ontology: str
    typed_slots: str
    semantic_skeleton: str
    category_catalog: str
    rule_catalog: str
    outcome_export: str


@dataclass(frozen=True, slots=True)
class ConfirmedOutcome:
    version: str
    action: Literal["accept", "reject"]
    mode: str | None
    target_category: str | None
    apply_fingerprint: str
    result_fingerprint: str
    kind: str = "confirmed_authoritative"


@dataclass(frozen=True, slots=True)
class CorpusRecord:
    record_id: str
    record_fingerprint: str
    document_set_id: str
    document_type: str | None
    audit_text: str
    unit: str | None
    category: str | None
    mode: str | None
    object_kind: str | None
    eligibility: str
    resolution: str
    manual_action_id: str | None
    matched_rule_ids: tuple[str, ...]
    outcome: ConfirmedOutcome | None


@dataclass(frozen=True, slots=True)
class CorpusSnapshot:
    corpus_fingerprint: str
    rule_ids: tuple[str, ...]
    versions: CorpusVersions
    records: tuple[CorpusRecord, ...]
    version: str = CORPUS_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class OutcomeSignature:
    action: str
    mode: str | None
    target_category: str | None


@dataclass(frozen=True, slots=True)
class PatternScope:
    category: str | None = None
    mode: str | None = None
    unit_family: str | None = None
    action: str | None = None
    object_kind: str | None = None
    document_type: str | None = None


@dataclass(frozen=True, slots=True)
class SupportSummary:
    support_atom_count: int
    semantic_identity_count: int
    document_set_count: int
    confirmed_record_count: int
    contradictory_atom_count: int
    support_refs: tuple[str, ...]

    @property
    def contradiction_count(self) -> int:
        """Compatibility read alias; canonical serialization uses the frozen name."""
        return self.contradictory_atom_count


@dataclass(frozen=True, slots=True)
class SynonymAbbreviationProposal:
    variants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SlotTemplateProposal:
    skeleton: str
    slot_signatures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IncludeExcludeProposal:
    predicate: str
    polarity: str


@dataclass(frozen=True, slots=True)
class SplitMergeProposal:
    variants: tuple[str, ...]
    relation: str


@dataclass(frozen=True, slots=True)
class CriticalModifierProposal:
    modifier: str
    disposition: str = "hard_boundary_review"


@dataclass(frozen=True, slots=True)
class MustLinkCannotLinkProposal:
    relation: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CategorySpecificNormalizationProposal:
    rewrite_from: str
    rewrite_to: str
    target_category: str


Proposal = (
    SynonymAbbreviationProposal
    | SlotTemplateProposal
    | IncludeExcludeProposal
    | SplitMergeProposal
    | CriticalModifierProposal
    | MustLinkCannotLinkProposal
    | CategorySpecificNormalizationProposal
)


@dataclass(frozen=True, slots=True)
class PatternCandidate:
    record_type: str
    candidate_id: str
    kind: CandidateKind
    scope: PatternScope
    proposal: Proposal
    expected_outcome: OutcomeSignature | None
    support: SupportSummary
    risk_codes: tuple[str, ...]
    fingerprint: str
    state: str = "proposed"
    descriptive_only: bool = True
    requires_owner_review: bool = True
    version: str = PATTERN_CANDIDATE_VERSION


@dataclass(frozen=True, slots=True)
class CandidateSet:
    source_corpus_fingerprint: str
    candidates: tuple[PatternCandidate, ...]
    version: str = CANDIDATE_SET_VERSION


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    candidate_id: str
    matched_atom_count: int
    matched_semantic_identity_count: int
    matched_document_set_count: int
    confirmed_support_atom_count: int
    confirmed_contradiction_atom_count: int
    unresolved_match_atom_count: int
    hard_boundary_mismatch_count: int
    parse_warning_atom_count: int
    agreement: Rational
    risk_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateEvaluationReport:
    source_corpus_fingerprint: str
    evaluations: tuple[CandidateEvaluation, ...]
    evaluation_mode: str = "descriptive_same_corpus"
    promotion_eligible: bool = False
    version: str = CANDIDATE_EVALUATION_VERSION


@dataclass(frozen=True, slots=True)
class Rational:
    """An exact public ratio; floats are intentionally never part of Wave 3."""

    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class FrequencyItem:
    value: str
    occurrence_count: int
    support_atom_count: int
    semantic_identity_count: int
    document_set_count: int


@dataclass(frozen=True, slots=True)
class RankedSection:
    items: tuple[FrequencyItem, ...]
    total_distinct: int
    truncated: int


@dataclass(frozen=True, slots=True)
class VariantSetItem:
    variants: tuple[str, ...]
    outcome: OutcomeSignature
    occurrence_count: int
    support_atom_count: int
    semantic_identity_count: int
    document_set_count: int


@dataclass(frozen=True, slots=True)
class VariantSetSection:
    items: tuple[VariantSetItem, ...]
    total_distinct: int
    truncated: int


@dataclass(frozen=True, slots=True)
class ManualActionDriver:
    skeleton: str
    term: str
    unique_manual_action_count: int
    occurrence_count: int
    support_atom_count: int
    semantic_identity_count: int
    document_set_count: int


@dataclass(frozen=True, slots=True)
class ManualActionDriverSection:
    items: tuple[ManualActionDriver, ...]
    total_distinct: int
    truncated: int


@dataclass(frozen=True, slots=True)
class CorpusCounts:
    record_count: int
    review_relevant_count: int
    confirmed_count: int
    manual_unresolved_count: int
    exact_resolved_count: int
    not_applicable_count: int


@dataclass(frozen=True, slots=True)
class OntologyCoverage:
    review_relevant_denominator: int
    known_action_count: int
    known_object_count: int
    known_unit_count: int
    full_coverage_count: int
    parse_warning_count: int
    semantic_conflict_count: int
    known_action_ratio: Rational
    known_object_ratio: Rational
    known_unit_ratio: Rational
    full_coverage_ratio: Rational
    token_denominator: int
    known_ontology_token_count: int
    slotted_token_count: int
    known_ontology_token_ratio: Rational
    slotted_token_ratio: Rational


@dataclass(frozen=True, slots=True)
class RuleCoverageItem:
    rule_id: str
    occurrence_count: int
    support_atom_count: int
    semantic_identity_count: int
    document_set_count: int
    coverage_ratio: Rational


@dataclass(frozen=True, slots=True)
class RuleCoverage:
    items: tuple[RuleCoverageItem, ...]
    review_relevant_denominator: int


@dataclass(frozen=True, slots=True)
class CorpusProfile:
    source_corpus_fingerprint: str
    corpus_counts: CorpusCounts
    uncovered_tokens: RankedSection
    uncovered_ngrams: RankedSection
    unknown_actions: RankedSection
    unknown_objects: RankedSection
    unknown_units: RankedSection
    near_name_pairs: RankedSection
    same_outcome_variant_sets: VariantSetSection
    manual_action_drivers: ManualActionDriverSection
    ontology_coverage: OntologyCoverage
    rule_coverage: RuleCoverage
    version: str = PROFILE_SCHEMA_VERSION


def _plain(value: object) -> object:
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset, set)):
        return [_plain(item) for item in value]
    return value


def canonical_json_bytes(value: object) -> bytes:
    """Render canonical JSON while rejecting non-JSON numeric values."""
    try:
        plain = _plain(value)
        _reject_floats(plain)
        return json.dumps(
            plain,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OfflineContractError(
            "INVARIANT_VIOLATION", "canonical JSON invariant failed"
        ) from exc


def _reject_floats(value: object) -> None:
    """The contract has integer counts and rational pairs only; floats are never canonical."""
    if isinstance(value, float):
        raise OfflineContractError("INVARIANT_VIOLATION", "canonical JSON invariant failed")
    if isinstance(value, dict):
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, (tuple, list, frozenset, set)):
        for item in value:
            _reject_floats(item)


def _contains_float(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(item) for item in value)
    return False


def fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _required(mapping: dict[str, Any], keys: set[str]) -> None:
    if set(mapping) != keys:
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")


def _hash(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    return value


def _text(value: object, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    return value


def _nonempty_text(value: object, *, nullable: bool = False) -> str | None:
    text = _text(value, nullable=nullable)
    if text is not None and not text:
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    return text


def _controlled(value: object, allowed: frozenset[str], *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    return value


def _versions(value: object) -> CorpusVersions:
    if not isinstance(value, dict):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    names = {field for field in CorpusVersions.__dataclass_fields__}
    _required(value, names)
    versions = CorpusVersions(**{name: _nonempty_text(value[name]) for name in names})  # type: ignore[arg-type]
    expected = (
        "TermCanonicalization-2.0",
        "DomainOntology-1.0",
        "UnitOntology-1.1",
        "TypedSlots-1.0",
        "SemanticSkeleton-1.0",
        CONFIRMED_OUTCOME_VERSION,
    )
    if (
        (
            versions.term_canonicalization,
            versions.domain_ontology,
            versions.unit_ontology,
            versions.typed_slots,
            versions.semantic_skeleton,
            versions.outcome_export,
        )
        != expected
        or not versions.category_catalog
        or not versions.rule_catalog
    ):
        raise OfflineContractError("INPUT_VERSION_UNSUPPORTED", "input version is unsupported")
    return versions


def _outcome(value: object) -> ConfirmedOutcome | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    _required(
        value,
        {
            "version",
            "kind",
            "action",
            "mode",
            "target_category",
            "apply_fingerprint",
            "result_fingerprint",
        },
    )
    action = _controlled(value["action"], frozenset({"accept", "reject"}))
    mode = _controlled(value["mode"], frozenset({"quantity_cost", "cost_only"}), nullable=True)
    target_category = _nonempty_text(value["target_category"], nullable=True)
    outcome = ConfirmedOutcome(
        _nonempty_text(value["version"]),
        action,  # type: ignore[arg-type]
        mode,
        target_category,
        _hash(value["apply_fingerprint"]),
        _hash(value["result_fingerprint"]),
        _nonempty_text(value["kind"]),
    )
    if (
        outcome.version != CONFIRMED_OUTCOME_VERSION
        or outcome.kind != "confirmed_authoritative"
        or outcome.action not in {"accept", "reject"}
        or (
            outcome.action == "accept"
            and (outcome.mode not in {"quantity_cost", "cost_only"} or not outcome.target_category)
        )
        or (
            outcome.action == "reject"
            and (outcome.mode is not None or outcome.target_category is not None)
        )
    ):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    return outcome


def _record(value: object, rule_ids: tuple[str, ...]) -> CorpusRecord:
    if not isinstance(value, dict):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    names = {
        "record_type",
        "record_id",
        "record_fingerprint",
        "document_set_id",
        "document_type",
        "audit_text",
        "unit",
        "category",
        "mode",
        "object_kind",
        "eligibility",
        "resolution",
        "manual_action_id",
        "matched_rule_ids",
        "outcome",
    }
    _required(value, names)
    if value["record_type"] != "row":
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    mode = _controlled(value["mode"], frozenset({"quantity_cost", "cost_only"}), nullable=True)
    eligibility = _controlled(
        value["eligibility"],
        frozenset({"review_relevant", "excluded_hazard", "zero_ephemeral", "unsupported"}),
    )
    resolution = _controlled(
        value["resolution"],
        frozenset({"confirmed", "manual_unresolved", "exact_resolved", "not_applicable"}),
    )
    matched = value["matched_rule_ids"]
    if (
        not isinstance(matched, list)
        or not all(isinstance(item, str) and item for item in matched)
        or tuple(matched) != tuple(sorted(set(matched)))
        or not set(matched) <= set(rule_ids)
    ):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    outcome = _outcome(value["outcome"])
    manual = _nonempty_text(value["manual_action_id"], nullable=True)
    if manual is not None:
        _hash(manual)
    if (
        (resolution == "confirmed") != (outcome is not None)
        or (
            resolution == "manual_unresolved"
            and (eligibility != "review_relevant" or manual is None)
        )
        or (resolution != "manual_unresolved" and manual is not None)
    ):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    record = CorpusRecord(
        _hash(value["record_id"]),
        _hash(value["record_fingerprint"]),
        _hash(value["document_set_id"]),
        _nonempty_text(value["document_type"], nullable=True),
        _nonempty_text(value["audit_text"]),
        _nonempty_text(value["unit"], nullable=True),
        _nonempty_text(value["category"], nullable=True),
        mode,
        _nonempty_text(value["object_kind"], nullable=True),
        eligibility,  # type: ignore[arg-type]
        resolution,  # type: ignore[arg-type]
        manual,
        tuple(matched),
        outcome,
    )  # type: ignore[arg-type]
    if record.record_fingerprint != fingerprint(_record_fingerprint_material(record)):
        raise OfflineContractError("INPUT_FINGERPRINT_MISMATCH", "input fingerprint does not match")
    return record


def _record_fingerprint_material(record: CorpusRecord) -> object:
    """Stable canonical row material, deliberately excluding its own fingerprint."""
    return {
        "record_type": "row",
        "record_id": record.record_id,
        "document_set_id": record.document_set_id,
        "document_type": record.document_type,
        "audit_text": record.audit_text,
        "unit": record.unit,
        "category": record.category,
        "mode": record.mode,
        "object_kind": record.object_kind,
        "eligibility": record.eligibility,
        "resolution": record.resolution,
        "manual_action_id": record.manual_action_id,
        "matched_rule_ids": record.matched_rule_ids,
        "outcome": record.outcome,
    }


def load_corpus_jsonl(path: Path) -> CorpusSnapshot:
    try:
        if not path.exists():
            raise OfflineContractError("INPUT_NOT_FOUND", "input is absent")
        if not path.is_file():
            raise OfflineContractError("INPUT_NOT_REGULAR", "input is not a regular file")
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise OfflineContractError("INPUT_NOT_FOUND", "input is absent") from exc
    except OSError as exc:
        raise OfflineContractError("INPUT_NOT_REGULAR", "input is not readable") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OfflineContractError("INPUT_INVALID_UTF8", "input is not UTF-8") from exc
    if not text.endswith("\n") or "\r" in text or not text.strip():
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    try:
        rows = [
            json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            for line in text.splitlines()
        ]
    except (json.JSONDecodeError, ValueError) as exc:
        raise OfflineContractError("INPUT_INVALID_JSON", "input JSON is invalid") from exc
    if any(_contains_float(row) for row in rows):
        raise OfflineContractError("INPUT_INVALID_JSON", "input JSON is invalid")
    if not rows or not isinstance(rows[0], dict):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    header = rows[0]
    _required(
        header, {"record_type", "schema_version", "corpus_fingerprint", "rule_ids", "versions"}
    )
    if (
        header["record_type"] != "header"
        or header["schema_version"] != CORPUS_SCHEMA_VERSION
        or not isinstance(header["rule_ids"], list)
        or not all(isinstance(x, str) and x for x in header["rule_ids"])
        or tuple(header["rule_ids"]) != tuple(sorted(set(header["rule_ids"])))
    ):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    versions = _versions(header["versions"])
    rule_ids = tuple(header["rule_ids"])
    records = tuple(
        sorted((_record(row, rule_ids) for row in rows[1:]), key=lambda record: record.record_id)
    )
    if len({record.record_id for record in records}) != len(records):
        raise OfflineContractError("INPUT_SCHEMA_INVALID", "input schema is invalid")
    snap = CorpusSnapshot(_hash(header["corpus_fingerprint"]), rule_ids, versions, records)
    expected = fingerprint(_corpus_material(snap))
    if snap.corpus_fingerprint != expected:
        raise OfflineContractError("INPUT_FINGERPRINT_MISMATCH", "input fingerprint does not match")
    return snap


def _corpus_material(corpus: CorpusSnapshot) -> object:
    return {
        "schema_version": corpus.version,
        "rule_ids": corpus.rule_ids,
        "versions": corpus.versions,
        "rows": corpus.records,
    }


def _facts(corpus: CorpusSnapshot) -> list[dict[str, object]]:
    facts = []
    for record in corpus.records:
        canon = canonicalize_term(
            record.audit_text,
            category=record.category,
            object_kind=record.object_kind,
            ontology=DEFAULT_ONTOLOGY,
        )
        skeleton = build_semantic_skeleton(
            record.audit_text, category=record.category, object_kind=record.object_kind
        )
        unit = DEFAULT_ONTOLOGY.unit_identity(record.unit)
        slots = tuple(
            (slot.kind.value, slot.impact.value, slot.normalized)
            for slot in skeleton.slots
            if slot.impact != "display_only"
        )
        identity = fingerprint(
            {
                "text": canon.semantic_text,
                "skeleton": skeleton.skeleton_text,
                "unit": unit.canonical_unit,
                "exact_only": unit.exact_only,
                "slots": slots,
                "versions": {
                    "term": corpus.versions.term_canonicalization,
                    "ontology": corpus.versions.domain_ontology,
                    "unit": corpus.versions.unit_ontology,
                    "typed": corpus.versions.typed_slots,
                    "skeleton": corpus.versions.semantic_skeleton,
                },
            }
        )
        labels = DEFAULT_ONTOLOGY.labels(canon.semantic_text, category=record.category)
        facts.append(
            {
                "record": record,
                "canon": canon,
                "skeleton": skeleton,
                "unit": unit,
                "identity": identity,
                "labels": labels,
                "slots": slots,
                "private_text": _source_private_text(record.audit_text),
            }
        )
    return facts


def _looks_private_text(value: str) -> bool:
    filename = _FILENAME.search(value)
    return bool(
        "/" in value
        or "\\" in value
        or bool(re.match(r"^[A-Za-z]:", value))
        or (filename and not _VERSION_TOKEN.fullmatch(value.strip()))
        or _CELL_COORDINATE.search(value)
        or _FORMULA.search(value)
        or _COMMENT_FRAGMENT.search(value)
        or _ROW_COORDINATE.search(value)
        or _PROVENANCE.search(value)
        or _RAW_PARAMETER.search(value)
    )


def _source_private_text(value: str) -> bool:
    """Classify source metadata while leaving typed parameters available internally."""
    return _looks_private_text(_RAW_PARAMETER.sub("parameter", value))


def _section(counter: Counter[str], facts: list[dict[str, object]], top: int) -> RankedSection:
    """Freeze a ranked descriptive section from ephemeral internal facts."""
    atoms: dict[str, set[tuple[str, str]]] = defaultdict(set)
    docs: dict[str, set[str]] = defaultdict(set)
    identities: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        key = fact.get("key")
        if not isinstance(key, str):
            continue
        rec = fact["record"]
        assert isinstance(rec, CorpusRecord)
        atoms[key].add((str(fact["identity"]), rec.document_set_id))
        docs[key].add(rec.document_set_id)
        identities[key].add(str(fact["identity"]))
    ordered = sorted(counter, key=lambda k: (-len(atoms[k]), -counter[k], k, fingerprint(k)))
    return RankedSection(
        tuple(
            FrequencyItem(
                key,
                counter[key],
                len(atoms[key]),
                len(identities[key]),
                len(docs[key]),
            )
            for key in ordered[:top]
        ),
        len(ordered),
        max(0, len(ordered) - top),
    )


def _atom(fact: dict[str, object]) -> tuple[str, str]:
    record = fact["record"]
    assert isinstance(record, CorpusRecord)
    return str(fact["identity"]), record.document_set_id


def _is_known_ontology_token(token: str) -> bool:
    labels = DEFAULT_ONTOLOGY.labels(token)
    return labels.primary_action is not None or labels.primary_object is not None


def _known_ontology_tokens(fact: dict[str, object]) -> frozenset[str]:
    """Recognize ontology aliases/stems in the source language, including Russian forms."""
    return frozenset(token for token in fact["canon"].tokens if _is_known_ontology_token(token))


def _uncovered_tokens(fact: dict[str, object]) -> tuple[str, ...]:
    """Tokens not classified by ontology or captured in a non-display slot."""
    labels = _known_ontology_tokens(fact)
    slot_tokens = {part for _, _, normalized in fact["slots"] for part in str(normalized).split()}
    return tuple(
        token
        for token in fact["canon"].tokens
        if (
            token not in labels and token not in slot_tokens and not _RAW_PARAMETER.fullmatch(token)
        )
    )


def _rational(numerator: int, denominator: int) -> Rational:
    return Rational(numerator, denominator)


def _audit_form(fact: dict[str, object]) -> str:
    """Retain safe punctuation/parameter distinctions instead of semantic normalization."""
    record = fact["record"]
    assert isinstance(record, CorpusRecord)
    return " ".join(record.audit_text.casefold().split())


def _public_text(value: str) -> str:
    """Retain the safe lexical form while replacing raw typed parameter values."""
    return _RAW_PARAMETER.sub("<parameter>", value)


def _public_audit_form(fact: dict[str, object]) -> str:
    return _public_text(_audit_form(fact))


def _slot_signature(fact: dict[str, object]) -> str:
    """Keep slot variants distinguishable without serializing their raw values."""
    return fingerprint({"salt": "reconciliation-slot-signature-v1", "slots": fact["slots"]})


def _parameter_signature(fact: dict[str, object]) -> str:
    """Salt a bare parameter value before it can participate in public descriptions."""
    return fingerprint(
        {
            "salt": "reconciliation-parameter-signature-v1",
            "parameters": tuple(_RAW_PARAMETER.findall(_audit_form(fact))),
        }
    )


def _parameter_near(left: dict[str, object], right: dict[str, object]) -> bool:
    """Recognize equal typed structure whose parameter values differ."""
    left_slots = tuple((kind, impact) for kind, impact, _ in left["slots"])
    right_slots = tuple((kind, impact) for kind, impact, _ in right["slots"])
    typed_near = bool(
        left_slots
        and left_slots == right_slots
        and _slot_signature(left) != _slot_signature(right)
        and left["skeleton"].skeleton_text == right["skeleton"].skeleton_text
    )
    left_parameters = tuple(_RAW_PARAMETER.findall(_audit_form(left)))
    right_parameters = tuple(_RAW_PARAMETER.findall(_audit_form(right)))
    bare_near = bool(
        left_parameters
        and right_parameters
        and left_parameters != right_parameters
        and _public_audit_form(left) == _public_audit_form(right)
    )
    return typed_near or bare_near


def _outcome_signature(record: CorpusRecord) -> OutcomeSignature:
    assert record.outcome is not None
    return OutcomeSignature(
        record.outcome.action, record.outcome.mode, record.outcome.target_category
    )


def _scope_key(fact: dict[str, object]) -> tuple[object, ...]:
    """The complete non-outcome compatibility boundary for a candidate."""
    record = fact["record"]
    assert isinstance(record, CorpusRecord)
    labels = fact["labels"]
    return (
        record.category,
        record.mode,
        fact["unit"].family,
        labels.primary_action,
        labels.primary_object,
        record.document_type,
    )


def profile_corpus(corpus: CorpusSnapshot, *, top: int = DEFAULT_PROFILE_TOP) -> CorpusProfile:
    if isinstance(top, bool) or not isinstance(top, int) or top < 1:
        raise OfflineContractError("INVARIANT_VIOLATION", "profile invariant failed")
    # Privacy-looking values are excluded from public descriptions, never from
    # review-relevant aggregate denominators.
    review_facts = [
        fact for fact in _facts(corpus) if fact["record"].eligibility == "review_relevant"
    ]
    facts = [fact for fact in review_facts if not fact["private_text"]]

    def collect(selector: Any) -> dict[str, object]:
        selected = []
        counts: Counter[str] = Counter()
        for fact in facts:
            key = selector(fact)
            if key:
                copy = dict(fact)
                copy["key"] = str(key)
                selected.append(copy)
                counts[str(key)] += 1
        return _section(counts, selected, top)

    def unknown_action(fact: dict[str, object]) -> str | None:
        labels = fact["labels"]
        return (
            _public_text(str(fact["canon"].semantic_text))
            if labels.primary_action is None
            else None
        )

    def unknown_object(fact: dict[str, object]) -> str | None:
        labels = fact["labels"]
        return (
            _public_text(str(fact["canon"].semantic_text))
            if labels.primary_object is None
            else None
        )

    records = corpus.records
    token_counter = Counter(
        token for fact in facts for token in _uncovered_tokens(fact) if len(token) > 1
    )
    token_facts = []
    for fact in facts:
        for token in _uncovered_tokens(fact):
            if len(token) > 1:
                copy = dict(fact)
                copy["key"] = token
                token_facts.append(copy)
    ngram_counter: Counter[str] = Counter()
    ngram_facts = []
    for fact in facts:
        tokens = tuple(fact["canon"].tokens)
        uncovered = set(_uncovered_tokens(fact))
        for width in (2, 3):
            for i in range(max(0, len(tokens) - width + 1)):
                window = tokens[i : i + width]
                if not all(token in uncovered for token in window):
                    continue
                value = " ".join(window)
                ngram_counter[value] += 1
                copy = dict(fact)
                copy["key"] = value
                ngram_facts.append(copy)
    manual_groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        record = fact["record"]
        assert isinstance(record, CorpusRecord)
        if record.resolution == "manual_unresolved":
            manual_groups[
                (
                    str(fact["skeleton"].skeleton_text),
                    _public_text(str(fact["canon"].semantic_text)),
                )
            ].append(fact)
    manual_items = []
    for (skeleton, term), entries in manual_groups.items():
        atoms = {_atom(entry) for entry in entries}
        identities = {atom[0] for atom in atoms}
        docs = {atom[1] for atom in atoms}
        actions = {entry["record"].manual_action_id for entry in entries}
        manual_items.append(
            ManualActionDriver(
                skeleton, term, len(actions), len(entries), len(atoms), len(identities), len(docs)
            )
        )
    manual_items.sort(
        key=lambda item: (
            -item.unique_manual_action_count,
            -item.support_atom_count,
            -item.occurrence_count,
            item.skeleton,
            item.term,
            fingerprint((item.skeleton, item.term)),
        )
    )
    near_counter: Counter[str] = Counter()
    near_facts: list[dict[str, object]] = []
    by_audit_form: dict[str, list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        by_audit_form[_audit_form(fact)].append(fact)
    names = sorted(by_audit_form)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            pair = by_audit_form[left] + by_audit_form[right]
            parameter_near = any(
                _parameter_near(left_fact, right_fact)
                for left_fact in by_audit_form[left]
                for right_fact in by_audit_form[right]
            )
            if _lexical_near(left, right) or parameter_near:
                public_left = _public_text(left)
                public_right = _public_text(right)
                if parameter_near and public_left == public_right:
                    left_fact, right_fact = by_audit_form[left][0], by_audit_form[right][0]
                    left_signature = (
                        _slot_signature(left_fact)
                        if left_fact["slots"]
                        else _parameter_signature(left_fact)
                    )
                    right_signature = (
                        _slot_signature(right_fact)
                        if right_fact["slots"]
                        else _parameter_signature(right_fact)
                    )
                    public_left = f"parameter_variant:{left_signature}"
                    public_right = f"parameter_variant:{right_signature}"
                key = f"{public_left} | {public_right}"
                near_counter[key] += len(pair)
                near_facts.extend({**fact, "key": key} for fact in pair)
    variant_groups: dict[tuple[tuple[object, ...], OutcomeSignature], list[dict[str, object]]] = (
        defaultdict(list)
    )
    for fact in facts:
        record = fact["record"]
        if record.resolution == "confirmed" and record.outcome is not None:
            variant_groups[(_scope_key(fact), _outcome_signature(record))].append(fact)
    variant_items: list[VariantSetItem] = []
    for (_, outcome), entries in variant_groups.items():
        variants = tuple(sorted({_public_audit_form(entry) for entry in entries}))
        atoms = {_atom(entry) for entry in entries}
        identities = {atom[0] for atom in atoms}
        if len(variants) < 2 or len(identities) < 2:
            continue
        variant_items.append(
            VariantSetItem(
                variants,
                outcome,
                len(entries),
                len(atoms),
                len(identities),
                len({atom[1] for atom in atoms}),
            )
        )
    variant_items.sort(
        key=lambda item: (
            -item.support_atom_count,
            -item.occurrence_count,
            item.variants,
            fingerprint((item.variants, item.outcome)),
        )
    )
    review_count = len(review_facts)
    known_action = sum(fact["labels"].primary_action is not None for fact in review_facts)
    known_object = sum(fact["labels"].primary_object is not None for fact in review_facts)
    known_unit = sum(not fact["unit"].exact_only for fact in review_facts)
    full = sum(
        fact["labels"].primary_action is not None
        and fact["labels"].primary_object is not None
        and not fact["unit"].exact_only
        and not fact["skeleton"].warnings
        and not fact["skeleton"].conflicts
        for fact in review_facts
    )
    token_total = sum(len(fact["canon"].tokens) for fact in review_facts)
    known_token_count = sum(
        sum(_is_known_ontology_token(token) for token in fact["canon"].tokens)
        for fact in review_facts
    )
    slot_token_count = sum(
        sum(len(str(slot[2]).split()) for slot in fact["slots"]) for fact in review_facts
    )
    rule_items = []
    for rule in corpus.rule_ids:
        entries = [fact for fact in review_facts if rule in fact["record"].matched_rule_ids]
        atoms = {_atom(entry) for entry in entries}
        rule_items.append(
            RuleCoverageItem(
                rule,
                len(entries),
                len(atoms),
                len({atom[0] for atom in atoms}),
                len({atom[1] for atom in atoms}),
                _rational(len(atoms), review_count),
            )
        )
    rule_items.sort(key=lambda item: item.rule_id)
    return CorpusProfile(
        corpus.corpus_fingerprint,
        CorpusCounts(
            len(records),
            sum(record.eligibility == "review_relevant" for record in records),
            sum(record.resolution == "confirmed" for record in records),
            sum(record.resolution == "manual_unresolved" for record in records),
            sum(record.resolution == "exact_resolved" for record in records),
            sum(record.resolution == "not_applicable" for record in records),
        ),
        _section(token_counter, token_facts, top),
        _section(ngram_counter, ngram_facts, top),
        collect(unknown_action),
        collect(unknown_object),
        collect(lambda fact: fact["unit"].canonical_unit if fact["unit"].exact_only else None),
        _section(near_counter, near_facts, top),
        VariantSetSection(
            tuple(variant_items[:top]), len(variant_items), max(0, len(variant_items) - top)
        ),
        ManualActionDriverSection(
            tuple(manual_items[:top]), len(manual_items), max(0, len(manual_items) - top)
        ),
        OntologyCoverage(
            review_count,
            known_action,
            known_object,
            known_unit,
            full,
            sum(bool(fact["skeleton"].warnings) for fact in review_facts),
            sum(bool(fact["skeleton"].conflicts) for fact in review_facts),
            _rational(known_action, review_count),
            _rational(known_object, review_count),
            _rational(known_unit, review_count),
            _rational(full, review_count),
            token_total,
            known_token_count,
            slot_token_count,
            _rational(known_token_count, token_total),
            _rational(slot_token_count, token_total),
        ),
        RuleCoverage(tuple(rule_items), review_count),
    )


def _lexical_near(left: str, right: str) -> bool:
    if re.sub(r"[^\w]", "", left) == re.sub(r"[^\w]", "", right):
        return True
    a, b = left.split(), right.split()
    if len(a) == len(b):
        diff = [(x, y) for x, y in zip(a, b, strict=True) if x != y]
        if len(diff) == 1 and (len(diff[0][0]) == 1 or len(diff[0][1]) == 1 or _edit_one(*diff[0])):
            return True
    return False


def _edit_one(left: str, right: str) -> bool:
    if min(len(left), len(right)) < 8 or abs(len(left) - len(right)) > 1:
        return False
    i = j = changes = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        changes += 1
        if changes > 1:
            return False
        if len(left) > len(right):
            i += 1
        elif len(right) > len(left):
            j += 1
        else:
            i += 1
            j += 1
    return True


def _confirmed_atoms(
    corpus: CorpusSnapshot,
) -> tuple[list[dict[str, object]], set[tuple[str, str]]]:
    facts = _facts(corpus)
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        record = fact["record"]
        assert isinstance(record, CorpusRecord)
        if record.resolution == "confirmed" and not fact["private_text"]:
            groups[(str(fact["identity"]), record.document_set_id)].append(fact)
    usable = []
    contradictory = set()
    for atom, entries in groups.items():
        sigs = {
            (
                e["record"].outcome.action,
                e["record"].outcome.mode,
                e["record"].outcome.target_category,
            )
            for e in entries
            if isinstance(e["record"], CorpusRecord) and e["record"].outcome
        }
        if len(sigs) != 1:
            contradictory.add(atom)
        else:
            usable.append(sorted(entries, key=lambda e: e["record"].record_id)[0])
    return usable, contradictory


def _scope_from_fact(fact: dict[str, object]) -> PatternScope:
    category, mode, unit_family, action, object_kind, document_type = _scope_key(fact)
    return PatternScope(category, mode, unit_family, action, object_kind, document_type)  # type: ignore[arg-type]


def _scope_matches(scope: PatternScope, fact: dict[str, object]) -> bool:
    return scope == _scope_from_fact(fact)


def _proposal_matches(proposal: Proposal, fact: dict[str, object]) -> bool:
    semantic = str(fact["canon"].semantic_text)
    if isinstance(proposal, SlotTemplateProposal):
        return str(fact["skeleton"].skeleton_text) == proposal.skeleton
    if isinstance(proposal, IncludeExcludeProposal):
        return str(fact["skeleton"].skeleton_text) == proposal.predicate
    if isinstance(proposal, (SynonymAbbreviationProposal, SplitMergeProposal)):
        return semantic in proposal.variants or _public_text(semantic) in proposal.variants
    if isinstance(proposal, MustLinkCannotLinkProposal):
        return semantic in proposal.members
    if isinstance(proposal, CriticalModifierProposal):
        return any(token in semantic.split() for token in proposal.modifier.split("|"))
    if isinstance(proposal, CategorySpecificNormalizationProposal):
        return semantic in {proposal.rewrite_from, proposal.rewrite_to}
    return False


def _candidate(
    kind: CandidateKind,
    proposal: Proposal,
    entries: list[dict[str, object]],
    contradictory: set[tuple[str, str]],
    *,
    all_confirmed: list[dict[str, object]],
) -> PatternCandidate:
    """Create a candidate only from one already-compatible complete scope."""
    if not entries or len({_scope_key(entry) for entry in entries}) != 1:
        raise OfflineContractError("INVARIANT_VIOLATION", "candidate scope invariant failed")
    atoms = {_atom(e) for e in entries}
    docs = {atom[1] for atom in atoms}
    ids = {atom[0] for atom in atoms}
    risks = set()
    for entry in entries:
        if entry["unit"].exact_only:
            risks.add("unknown_unit")
        if entry["skeleton"].warnings:
            risks.add("parse_warning")
        if entry["skeleton"].conflicts:
            risks.add("semantic_conflict")
    outcomes = {_outcome_signature(entry["record"]) for entry in entries}
    expected_outcome = next(iter(outcomes)) if len(outcomes) == 1 else None
    scope = _scope_from_fact(entries[0])
    if any(
        _proposal_matches(proposal, fact) and not _scope_matches(scope, fact)
        for fact in all_confirmed
    ):
        risks.add("incomplete_scope")
    material = {
        "version": PATTERN_CANDIDATE_VERSION,
        "kind": kind.value,
        "scope": scope,
        "proposal": proposal,
    }
    cid = fingerprint(material)
    refs = tuple(
        sorted(
            fingerprint({"salt": "reconciliation-pattern-support-v1", "atom": atom})
            for atom in atoms
        )[:MAX_SUPPORT_REFS]
    )
    contradictory_atoms = {
        _atom(fact)
        for fact in all_confirmed
        if _scope_matches(scope, fact)
        and _proposal_matches(proposal, fact)
        and _atom(fact) in contradictory
    }
    support = SupportSummary(
        len(atoms), len(ids), len(docs), len(entries), len(contradictory_atoms), refs
    )
    evidence = fingerprint({"candidate_id": cid, "support": support, "risks": sorted(risks)})
    return PatternCandidate(
        "candidate",
        cid,
        kind,
        scope,
        proposal,
        expected_outcome,
        support,
        tuple(sorted(risks)),
        evidence,
    )


def mine_candidates(
    corpus: CorpusSnapshot, *, min_support_atoms: int = DEFAULT_MIN_SUPPORT_ATOMS
) -> CandidateSet:
    if (
        isinstance(min_support_atoms, bool)
        or not isinstance(min_support_atoms, int)
        or min_support_atoms < 1
    ):
        raise OfflineContractError("INVARIANT_VIOLATION", "mining invariant failed")
    facts, contradictory = _confirmed_atoms(corpus)
    all_confirmed = [
        fact
        for fact in _facts(corpus)
        if fact["record"].resolution == "confirmed" and not fact["private_text"]
    ]
    candidates: list[PatternCandidate] = []
    by_skeleton: dict[tuple[tuple[object, ...], str], list[dict[str, object]]] = defaultdict(list)
    by_text: dict[tuple[tuple[object, ...], str], list[dict[str, object]]] = defaultdict(list)
    for fact in facts:
        scope = _scope_key(fact)
        by_skeleton[(scope, str(fact["skeleton"].skeleton_text))].append(fact)
        by_text[(scope, str(fact["canon"].semantic_text))].append(fact)

    def enough(entries: list[dict[str, object]]) -> bool:
        return len({_atom(entry) for entry in entries}) >= min_support_atoms

    def outcome_keys(entries: list[dict[str, object]]) -> set[tuple[str, str | None, str | None]]:
        return {
            (
                entry["record"].outcome.action,
                entry["record"].outcome.mode,
                entry["record"].outcome.target_category,
            )
            for entry in entries
        }

    for (_, skeleton), entries in sorted(
        by_skeleton.items(), key=lambda item: (item[0][1], repr(item[0][0]))
    ):
        if not enough(entries):
            continue
        outcomes = outcome_keys(entries)
        signatures = {_slot_signature(entry) for entry in entries}
        safe_skeleton = not _looks_private_text(skeleton)
        if safe_skeleton and len(signatures) > 1 and len(outcomes) == 1:
            candidates.append(
                _candidate(
                    CandidateKind.SLOT_TEMPLATE,
                    SlotTemplateProposal(skeleton, tuple(sorted(signatures))),
                    entries,
                    contradictory,
                    all_confirmed=all_confirmed,
                )
            )
        if safe_skeleton and len(outcomes) == 1:
            candidates.append(
                _candidate(
                    CandidateKind.INCLUDE_EXCLUDE,
                    IncludeExcludeProposal(skeleton, next(iter(outcomes))[0]),
                    entries,
                    contradictory,
                    all_confirmed=all_confirmed,
                )
            )
        elif len(outcomes) > 1:
            candidates.append(
                _candidate(
                    CandidateKind.SPLIT_MERGE,
                    SplitMergeProposal(
                        tuple(
                            sorted(
                                {
                                    _public_text(str(entry["canon"].semantic_text))
                                    for entry in entries
                                }
                            )
                        ),
                        "partitioned_outcomes",
                    ),
                    entries,
                    contradictory,
                    all_confirmed=all_confirmed,
                )
            )

    for scope in sorted({scope for scope, _ in by_text}, key=repr):
        texts = sorted(text for text_scope, text in by_text if text_scope == scope)
        for index, left in enumerate(texts):
            for right in texts[index + 1 :]:
                entries = by_text[(scope, left)] + by_text[(scope, right)]
                if not enough(entries):
                    continue
                outcomes = outcome_keys(entries)
                if _public_text(left) != left or _public_text(right) != right:
                    # Parameter values are structural evidence only: slot templates can
                    # describe them, but lexical proposals must never serialize values.
                    continue
                modifier = _single_uncovered_token_difference(left, right, entries)
                if len(outcomes) > 1 and modifier is not None:
                    candidates.append(
                        _candidate(
                            CandidateKind.CRITICAL_MODIFIER,
                            CriticalModifierProposal(modifier),
                            entries,
                            contradictory,
                            all_confirmed=all_confirmed,
                        )
                    )
                # Link-like candidates are strictly lexical; critical modifiers use the
                # narrower exactly-one-uncovered-token rule above.
                if not _lexical_near(left, right):
                    continue
                if len(outcomes) == 1:
                    candidates.append(
                        _candidate(
                            CandidateKind.SYNONYM_ABBREVIATION,
                            SynonymAbbreviationProposal((left, right)),
                            entries,
                            contradictory,
                            all_confirmed=all_confirmed,
                        )
                    )
                    candidates.append(
                        _candidate(
                            CandidateKind.SPLIT_MERGE,
                            SplitMergeProposal((left, right), "same_outcome"),
                            entries,
                            contradictory,
                            all_confirmed=all_confirmed,
                        )
                    )
                    candidates.append(
                        _candidate(
                            CandidateKind.MUST_LINK_CANNOT_LINK,
                            MustLinkCannotLinkProposal("must_link", (left, right)),
                            entries,
                            contradictory,
                            all_confirmed=all_confirmed,
                        )
                    )
                    action, _, target_category = next(iter(outcomes))
                    if action == "accept" and target_category:
                        left_entries = by_text[(scope, left)]
                        right_entries = by_text[(scope, right)]
                        if enough(left_entries) and enough(right_entries):
                            candidates.append(
                                _candidate(
                                    CandidateKind.CATEGORY_SPECIFIC_NORMALIZATION,
                                    CategorySpecificNormalizationProposal(
                                        left, right, target_category
                                    ),
                                    entries,
                                    contradictory,
                                    all_confirmed=all_confirmed,
                                )
                            )
                else:
                    candidates.append(
                        _candidate(
                            CandidateKind.MUST_LINK_CANNOT_LINK,
                            MustLinkCannotLinkProposal("cannot_link", (left, right)),
                            entries,
                            contradictory,
                            all_confirmed=all_confirmed,
                        )
                    )

    unique = {candidate.candidate_id: candidate for candidate in candidates}
    return CandidateSet(
        corpus.corpus_fingerprint,
        tuple(
            sorted(
                unique.values(),
                key=lambda candidate: (
                    candidate.kind,
                    canonical_json_bytes(candidate.scope),
                    candidate.candidate_id,
                ),
            )
        ),
    )


def _single_uncovered_token_difference(
    left: str, right: str, entries: list[dict[str, object]]
) -> str | None:
    """Find one positional lexical boundary without treating a token set as a bag."""
    left_tokens = left.split()
    right_tokens = right.split()
    if len(left_tokens) != len(right_tokens):
        return None
    differences = [
        (left_token, right_token)
        for left_token, right_token in zip(left_tokens, right_tokens, strict=True)
        if left_token != right_token
    ]
    if len(differences) != 1:
        return None
    left_token, right_token = differences[0]
    uncovered = {token for entry in entries for token in _uncovered_tokens(entry)}
    if left_token not in uncovered or right_token not in uncovered:
        return None
    return f"{left_token}|{right_token}"


_PROPOSALS: dict[str, type[Proposal]] = {
    "synonym_abbreviation": SynonymAbbreviationProposal,
    "slot_template": SlotTemplateProposal,
    "include_exclude": IncludeExcludeProposal,
    "split_merge": SplitMergeProposal,
    "critical_modifier": CriticalModifierProposal,
    "must_link_cannot_link": MustLinkCannotLinkProposal,
    "category_specific_normalization": CategorySpecificNormalizationProposal,
}


def _candidate_invalid() -> None:
    raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")


def _candidate_hash(value: object) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        _candidate_invalid()
    return value


def _candidate_required(mapping: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(mapping, dict) or set(mapping) != keys:
        _candidate_invalid()
    return mapping


def _sorted_text_tuple(value: object, *, minimum: int = 1) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or not all(isinstance(item, str) and item for item in value)
        or tuple(value) != tuple(sorted(set(value)))
    ):
        _candidate_invalid()
    return tuple(value)


def _proposal_from_mapping(kind: str, value: object) -> Proposal:
    proposal_type = _PROPOSALS[kind]
    _require_exact_mapping(value, set(proposal_type.__dataclass_fields__))
    assert isinstance(value, dict)
    if kind == CandidateKind.SYNONYM_ABBREVIATION:
        variants = _sorted_text_tuple(value["variants"], minimum=2)
        if len(variants) != 2 or not _lexical_near(*variants):
            _candidate_invalid()
        return SynonymAbbreviationProposal(variants)
    if kind == CandidateKind.SLOT_TEMPLATE:
        skeleton = value["skeleton"]
        signatures = _sorted_text_tuple(value["slot_signatures"], minimum=2)
        if not isinstance(skeleton, str) or not skeleton:
            _candidate_invalid()
        return SlotTemplateProposal(skeleton, signatures)
    if kind == CandidateKind.INCLUDE_EXCLUDE:
        predicate, polarity = value["predicate"], value["polarity"]
        if (
            not isinstance(predicate, str)
            or not predicate
            or not isinstance(polarity, str)
            or polarity not in {"accept", "reject"}
        ):
            _candidate_invalid()
        return IncludeExcludeProposal(predicate, polarity)
    if kind == CandidateKind.SPLIT_MERGE:
        variants, relation = _sorted_text_tuple(value["variants"], minimum=2), value["relation"]
        if (
            len(variants) != 2
            or not isinstance(relation, str)
            or relation not in {"same_outcome", "partitioned_outcomes"}
        ):
            _candidate_invalid()
        return SplitMergeProposal(variants, relation)
    if kind == CandidateKind.CRITICAL_MODIFIER:
        modifier, disposition = value["modifier"], value["disposition"]
        parts = modifier.split("|") if isinstance(modifier, str) else []
        if (
            len(parts) != 2
            or not all(parts)
            or parts[0] == parts[1]
            or disposition != "hard_boundary_review"
        ):
            _candidate_invalid()
        return CriticalModifierProposal(modifier, disposition)
    if kind == CandidateKind.MUST_LINK_CANNOT_LINK:
        relation, members = value["relation"], _sorted_text_tuple(value["members"], minimum=2)
        if (
            not isinstance(relation, str)
            or relation not in {"must_link", "cannot_link"}
            or len(members) != 2
        ):
            _candidate_invalid()
        return MustLinkCannotLinkProposal(relation, members)
    rewrite_from, rewrite_to, target_category = (
        value["rewrite_from"],
        value["rewrite_to"],
        value["target_category"],
    )
    if (
        not isinstance(rewrite_from, str)
        or not rewrite_from
        or not isinstance(rewrite_to, str)
        or not rewrite_to
        or rewrite_from == rewrite_to
        or not isinstance(target_category, str)
        or not target_category
    ):
        _candidate_invalid()
    return CategorySpecificNormalizationProposal(rewrite_from, rewrite_to, target_category)


def _validated_expected_outcome(value: object) -> OutcomeSignature | None:
    if value is None:
        return None
    _require_exact_mapping(value, set(OutcomeSignature.__dataclass_fields__))
    assert isinstance(value, dict)
    action = value["action"]
    mode = value["mode"]
    category = value["target_category"]
    if not isinstance(action, str) or action not in {"accept", "reject"}:
        _candidate_invalid()
    if action == "accept":
        if (
            not isinstance(mode, str)
            or mode not in {"quantity_cost", "cost_only"}
            or not isinstance(category, str)
            or not category
        ):
            _candidate_invalid()
    elif mode is not None or category is not None:
        _candidate_invalid()
    return OutcomeSignature(action, mode, category)  # type: ignore[arg-type]


def _proposal_outcome_is_consistent(proposal: Proposal, expected: OutcomeSignature | None) -> bool:
    if isinstance(proposal, IncludeExcludeProposal):
        return expected is not None and expected.action == proposal.polarity
    if isinstance(proposal, CriticalModifierProposal):
        return expected is None
    if isinstance(proposal, SplitMergeProposal):
        return (proposal.relation == "same_outcome") == (expected is not None)
    if isinstance(proposal, MustLinkCannotLinkProposal):
        return (proposal.relation == "must_link") == (expected is not None)
    if isinstance(proposal, CategorySpecificNormalizationProposal):
        return (
            expected is not None
            and expected.action == "accept"
            and expected.target_category == proposal.target_category
        )
    return expected is not None


def _candidate_from_mapping(value: object) -> PatternCandidate:
    required = {
        "record_type",
        "version",
        "candidate_id",
        "kind",
        "scope",
        "proposal",
        "expected_outcome",
        "support",
        "risk_codes",
        "fingerprint",
        "state",
        "descriptive_only",
        "requires_owner_review",
    }
    value = _candidate_required(value, required)
    kind = value["kind"]
    if (
        value["record_type"] != "candidate"
        or not isinstance(kind, str)
        or kind not in _KINDS
        or value["version"] != PATTERN_CANDIDATE_VERSION
        or value["state"] != "proposed"
        or value["descriptive_only"] is not True
        or value["requires_owner_review"] is not True
        or not isinstance(value["scope"], dict)
        or not isinstance(value["proposal"], dict)
        or not isinstance(value["support"], dict)
        or not isinstance(value["risk_codes"], list)
    ):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    _require_exact_mapping(value["scope"], set(PatternScope.__dataclass_fields__))
    _require_exact_mapping(value["support"], set(SupportSummary.__dataclass_fields__))
    if any(
        item is not None and (not isinstance(item, str) or not item)
        for item in value["scope"].values()
    ):
        _candidate_invalid()
    if value["scope"]["mode"] is not None and value["scope"]["mode"] not in {
        "quantity_cost",
        "cost_only",
    }:
        _candidate_invalid()
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item < 0
        for key, item in value["support"].items()
        if key != "support_refs"
    ):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    refs = value["support"]["support_refs"]
    if (
        not isinstance(refs, list)
        or not all(isinstance(ref, str) and _SHA.fullmatch(ref) for ref in refs)
        or tuple(refs) != tuple(sorted(set(refs)))
        or len(refs) > MAX_SUPPORT_REFS
    ):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    try:
        scope = PatternScope(**value["scope"])
        proposal = _proposal_from_mapping(kind, value["proposal"])
        support = SupportSummary(**{**value["support"], "support_refs": tuple(refs)})
    except (TypeError, ValueError) as exc:
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid") from exc
    expected_outcome = _validated_expected_outcome(value["expected_outcome"])
    if (
        support.support_atom_count < 1
        or support.semantic_identity_count > support.support_atom_count
        or support.document_set_count > support.support_atom_count
        or support.confirmed_record_count < support.support_atom_count
        or not _proposal_outcome_is_consistent(proposal, expected_outcome)
    ):
        _candidate_invalid()
    if not all(isinstance(code, str) and code for code in value["risk_codes"]) or tuple(
        value["risk_codes"]
    ) != tuple(sorted(set(value["risk_codes"]))):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    candidate = PatternCandidate(
        "candidate",
        _candidate_hash(value["candidate_id"]),
        CandidateKind(kind),
        scope,
        proposal,
        expected_outcome,
        support,
        tuple(value["risk_codes"]),
        _candidate_hash(value["fingerprint"]),
    )
    if candidate.candidate_id != fingerprint(
        {"version": PATTERN_CANDIDATE_VERSION, "kind": kind, "scope": scope, "proposal": proposal}
    ):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    if candidate.fingerprint != fingerprint(
        {
            "candidate_id": candidate.candidate_id,
            "support": support,
            "risks": list(candidate.risk_codes),
        }
    ):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    return candidate


def _require_exact_mapping(value: object, keys: set[str]) -> None:
    _candidate_required(value, keys)


def load_candidate_jsonl(path: Path) -> CandidateSet:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise OfflineContractError("INPUT_NOT_FOUND", "input is absent") from exc
    except OSError as exc:
        raise OfflineContractError("INPUT_NOT_REGULAR", "input is not readable") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OfflineContractError("INPUT_INVALID_UTF8", "input is not UTF-8") from exc
    if not text.endswith("\n") or "\r" in text:
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    try:
        rows = [
            json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            for line in text.splitlines()
        ]
    except (ValueError, json.JSONDecodeError) as exc:
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid") from exc
    if any(_contains_float(row) for row in rows):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    if not rows or not isinstance(rows[0], dict):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    header = _candidate_required(
        rows[0], {"record_type", "schema_version", "source_corpus_fingerprint"}
    )
    if header["record_type"] != "header" or header["schema_version"] != CANDIDATE_SET_VERSION:
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    candidates = tuple(_candidate_from_mapping(row) for row in rows[1:])
    if tuple(c.candidate_id for c in candidates) != tuple(
        c.candidate_id
        for c in sorted(
            candidates, key=lambda c: (c.kind, canonical_json_bytes(c.scope), c.candidate_id)
        )
    ) or len({c.candidate_id for c in candidates}) != len(candidates):
        raise OfflineContractError("CANDIDATE_INPUT_INVALID", "candidate input is invalid")
    source = header["source_corpus_fingerprint"]
    if not isinstance(source, str) or not _SHA.fullmatch(source):
        _candidate_invalid()
    return CandidateSet(source, candidates)


def _candidate_matches(candidate: PatternCandidate, fact: dict[str, object]) -> bool:
    return _scope_matches(candidate.scope, fact) and _proposal_matches(candidate.proposal, fact)


def evaluate_candidates(
    corpus: CorpusSnapshot, candidates: CandidateSet
) -> CandidateEvaluationReport:
    if corpus.corpus_fingerprint != candidates.source_corpus_fingerprint:
        raise OfflineContractError(
            "INPUT_FINGERPRINT_MISMATCH", "candidate source does not match corpus"
        )
    facts, contradictions = _confirmed_atoms(corpus)
    allfacts = [fact for fact in _facts(corpus) if not fact["private_text"]]
    values: list[CandidateEvaluation] = []
    for candidate in candidates.candidates:
        proposal_matched = [
            fact for fact in allfacts if _proposal_matches(candidate.proposal, fact)
        ]
        matched = [fact for fact in proposal_matched if _scope_matches(candidate.scope, fact)]
        supported = [fact for fact in facts if _candidate_matches(candidate, fact)]
        matched_atoms = {_atom(fact) for fact in matched}
        atoms = {_atom(fact) for fact in supported}
        identities = {atom[0] for atom in matched_atoms}
        documents = {atom[1] for atom in matched_atoms}
        supported_by_atom = {_atom(fact): fact for fact in supported}
        expected = candidate.expected_outcome
        agreement_denominator = len(atoms) if expected is not None else 0
        agreement_numerator = (
            sum(
                _outcome_signature(fact["record"]) == expected
                for fact in supported_by_atom.values()
            )
            if expected is not None
            else 0
        )
        contradictory_matched = {
            _atom(fact)
            for fact in matched
            if fact["record"].resolution == "confirmed" and _atom(fact) in contradictions
        }
        unresolved = {
            _atom(fact) for fact in matched if fact["record"].resolution == "manual_unresolved"
        }
        hard = {
            _atom(fact) for fact in proposal_matched if not _scope_matches(candidate.scope, fact)
        }
        warnings = {_atom(fact) for fact in matched if fact["skeleton"].warnings}
        risks = set(candidate.risk_codes)
        if agreement_denominator and agreement_numerator != agreement_denominator:
            risks.add("outcome_partition")
        if contradictory_matched:
            risks.add("contradictory_atom")
        if hard:
            risks.add("hard_boundary_mismatch")
        values.append(
            CandidateEvaluation(
                candidate.candidate_id,
                len(matched_atoms),
                len(identities),
                len(documents),
                len(atoms),
                len(contradictory_matched),
                len(unresolved),
                len(hard),
                len(warnings),
                Rational(agreement_numerator, agreement_denominator),
                tuple(sorted(risks)),
            )
        )
    return CandidateEvaluationReport(corpus.corpus_fingerprint, tuple(values))


def profile_payload(profile: CorpusProfile) -> dict[str, object]:
    return _plain(profile)  # type: ignore[return-value]


def candidate_jsonl_bytes(candidates: CandidateSet) -> bytes:
    header = {
        "record_type": "header",
        "schema_version": CANDIDATE_SET_VERSION,
        "source_corpus_fingerprint": candidates.source_corpus_fingerprint,
    }
    return b"".join(canonical_json_bytes(row) + b"\n" for row in (header, *candidates.candidates))


def evaluation_payload(report: CandidateEvaluationReport) -> dict[str, object]:
    return _plain(report)  # type: ignore[return-value]


def atomic_private_write(path: Path, payload: bytes, *, overwrite: bool) -> None:
    """Publish a mode-0600 regular file, never following an output symlink."""
    try:
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe")
            if not overwrite:
                raise OfflineContractError("OUTPUT_EXISTS", "output exists")
        parent = path.parent
        if not parent.is_dir() or parent.is_symlink():
            raise OfflineContractError("OUTPUT_UNSAFE", "output parent is unsafe")
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
        try:
            os.fchmod(fd, 0o600)
            _write_all(fd, payload)
            os.fsync(fd)
            os.close(fd)
            temp = Path(temp_name)
            if temp.is_symlink() or not temp.is_file():
                raise OfflineContractError("OUTPUT_UNSAFE", "output is unsafe")
            os.replace(temp, path)
        except BaseException:
            with suppress(OSError):
                os.close(fd)
            Path(temp_name).unlink(missing_ok=True)
            raise
    except OfflineContractError:
        raise
    except OSError as exc:
        raise OfflineContractError("OUTPUT_IO_ERROR", "output I/O failed") from exc


def _write_all(fd: int, payload: bytes) -> None:
    """Handle permitted short writes before publication of the temporary file."""
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if written <= 0:
            raise OSError("short output write")
        offset += written


def _ensure_private(value: object) -> None:
    """Regression guard: public serializers must never receive corpus fields."""
    if isinstance(value, str):
        if _looks_private_text(value):
            raise OfflineContractError("INVARIANT_VIOLATION", "privacy invariant failed")
        return
    if isinstance(value, dict):
        keys = {str(key).casefold() for key in value}
        if _PRIVATE & set(value) or any(part in key for key in keys for part in _PRIVATE_KEY_PARTS):
            raise OfflineContractError("INVARIANT_VIOLATION", "privacy invariant failed")
        for item in value.values():
            _ensure_private(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _ensure_private(item)


def write_profile(path: Path, profile: CorpusProfile, *, overwrite: bool) -> None:
    value = profile_payload(profile)
    _ensure_private(value)
    atomic_private_write(path, canonical_json_bytes(value) + b"\n", overwrite=overwrite)


def write_candidates(path: Path, candidates: CandidateSet, *, overwrite: bool) -> None:
    value = candidate_jsonl_bytes(candidates)
    _ensure_private_jsonl(value)
    atomic_private_write(path, value, overwrite=overwrite)


def _ensure_private_jsonl(value: bytes) -> None:
    try:
        for line in value.splitlines():
            _ensure_private(json.loads(line))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfflineContractError("INVARIANT_VIOLATION", "privacy invariant failed") from exc


def write_evaluation(path: Path, report: CandidateEvaluationReport, *, overwrite: bool) -> None:
    value = evaluation_payload(report)
    _ensure_private(value)
    atomic_private_write(path, canonical_json_bytes(value) + b"\n", overwrite=overwrite)

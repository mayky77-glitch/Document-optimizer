"""Synthetic acceptance tests for the isolated Wave 3 offline contract."""

from __future__ import annotations

import json
import stat
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from report_processor.reconciliation_patterns import offline


def _hash(char: str) -> str:
    return f"sha256:{char * 64}"


def _row(
    number: int,
    *,
    text: str = "synthetic item",
    document: str = "a",
    resolution: str = "confirmed",
    action: str = "accept",
    manual: bool = False,
    rules: list[str] | None = None,
    object_kind: str | None = None,
    unit: str | None = "synthetic_unit",
    document_type: str | None = "synthetic_type",
    eligibility: str = "review_relevant",
) -> dict[str, object]:
    outcome: dict[str, object] | None = None
    if resolution == "confirmed":
        outcome = {
            "version": offline.CONFIRMED_OUTCOME_VERSION,
            "kind": "confirmed_authoritative",
            "action": action,
            "mode": "quantity_cost" if action == "accept" else None,
            "target_category": "synthetic_category" if action == "accept" else None,
            "apply_fingerprint": _hash("c"),
            "result_fingerprint": _hash("d"),
        }
    row: dict[str, object] = {
        "record_type": "row",
        "record_id": _hash(f"{number:x}"),
        "record_fingerprint": _hash("0"),
        "document_set_id": _hash(document),
        "document_type": document_type,
        "audit_text": text,
        "unit": unit,
        "category": None,
        "mode": "quantity_cost",
        "object_kind": object_kind,
        "eligibility": eligibility,
        "resolution": resolution,
        "manual_action_id": _hash("f") if manual else None,
        "matched_rule_ids": rules or [],
        "outcome": outcome,
    }
    fingerprint_material = {
        key: value for key, value in row.items() if key not in {"record_type", "record_fingerprint"}
    }
    fingerprint_material["record_type"] = "row"
    row["record_fingerprint"] = offline.fingerprint(fingerprint_material)
    return row


def write_corpus(
    path: Path, rows: list[dict[str, object]], *, rules: list[str] | None = None
) -> bytes:
    rules = rules or []
    versions = {
        "term_canonicalization": "TermCanonicalization-2.0",
        "domain_ontology": "DomainOntology-1.0",
        "unit_ontology": "UnitOntology-1.1",
        "typed_slots": "TypedSlots-1.0",
        "semantic_skeleton": "SemanticSkeleton-1.0",
        "category_catalog": "synthetic-catalog",
        "rule_catalog": "synthetic-rules",
        "outcome_export": "ConfirmedOutcome-1.0",
    }
    # Build only through public models; production parsing helpers are deliberately
    # not test-fixture dependencies.
    records = tuple(
        offline.CorpusRecord(
            record_id=str(row["record_id"]),
            record_fingerprint=str(row["record_fingerprint"]),
            document_set_id=str(row["document_set_id"]),
            document_type=row["document_type"],  # type: ignore[arg-type]
            audit_text=str(row["audit_text"]),
            unit=row["unit"],  # type: ignore[arg-type]
            category=row["category"],  # type: ignore[arg-type]
            mode=row["mode"],  # type: ignore[arg-type]
            object_kind=row["object_kind"],  # type: ignore[arg-type]
            eligibility=str(row["eligibility"]),
            resolution=str(row["resolution"]),
            manual_action_id=row["manual_action_id"],  # type: ignore[arg-type]
            matched_rule_ids=tuple(row["matched_rule_ids"]),  # type: ignore[arg-type]
            outcome=(offline.ConfirmedOutcome(**row["outcome"]) if row["outcome"] else None),  # type: ignore[arg-type]
        )
        for row in sorted(rows, key=lambda x: str(x["record_id"]))
    )
    material = {
        "schema_version": offline.CORPUS_SCHEMA_VERSION,
        "rule_ids": tuple(rules),
        "versions": offline.CorpusVersions(**versions),
        "rows": records,
    }
    header = {
        "record_type": "header",
        "schema_version": offline.CORPUS_SCHEMA_VERSION,
        "corpus_fingerprint": offline.fingerprint(material),
        "rule_ids": rules,
        "versions": versions,
    }
    payload = b"".join(offline.canonical_json_bytes(value) + b"\n" for value in (header, *rows))
    path.write_bytes(payload)
    return payload


def _assert_public_graph_immutable(value: object) -> None:
    if is_dataclass(value):
        assert value.__dataclass_params__.frozen
        assert hasattr(value, "__slots__")
        for field in fields(value):
            _assert_public_graph_immutable(getattr(value, field.name))
    elif isinstance(value, (tuple, frozenset)):
        for item in value:
            _assert_public_graph_immutable(item)
    else:
        assert not isinstance(value, (dict, list, set))


def test_loader_rejects_unknown_fields_versions_and_duplicate_ids(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    row = _row(1)
    write_corpus(source, [row])
    assert offline.load_corpus_jsonl(source).version == offline.CORPUS_SCHEMA_VERSION
    row["unexpected"] = "x"
    source.write_bytes(
        source.read_bytes().replace(b'"record_type":"row"', b'"unexpected":"x","record_type":"row"')
    )
    with pytest.raises(offline.OfflineContractError, match="input schema"):
        offline.load_corpus_jsonl(source)
    row = _row(1)
    payload = write_corpus(source, [row])
    source.write_bytes(payload + payload.splitlines()[1] + b"\n")
    with pytest.raises(offline.OfflineContractError, match="input schema"):
        offline.load_corpus_jsonl(source)


def test_loader_rejects_legacy_unit_ontology_corpus(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(source, [_row(1)])
    source.write_bytes(
        source.read_bytes().replace(
            b'"unit_ontology":"UnitOntology-1.1"', b'"unit_ontology":"UnitOntology-1.0"', 1
        )
    )

    with pytest.raises(offline.OfflineContractError, match="input version is unsupported"):
        offline.load_corpus_jsonl(source)


def test_profile_is_complete_deterministic_and_private(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    original = write_corpus(
        source,
        [_row(1, rules=["rule-a"]), _row(2, resolution="manual_unresolved", manual=True)],
        rules=["rule-a", "rule-zero"],
    )
    corpus = offline.load_corpus_jsonl(source)
    profile = offline.profile_corpus(corpus, top=1)
    payload = offline.profile_payload(profile)
    assert set(payload) >= {
        "corpus_counts",
        "uncovered_tokens",
        "uncovered_ngrams",
        "unknown_actions",
        "unknown_objects",
        "unknown_units",
        "near_name_pairs",
        "same_outcome_variant_sets",
        "manual_action_drivers",
        "ontology_coverage",
        "rule_coverage",
    }
    assert {item["rule_id"] for item in payload["rule_coverage"]["items"]} == {
        "rule-a",
        "rule-zero",
    }
    assert source.read_bytes() == original
    output = tmp_path / "profile.json"
    offline.write_profile(output, profile, overwrite=False)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    rendered = output.read_text(encoding="utf-8")
    assert "audit_text" not in rendered and "record_id" not in rendered


def test_shuffled_rows_are_accepted_and_produce_byte_identical_profile(tmp_path: Path) -> None:
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    rows = [_row(1, text="alpha"), _row(2, text="beta")]
    write_corpus(left, rows)
    write_corpus(right, list(reversed(rows)))
    left_profile = offline.profile_payload(offline.profile_corpus(offline.load_corpus_jsonl(left)))
    right_profile = offline.profile_payload(
        offline.profile_corpus(offline.load_corpus_jsonl(right))
    )
    assert offline.canonical_json_bytes(left_profile) == offline.canonical_json_bytes(right_profile)


def test_record_fingerprint_is_verified_not_only_shape_checked(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    row = _row(1)
    write_corpus(source, [row])
    source.write_bytes(
        source.read_bytes().replace(row["record_fingerprint"].encode(), _hash("f").encode())
    )
    with pytest.raises(offline.OfflineContractError, match="fingerprint"):
        offline.load_corpus_jsonl(source)


def test_synthetic_fixture_can_exercise_all_seven_inert_candidate_kinds(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    rows = [
        _row(1, text="longsynthetic-a", document="1"),
        _row(2, text="longsynthetic-a", document="2"),
        _row(3, text="longsynthetic-b", document="3"),
        _row(4, text="longsynthetic-b", document="4"),
        _row(5, text="cable 3x10", document="5", object_kind="cable"),
        _row(6, text="cable 4x16", document="6", object_kind="cable"),
        _row(7, text="boundary alpha", document="7", action="accept"),
        _row(8, text="boundary beta", document="8", action="reject"),
        _row(9, text="boundary alpha", document="9", action="accept"),
        _row(10, text="boundary beta", document="a", action="reject"),
    ]
    write_corpus(source, rows)
    candidates = offline.mine_candidates(offline.load_corpus_jsonl(source))
    assert {candidate.kind for candidate in candidates.candidates} == set(offline._KINDS)


def test_confirmed_only_atoms_deduplicate_and_contradictions_do_not_support(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(
        source,
        [
            _row(1, text="same form", document="a"),
            _row(2, text="same form", document="a"),
            _row(3, text="same form", document="b"),
            _row(4, text="same form", document="c", action="reject"),
            _row(5, text="same form", document="c", action="accept"),
            _row(6, text="same form", document="d", resolution="manual_unresolved", manual=True),
        ],
    )
    candidates = offline.mine_candidates(offline.load_corpus_jsonl(source), min_support_atoms=2)
    assert all(candidate.support.support_atom_count == 2 for candidate in candidates.candidates)
    assert all(candidate.support.contradiction_count >= 1 for candidate in candidates.candidates)
    assert all(
        candidate.state == "proposed" and candidate.descriptive_only
        for candidate in candidates.candidates
    )


def test_private_writer_refuses_unsafe_existing_and_symlink_output(tmp_path: Path) -> None:
    target = tmp_path / "output.json"
    offline.atomic_private_write(target, b"{}\n", overwrite=False)
    with pytest.raises(offline.OfflineContractError, match="output exists"):
        offline.atomic_private_write(target, b"{}\n", overwrite=False)
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(offline.OfflineContractError, match="output is unsafe"):
        offline.atomic_private_write(link, b"{}\n", overwrite=True)


def test_public_profiles_and_evaluations_are_deeply_immutable(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(source, [_row(1), _row(2, document="b")])
    corpus = offline.load_corpus_jsonl(source)
    profile = offline.profile_corpus(corpus)
    candidates = offline.mine_candidates(corpus)
    report = offline.evaluate_candidates(corpus, candidates)
    for value in (corpus, profile, candidates, report):
        _assert_public_graph_immutable(value)


def test_candidate_loader_rejects_tampered_identity_and_evidence(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    destination = tmp_path / "candidates.jsonl"
    write_corpus(source, [_row(1), _row(2, document="b")])
    candidates = offline.mine_candidates(offline.load_corpus_jsonl(source))
    assert candidates.candidates
    payload = offline.candidate_jsonl_bytes(candidates)
    destination.write_bytes(payload)
    assert offline.load_candidate_jsonl(destination) == candidates
    first = candidates.candidates[0]
    for original, replacement in (
        (first.candidate_id, _hash("e")),
        (first.fingerprint, _hash("f")),
    ):
        destination.write_bytes(payload.replace(original.encode(), replacement.encode(), 1))
        with pytest.raises(offline.OfflineContractError) as error:
            offline.load_candidate_jsonl(destination)
        assert error.value.code == "CANDIDATE_INPUT_INVALID"

    malformed = [json.loads(line) for line in payload.splitlines()]
    malformed[1]["support"]["support_atom_count"] = True
    destination.write_bytes(
        b"".join(offline.canonical_json_bytes(item) + b"\n" for item in malformed)
    )
    with pytest.raises(offline.OfflineContractError) as error:
        offline.load_candidate_jsonl(destination)
    assert error.value.code == "CANDIDATE_INPUT_INVALID"

    malformed = [json.loads(line) for line in payload.splitlines()]
    malformed[1]["expected_outcome"] = {
        "action": "reject",
        "mode": "quantity_cost",
        "target_category": "synthetic_category",
    }
    destination.write_bytes(
        b"".join(offline.canonical_json_bytes(item) + b"\n" for item in malformed)
    )
    with pytest.raises(offline.OfflineContractError) as error:
        offline.load_candidate_jsonl(destination)
    assert error.value.code == "CANDIDATE_INPUT_INVALID"


def test_atomic_writer_retries_short_writes_and_preserves_existing_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "output.json"
    payload = b"short-write-payload\n"
    real_write = offline.os.write

    def short_write(fd: int, value: bytes) -> int:
        return real_write(fd, value[:3])

    monkeypatch.setattr(offline.os, "write", short_write)
    offline.atomic_private_write(target, payload, overwrite=False)
    assert target.read_bytes() == payload
    target.write_bytes(b"old\n")

    def failed_write(fd: int, value: bytes) -> int:
        raise OSError("simulated")

    monkeypatch.setattr(offline.os, "write", failed_write)
    with pytest.raises(offline.OfflineContractError) as error:
        offline.atomic_private_write(target, b"new\n", overwrite=True)
    assert error.value.code == "OUTPUT_IO_ERROR"
    assert target.read_bytes() == b"old\n"


def test_profile_output_never_leaks_private_row_values(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    output = tmp_path / "profile.json"
    private_value = "/private/estimate-secret.xlsx"
    write_corpus(source, [_row(1, text=private_value), _row(2, document="b")])
    offline.write_profile(
        output, offline.profile_corpus(offline.load_corpus_jsonl(source)), overwrite=False
    )
    assert private_value not in output.read_text(encoding="utf-8")


def test_loader_rejects_nested_shape_and_outcome_invariant_tampering(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(source, [_row(1)])
    original = source.read_bytes()
    for needle, replacement in (
        (b'"mode":"quantity_cost"', b'"mode":[]'),
        (b'"action":"accept"', b'"action":"maybe"'),
        (b'"target_category":"synthetic_category"', b'"target_category":null'),
    ):
        source.write_bytes(original.replace(needle, replacement, 1))
        with pytest.raises(offline.OfflineContractError) as error:
            offline.load_corpus_jsonl(source)
        assert error.value.code == "INPUT_SCHEMA_INVALID"


def test_public_semantic_identity_distinguishes_slot_kind_impact_and_normalized_value(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(
        source,
        [
            _row(
                1, text="Монтаж кабеля, марка: ВВГнг-LS 4×16 мм², 0,66 кВ", document="a", unit="м"
            ),
            _row(
                2, text="Монтаж кабеля, марка: ВВГнг-LS 3×10 мм², 0,66 кВ", document="b", unit="м"
            ),
        ],
    )
    candidates = offline.mine_candidates(offline.load_corpus_jsonl(source))
    slot_candidate = next(
        candidate for candidate in candidates.candidates if candidate.kind == "slot_template"
    )
    assert slot_candidate.support.semantic_identity_count == 2


def test_profiler_keeps_private_review_row_in_denominator_without_leaking_it(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.jsonl"
    private = "Estimate.PDF =SUM(A1:A2) Sheet1!B7 reviewer comment"
    write_corpus(
        source,
        [
            _row(1, text="Монтаж кабеля", document="a", unit="м"),
            _row(2, text=private, document="b", unit="м"),
        ],
    )
    profile = offline.profile_corpus(offline.load_corpus_jsonl(source))
    coverage = profile.ontology_coverage
    assert coverage.review_relevant_denominator == 2
    assert coverage.known_action_ratio == offline.Rational(1, 2)
    assert coverage.full_coverage_count < coverage.review_relevant_denominator
    rendered = json.dumps(offline.profile_payload(profile), ensure_ascii=False)
    for forbidden in ("Estimate.PDF", "=SUM(A1:A2)", "Sheet1!B7", "reviewer comment"):
        assert forbidden not in rendered


def test_evaluator_reports_exact_atoms_contradiction_scope_and_agreement(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    text = "Монтаж кабеля"
    write_corpus(
        source,
        [
            _row(1, text=text, document="a", unit="м"),
            _row(2, text=text, document="a", unit="м"),
            _row(3, text=text, document="b", unit="м"),
            _row(4, text=text, document="c", unit="м", action="accept"),
            _row(5, text=text, document="c", unit="м", action="reject"),
            _row(6, text=text, document="d", unit="м", resolution="manual_unresolved", manual=True),
            _row(7, text=text, document="e", unit="м", document_type="other_type"),
        ],
    )
    corpus = offline.load_corpus_jsonl(source)
    scope = offline.PatternScope(
        mode="quantity_cost",
        unit_family="length",
        action="installation",
        object_kind="cable",
        document_type="synthetic_type",
    )
    proposal = offline.MustLinkCannotLinkProposal("must_link", ("монтаж кабеля",))
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": "must_link_cannot_link",
            "scope": scope,
            "proposal": proposal,
        }
    )
    candidate = offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.MUST_LINK_CANNOT_LINK,
        scope,
        proposal,
        offline.OutcomeSignature("accept", "quantity_cost", "synthetic_category"),
        offline.SupportSummary(2, 1, 2, 2, 1, ()),
        (),
        offline.fingerprint(
            {
                "candidate_id": candidate_id,
                "support": offline.SupportSummary(2, 1, 2, 2, 1, ()),
                "risks": [],
            }
        ),
    )
    value = offline.evaluate_candidates(
        corpus, offline.CandidateSet(corpus.corpus_fingerprint, (candidate,))
    ).evaluations[0]
    assert value.matched_atom_count == 4
    assert value.confirmed_support_atom_count == 2
    assert value.confirmed_contradiction_atom_count == 1
    assert value.unresolved_match_atom_count == 1
    assert value.hard_boundary_mismatch_count == 1
    assert value.agreement == offline.Rational(2, 2)


def test_parameter_near_pair_is_described_without_serializing_raw_dimensions(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(
        source,
        [
            _row(
                1,
                text="Монтаж кабеля, марка: ВВГнг-LS 3×10 мм², 0,66 кВ",
                document="a",
                unit="м",
            ),
            _row(
                2,
                text="Монтаж кабеля, марка: ВВГнг-LS 4×16 мм², 0,66 кВ",
                document="b",
                unit="м",
            ),
        ],
    )
    corpus = offline.load_corpus_jsonl(source)
    profile = offline.profile_corpus(corpus)
    candidates = offline.mine_candidates(corpus)
    assert profile.near_name_pairs.total_distinct >= 1
    rendered = "\n".join(
        (
            json.dumps(offline.profile_payload(profile), ensure_ascii=False),
            offline.candidate_jsonl_bytes(candidates).decode("utf-8"),
        )
    )
    for fragment in ("3x10", "4x16", "3×10", "4×16"):
        assert fragment not in rendered


def test_supported_quantity_skeleton_candidates_are_skipped_before_private_write(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus.jsonl"
    destination = tmp_path / "candidates.jsonl"
    write_corpus(
        source,
        [
            _row(1, text="кабель 3x10", document="a"),
            _row(2, text="кабель 3x10", document="b"),
            _row(3, text="кабель 4x16", document="c"),
            _row(4, text="кабель 4x16", document="d"),
        ],
    )
    corpus = offline.load_corpus_jsonl(source)
    profile = offline.profile_corpus(corpus)
    candidates = offline.mine_candidates(corpus, min_support_atoms=2)
    rendered = "\n".join(
        (
            json.dumps(offline.profile_payload(profile), ensure_ascii=False),
            offline.candidate_jsonl_bytes(candidates).decode("utf-8"),
        )
    )
    assert profile.near_name_pairs.total_distinct >= 1
    assert "3x10" not in rendered and "4x16" not in rendered
    offline.write_candidates(destination, candidates, overwrite=False)
    assert destination.read_bytes() == offline.candidate_jsonl_bytes(candidates)


def test_bare_parameter_variants_are_near_by_private_opaque_signature(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(
        source,
        [
            _row(1, text="кабель 3x10", document="a"),
            _row(2, text="кабель 3x10", document="b"),
            _row(3, text="кабель 4x16", document="c"),
            _row(4, text="кабель 4x16", document="d"),
        ],
    )
    profile = offline.profile_payload(offline.profile_corpus(offline.load_corpus_jsonl(source)))
    assert profile["near_name_pairs"]["total_distinct"] >= 1
    rendered = json.dumps(profile, ensure_ascii=False)
    assert "parameter_variant:sha256:" in rendered
    assert "3x10" not in rendered and "4x16" not in rendered


def test_uncovered_ngrams_keep_only_original_adjacent_windows(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    write_corpus(
        source,
        [
            _row(1, text="foo монтаж bar", document="a", unit="м"),
            _row(2, text="foo монтаж bar", document="b", unit="м"),
        ],
    )
    profile = offline.profile_corpus(offline.load_corpus_jsonl(source))
    values = {item.value for item in profile.uncovered_ngrams.items}
    assert "foo bar" not in values
    assert not values


def test_public_profile_and_candidates_redact_final_privacy_fragments(tmp_path: Path) -> None:
    source = tmp_path / "corpus.jsonl"
    fragments = (
        "archive.7z",
        "row 12",
        "строка 12",
        "provenance alpha",
        "source digest abc",
        "кабель 3x10",
        "кабель 4x16",
    )
    write_corpus(
        source,
        [
            _row(index + 1, text=value, document=f"{index:x}")
            for index, value in enumerate(fragments)
        ],
    )
    corpus = offline.load_corpus_jsonl(source)
    rendered = "\n".join(
        (
            json.dumps(offline.profile_payload(offline.profile_corpus(corpus)), ensure_ascii=False),
            offline.candidate_jsonl_bytes(offline.mine_candidates(corpus)).decode("utf-8"),
        )
    ).casefold()
    for fragment in fragments:
        assert fragment.casefold() not in rendered

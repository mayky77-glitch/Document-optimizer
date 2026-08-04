"""Integration coverage for the private append-only Wave 4 store."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields

import pytest

from report_processor.reconciliation_patterns import feedback_graph as graph
from report_processor.reconciliation_patterns import offline
from report_processor.reconciliation_patterns import pattern_models as models
from report_processor.reconciliation_patterns import pattern_persistence as persistence
from report_processor.reconciliation_patterns import pattern_registry as registry


def _hash(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _history(name: str = "one") -> registry.RegistryHistory:
    scope = offline.PatternScope("scope", "quantity_cost", "unit", "action", "object", "document")
    proposal = offline.IncludeExcludeProposal(f"predicate-{name}", "accept")
    candidate_id = offline.fingerprint(
        {
            "version": offline.PATTERN_CANDIDATE_VERSION,
            "kind": offline.CandidateKind.INCLUDE_EXCLUDE.value,
            "scope": scope,
            "proposal": proposal,
        }
    )
    support = offline.SupportSummary(
        2, 2, 2, 2, 0, tuple(sorted((_hash(name + "-a"), _hash(name + "-b"))))
    )
    candidate = offline.PatternCandidate(
        "candidate",
        candidate_id,
        offline.CandidateKind.INCLUDE_EXCLUDE,
        scope,
        proposal,
        offline.OutcomeSignature("accept", "quantity_cost", "target"),
        support,
        (),
        offline.fingerprint({"candidate_id": candidate_id, "support": support, "risks": ()}),
    )
    versions = models.PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0")
    return registry.register_candidate(candidate, versions=versions, actor_ref=_hash("actor"))


def _edge(
    relation: models.FeedbackRelation,
    left: models.PatternRecord,
    right: models.PatternRecord,
    *,
    right_outcome: offline.OutcomeSignature | None = None,
) -> models.FeedbackEdge:
    source = models.FeedbackEndpoint(left.pattern_id, left.candidate_id, left.expected_outcome)
    target = models.FeedbackEndpoint(
        right.pattern_id, right.candidate_id, right_outcome or right.expected_outcome
    )
    assert source.outcome is not None and target.outcome is not None
    confirmations = tuple(
        sorted(
            (
                models.FeedbackConfirmation(
                    _hash("confirmation-left-" + relation.value),
                    _hash("document-left-" + relation.value),
                    _hash("apply-left-" + relation.value),
                    _hash("result-left-" + relation.value),
                    source.outcome,
                ),
                models.FeedbackConfirmation(
                    _hash("confirmation-right-" + relation.value),
                    _hash("document-right-" + relation.value),
                    _hash("apply-right-" + relation.value),
                    _hash("result-right-" + relation.value),
                    target.outcome,
                ),
            ),
            key=lambda item: item.confirmation_ref,
        )
    )
    provenance = models.FeedbackProvenance(
        confirmations,
        tuple(sorted(item.document_set_ref for item in confirmations)),
        tuple(sorted(item.apply_fingerprint for item in confirmations)),
        tuple(sorted(item.result_fingerprint for item in confirmations)),
    )
    return graph.create_explicit_edge(
        relation=relation,
        reason=(
            models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFIRMATION
            if relation is models.FeedbackRelation.MUST_LINK
            else models.FeedbackReason.EXPLICIT_AUTHORITATIVE_CONFLICT
        ),
        source=source,
        target=target,
        provenance=provenance,
    )


def _active(name: str) -> registry.RegistryHistory:
    history = _history(name)
    history = registry.move_to_shadow(
        history, expected_head=history.head, actor_ref=_hash("shadow")
    )
    history = registry.approve_head(
        history,
        expected_head=history.head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    return registry.import_verified_wave5_active(
        history,
        expected_head=history.head,
        activation=models.ActivationMetadata(
            _hash("activation-" + name), _hash("activation-fp-" + name), 4, _hash("wave5")
        ),
        actor_ref=_hash("wave5"),
    )


def _preactivation_conflict_batch(
    left: registry.RegistryHistory, right: registry.RegistryHistory
) -> tuple[
    models.FeedbackEdge,
    models.FeedbackEdge,
    tuple[models.PatternRecord, ...],
    tuple[tuple[models.PatternRecord, models.PatternRegistryEvent], ...],
]:
    must = _edge(models.FeedbackRelation.MUST_LINK, left.head, right.head)
    cannot = _edge(
        models.FeedbackRelation.CANNOT_LINK,
        left.head,
        right.head,
        right_outcome=offline.OutcomeSignature("accept", "quantity_cost", "observed-other"),
    )
    contradictions = graph.derive_contradictions(graph.create_feedback_graph(edges=(must, cannot)))
    left_next = registry.add_pre_activation_conflicts(
        left,
        expected_head=left.head,
        contradictions=contradictions,
        actor_ref=_hash("evidence-left"),
    )
    right_next = registry.add_pre_activation_conflicts(
        right,
        expected_head=right.head,
        contradictions=contradictions,
        actor_ref=_hash("evidence-right"),
    )
    heads = tuple(sorted((left.head, right.head), key=lambda item: item.pattern_id))
    next_by_id = {
        left_next.head.pattern_id: (left_next.head, left_next.head_event),
        right_next.head.pattern_id: (right_next.head, right_next.head_event),
    }
    return must, cannot, heads, tuple(next_by_id[head.pattern_id] for head in heads)


def _mutate_immutable_row(
    connection: sqlite3.Connection,
    *,
    trigger_name: str,
    statement: str,
    params: tuple[object, ...] = (),
) -> None:
    trigger_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = ?", (trigger_name,)
    ).fetchone()[0]
    connection.execute(f"DROP TRIGGER {trigger_name}")
    connection.execute(statement, params)
    connection.execute(trigger_sql)


def test_creates_private_v1_store_pragmas_reopens_and_round_trips(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    history = _history()
    with persistence.PatternRegistryStore(path) as store:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert store._connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert store._connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert store._connection.execute("PRAGMA trusted_schema").fetchone()[0] == 0
        store.append_history(history)
        store.append_history(history)
        assert store.load_history(history.head.pattern_id) == history
        assert store.integrity_report(history.head.pattern_id).valid
    with persistence.PatternRegistryStore(path) as reopened:
        assert reopened.load_history(history.head.pattern_id) == history


@pytest.mark.parametrize("path", ["relative.sqlite", ":memory:", "file:registry.sqlite"])
def test_rejects_non_explicit_paths(path: str) -> None:
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "PATH_INVALID"


def test_rejects_mode_and_schema_tampering_and_append_only_triggers(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    history = _history()
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(history)
        with pytest.raises(sqlite3.DatabaseError):
            store._connection.execute("DELETE FROM records")
        store._connection.execute("DROP TRIGGER records_no_update")
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "SCHEMA_TAMPERED"
    os.chmod(path, 0o644)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "PATH_UNSAFE"


def test_rejects_unknown_nonempty_v0_database(tmp_path) -> None:
    path = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE legacy (value TEXT)")
    connection.commit()
    connection.close()
    os.chmod(path, 0o600)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "SCHEMA_UNSUPPORTED"


def test_rejects_same_name_noop_trigger_and_non_v1_schema(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    with persistence.PatternRegistryStore(path) as store:
        store._connection.execute("DROP TRIGGER records_no_update")
        store._connection.execute(
            "CREATE TRIGGER records_no_update BEFORE UPDATE ON records BEGIN SELECT 1; END"
        )
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "SCHEMA_TAMPERED"

    versioned = tmp_path / "versioned.sqlite"
    with persistence.PatternRegistryStore(versioned) as store:
        store._connection.execute("PRAGMA user_version = 2")
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(versioned)
    assert error.value.code == "SCHEMA_UNSUPPORTED"


def test_old_exact_history_prefix_is_stale_but_current_full_replay_is_idempotent(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    initial = _history()
    shadow = registry.move_to_shadow(initial, expected_head=initial.head, actor_ref=_hash("shadow"))
    approved = registry.approve_head(
        shadow,
        expected_head=shadow.head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(initial)
        store.append_history(shadow)
        store.append_history(approved)
        store.append_history(approved)
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_history(shadow)
    assert error.value.code == "STALE_HEAD"


def test_conflicting_edge_requires_and_atomically_persists_preactivation_revisions(
    tmp_path,
) -> None:
    path = tmp_path / "registry.sqlite"
    left, right = _history("left"), _history("right")
    must = _edge(models.FeedbackRelation.MUST_LINK, left.head, right.head)
    observed_conflict = offline.OutcomeSignature("accept", "quantity_cost", "observed-other")
    cannot = _edge(
        models.FeedbackRelation.CANNOT_LINK,
        left.head,
        right.head,
        right_outcome=observed_conflict,
    )
    combined = graph.create_feedback_graph(edges=(must, cannot))
    contradictions = graph.derive_contradictions(combined)
    left_next = registry.add_pre_activation_conflicts(
        left,
        expected_head=left.head,
        contradictions=tuple(
            item
            for item in contradictions
            if left.head.pattern_id in {item.left_pattern_id, item.right_pattern_id}
        ),
        actor_ref=_hash("evidence"),
    )
    right_next = registry.add_pre_activation_conflicts(
        right,
        expected_head=right.head,
        contradictions=tuple(
            item
            for item in contradictions
            if right.head.pattern_id in {item.left_pattern_id, item.right_pattern_id}
        ),
        actor_ref=_hash("evidence"),
    )
    ordered_heads = tuple(sorted((left.head, right.head), key=lambda item: item.pattern_id))
    next_by_id = {
        left_next.head.pattern_id: (left_next.head, left_next.head_event),
        right_next.head.pattern_id: (right_next.head, right_next.head_event),
    }
    revisions = tuple(next_by_id[head.pattern_id] for head in ordered_heads)
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(left)
        store.append_history(right)
        store.append_edge(must, records=(left.head, right.head))
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_edge(cannot, records=(left.head, right.head))
        assert error.value.code == "CONFLICT_REVISIONS_REQUIRED"
        store.append_edge_and_revisions(
            cannot,
            records=(left.head, right.head),
            revisions=revisions,
            expected_heads=ordered_heads,
        )
        assert store.load_history(left.head.pattern_id).head == left_next.head
        assert store.load_history(right.head.pattern_id).head == right_next.head


def test_rejects_parent_leaf_symlink_and_hardlink_store_paths(tmp_path) -> None:
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    parent_link = tmp_path / "linked"
    parent_link.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(parent_link / "registry.sqlite")
    assert error.value.code == "PATH_UNSAFE"

    path = real_parent / "registry.sqlite"
    with persistence.PatternRegistryStore(path):
        pass
    leaf_link = tmp_path / "leaf.sqlite"
    leaf_link.symlink_to(path)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(leaf_link)
    assert error.value.code == "PATH_UNSAFE"

    hard_link = tmp_path / "hard.sqlite"
    os.link(path, hard_link)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(hard_link)
    assert error.value.code == "PATH_UNSAFE"


def test_open_store_rejects_post_open_path_inode_replacement(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    incoming = tmp_path / "incoming.sqlite"
    original = _history("original-inode")
    with persistence.PatternRegistryStore(incoming):
        pass
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(original)
        os.replace(incoming, path)
        with pytest.raises(models.PatternRegistryError) as read_error:
            store.load_history(original.head.pattern_id)
        assert read_error.value.code == "PATH_RACE"
        with pytest.raises(models.PatternRegistryError) as write_error:
            store.append_history(_history("replacement-write"))
        assert write_error.value.code == "PATH_RACE"
    with (
        persistence.PatternRegistryStore(path) as replacement,
        pytest.raises(models.PatternRegistryError) as missing_error,
    ):
        replacement.load_history(original.head.pattern_id)
    assert missing_error.value.code == "PATTERN_NOT_FOUND"


def test_constructor_detects_inode_replacement_before_mutating_replacement(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "registry.sqlite"
    incoming = tmp_path / "incoming.sqlite"
    connection = sqlite3.connect(incoming)
    connection.execute("CREATE TABLE sentinel (value TEXT NOT NULL)")
    connection.execute("INSERT INTO sentinel VALUES ('unchanged')")
    connection.commit()
    connection.close()
    os.chmod(incoming, 0o600)
    original_bytes = incoming.read_bytes()
    real_connect = sqlite3.connect

    def replace_before_connect(database, *args, **kwargs):
        os.replace(incoming, path)
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(persistence.sqlite3, "connect", replace_before_connect)
    with pytest.raises(models.PatternRegistryError) as error:
        persistence.PatternRegistryStore(path)
    assert error.value.code == "PATH_RACE"
    assert path.read_bytes() == original_bytes
    replacement = real_connect(path)
    try:
        tables = {
            row[0]
            for row in replacement.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        }
        assert tables == {"sentinel"}
        assert replacement.execute("PRAGMA user_version").fetchone() == (0,)
    finally:
        replacement.close()


def test_private_execute_seam_exists_for_transactional_fault_injection() -> None:
    assert callable(getattr(persistence.PatternRegistryStore, "_execute", None))


def test_record_then_event_insert_failure_rolls_back_entire_history(tmp_path, monkeypatch) -> None:
    path = tmp_path / "registry.sqlite"
    history = _history("fault-injection")
    with persistence.PatternRegistryStore(path) as store:
        execute = store._execute

        def fail_event_insert(sql: str, params: tuple[object, ...] = ()):
            if "INSERT INTO pattern_events" in sql:
                raise models.PatternRegistryError("INJECTED_FAILURE", "injected failure")
            return execute(sql, params)

        monkeypatch.setattr(store, "_execute", fail_event_insert)
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_history(history)
        assert error.value.code == "INJECTED_FAILURE"
        assert store._connection.execute("SELECT COUNT(*) FROM records").fetchone() == (0,)
        assert store._connection.execute("SELECT COUNT(*) FROM pattern_events").fetchone() == (0,)
    with (
        persistence.PatternRegistryStore(path) as reopened,
        pytest.raises(models.PatternRegistryError) as error,
    ):
        reopened.load_history(history.head.pattern_id)
    assert error.value.code == "PATTERN_NOT_FOUND"


def test_exact_supersession_plan_replay_is_idempotent_and_retires_old_head(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    original = _history("superseded")
    replacement_record = _history("replacement").head
    replacement = offline.PatternCandidate(
        "candidate",
        replacement_record.candidate_id,
        replacement_record.candidate_kind,
        replacement_record.scope,
        replacement_record.template,
        replacement_record.expected_outcome,
        replacement_record.support,
        replacement_record.risk_codes,
        replacement_record.candidate_fingerprint,
    )
    plan = registry.plan_supersession(
        original,
        replacement,
        expected_head=original.head,
        versions=models.PatternVersions("Parser-1.0", "Model-1.0", "Taxonomy-1.0"),
        actor_ref=_hash("supersession"),
    )
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(original)
        store.apply_plan(plan)
        store.apply_plan(plan)
        assert (
            store.load_history(original.head.pattern_id).head.state is models.PatternState.RETIRED
        )
        assert (
            store.load_history(replacement.candidate_id).head.state is models.PatternState.PROPOSED
        )


def test_two_independent_store_connections_commit_one_next_revision(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    initial = _history("concurrent")
    shadow = registry.move_to_shadow(initial, expected_head=initial.head, actor_ref=_hash("shadow"))
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(initial)

    def append_once() -> str:
        with persistence.PatternRegistryStore(path) as store:
            try:
                store.append_history(shadow)
            except models.PatternRegistryError as error:
                return error.code
        return "OK"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: append_once(), range(2)))
    assert set(results) <= {"OK", "STALE_HEAD", "STORE_BUSY"}
    with persistence.PatternRegistryStore(path) as store:
        assert store.load_history(initial.head.pattern_id) == shadow
        assert store._connection.execute("SELECT COUNT(*) FROM records").fetchone() == (2,)
        assert store._connection.execute("SELECT COUNT(*) FROM pattern_events").fetchone() == (2,)


def test_owner_approved_conflict_batch_fails_before_edge_write(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    left = registry.approve_head(
        registry.move_to_shadow(
            _history("owner-left"), expected_head=_history("owner-left").head, actor_ref=_hash("x")
        ),
        expected_head=registry.move_to_shadow(
            _history("owner-left"), expected_head=_history("owner-left").head, actor_ref=_hash("x")
        ).head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    right = registry.approve_head(
        registry.move_to_shadow(
            _history("owner-right"),
            expected_head=_history("owner-right").head,
            actor_ref=_hash("y"),
        ),
        expected_head=registry.move_to_shadow(
            _history("owner-right"),
            expected_head=_history("owner-right").head,
            actor_ref=_hash("y"),
        ).head,
        owner_ref=_hash("owner"),
        approval_ref=_hash("approval"),
    )
    must = _edge(models.FeedbackRelation.MUST_LINK, left.head, right.head)
    cannot = _edge(
        models.FeedbackRelation.CANNOT_LINK,
        left.head,
        right.head,
        right_outcome=offline.OutcomeSignature("accept", "quantity_cost", "observed-owner"),
    )
    heads = tuple(sorted((left.head, right.head), key=lambda item: item.pattern_id))
    revisions = tuple(
        (head, left.head_event if head.pattern_id == left.head.pattern_id else right.head_event)
        for head in heads
    )
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(left)
        store.append_history(right)
        store.append_edge(must, records=(left.head, right.head))
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_edge_and_revisions(
                cannot, records=(left.head, right.head), revisions=revisions, expected_heads=heads
            )
        assert error.value.code == "CONFLICT_STATE_UNREPRESENTABLE"
        assert store._connection.execute("SELECT COUNT(*) FROM feedback_edges").fetchone() == (1,)


def test_active_conflict_batch_requires_suspension_revisions(tmp_path) -> None:
    path = tmp_path / "registry.sqlite"
    left, right = _active("active-left"), _active("active-right")
    must = _edge(models.FeedbackRelation.MUST_LINK, left.head, right.head)
    cannot = _edge(
        models.FeedbackRelation.CANNOT_LINK,
        left.head,
        right.head,
        right_outcome=offline.OutcomeSignature("accept", "quantity_cost", "observed-active"),
    )
    contradictions = graph.derive_contradictions(graph.create_feedback_graph(edges=(must, cannot)))
    left_next = registry.suspend_active_for_conflict(
        left, expected_head=left.head, contradictions=contradictions, actor_ref=_hash("evidence")
    )
    right_next = registry.suspend_active_for_conflict(
        right, expected_head=right.head, contradictions=contradictions, actor_ref=_hash("evidence")
    )
    heads = tuple(sorted((left.head, right.head), key=lambda item: item.pattern_id))
    next_by_id = {
        left_next.head.pattern_id: (left_next.head, left_next.head_event),
        right_next.head.pattern_id: (right_next.head, right_next.head_event),
    }
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(left)
        store.append_history(right)
        store.append_edge(must, records=(left.head, right.head))
        store.append_edge_and_revisions(
            cannot,
            records=(left.head, right.head),
            revisions=tuple(next_by_id[head.pattern_id] for head in heads),
            expected_heads=heads,
        )
        assert store.load_history(left.head.pattern_id).head.state is models.PatternState.SUSPENDED
        assert store.load_history(right.head.pattern_id).head.state is models.PatternState.SUSPENDED


@pytest.mark.parametrize("tamper", ["payload", "fingerprint"])
def test_load_rejects_noncanonical_payload_and_sql_identity_tampering(tmp_path, tamper) -> None:
    path = tmp_path / f"{tamper}.sqlite"
    history = _history(tamper)
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(history)
        if tamper == "payload":
            statement = "UPDATE records SET payload = ? WHERE pattern_id = ?"
            params = (b" " + persistence._payload(history.head), history.head.pattern_id)
        else:
            statement = "UPDATE records SET fingerprint = ? WHERE pattern_id = ?"
            params = (_hash("wrong-sql-fingerprint"), history.head.pattern_id)
        _mutate_immutable_row(
            store._connection,
            trigger_name="records_no_update",
            statement=statement,
            params=params,
        )
    with (
        persistence.PatternRegistryStore(path) as reopened,
        pytest.raises(models.PatternRegistryError) as error,
    ):
        reopened.load_history(history.head.pattern_id)
    assert error.value.code == "STORE_TAMPERED"


def test_load_rejects_missing_event_row_after_schema_preserving_tamper(tmp_path) -> None:
    path = tmp_path / "missing-event.sqlite"
    history = _history("missing-event")
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(history)
        _mutate_immutable_row(
            store._connection,
            trigger_name="pattern_events_no_delete",
            statement="DELETE FROM pattern_events WHERE pattern_id = ?",
            params=(history.head.pattern_id,),
        )
    with (
        persistence.PatternRegistryStore(path) as reopened,
        pytest.raises(models.PatternRegistryError) as error,
    ):
        reopened.load_history(history.head.pattern_id)
    assert error.value.code == "EVENT_CHAIN_INVALID"


def test_load_rejects_canonical_but_invalid_lifecycle_jump(tmp_path) -> None:
    path = tmp_path / "invalid-lifecycle.sqlite"
    history = _history("invalid-lifecycle")
    head = history.head
    values = {
        field.name: getattr(head, field.name)
        for field in fields(models.PatternRecord)
        if field.name != "fingerprint"
    }
    invalid = models.create_pattern_record(
        **{
            **values,
            "revision": 2,
            "previous_fingerprint": head.fingerprint,
            "state": models.PatternState.OWNER_APPROVED,
            "owner": models.OwnerApproval(_hash("owner"), _hash("approval"), 2),
        }
    )
    event = models.create_pattern_registry_event(
        event_id=_hash("invalid-lifecycle-event"),
        event_type=models.PatternRegistryEventType.STATE_TRANSITION,
        pattern_id=head.pattern_id,
        revision=2,
        previous_event_fingerprint=history.head_event.fingerprint,
        payload_fingerprint=invalid.fingerprint,
        actor_ref=_hash("actor"),
    )
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(history)
        store._connection.execute(
            "INSERT INTO records VALUES (?, ?, ?, ?)",
            (
                invalid.pattern_id,
                invalid.revision,
                invalid.fingerprint,
                persistence._payload(invalid),
            ),
        )
        store._connection.execute(
            "INSERT INTO pattern_events VALUES (?, ?, ?, ?)",
            (event.pattern_id, event.revision, event.fingerprint, persistence._payload(event)),
        )
    with (
        persistence.PatternRegistryStore(path) as reopened,
        pytest.raises(models.PatternRegistryError) as error,
    ):
        reopened.load_history(head.pattern_id)
    assert error.value.code == "STATE_TRANSITION_INVALID"


def test_conflict_edge_insert_failure_rolls_back_edge_records_and_events(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "conflict-failure.sqlite"
    left, right = _history("failure-left"), _history("failure-right")
    must, cannot, heads, revisions = _preactivation_conflict_batch(left, right)
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(left)
        store.append_history(right)
        store.append_edge(must, records=(left.head, right.head))
        execute = store._execute

        def fail_after_edge(sql: str, params: tuple[object, ...] = ()):
            result = execute(sql, params)
            if "INSERT INTO feedback_edges" in sql:
                raise models.PatternRegistryError("INJECTED_FAILURE", "injected failure")
            return result

        monkeypatch.setattr(store, "_execute", fail_after_edge)
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_edge_and_revisions(
                cannot,
                records=(left.head, right.head),
                revisions=revisions,
                expected_heads=heads,
            )
        assert error.value.code == "INJECTED_FAILURE"
        assert store._connection.execute("SELECT COUNT(*) FROM feedback_edges").fetchone() == (1,)
        assert store._connection.execute("SELECT COUNT(*) FROM records").fetchone() == (2,)
        assert store._connection.execute("SELECT COUNT(*) FROM pattern_events").fetchone() == (2,)
    with persistence.PatternRegistryStore(path) as reopened:
        assert reopened.load_graph().edges == (must,)
        assert reopened.load_history(left.head.pattern_id) == left
        assert reopened.load_history(right.head.pattern_id) == right


def test_conflict_batch_rejects_missing_revisions_and_preexisting_partial_edge(
    tmp_path,
) -> None:
    path = tmp_path / "partial-conflict.sqlite"
    left, right = _history("partial-left"), _history("partial-right")
    must, cannot, heads, revisions = _preactivation_conflict_batch(left, right)
    with persistence.PatternRegistryStore(path) as store:
        store.append_history(left)
        store.append_history(right)
        store.append_edge(must, records=(left.head, right.head))
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_edge_and_revisions(
                cannot,
                records=(left.head, right.head),
                revisions=revisions[:1],
                expected_heads=heads,
            )
        assert error.value.code == "CONFLICT_REVISIONS_INVALID"
        assert store.load_graph().edges == (must,)

        store._connection.execute(
            "INSERT INTO feedback_edges VALUES (?, ?, ?)",
            (cannot.edge_id, cannot.fingerprint, persistence._payload(cannot)),
        )
        with pytest.raises(models.PatternRegistryError) as error:
            store.append_edge_and_revisions(
                cannot,
                records=(left.head, right.head),
                revisions=revisions,
                expected_heads=heads,
            )
        assert error.value.code == "PARTIAL_REPLAY"
        assert store.load_history(left.head.pattern_id) == left
        assert store.load_history(right.head.pattern_id) == right

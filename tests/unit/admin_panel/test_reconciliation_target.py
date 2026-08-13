"""Fail-closed target index and stage selection contracts."""

from __future__ import annotations

import pytest

from report_processor.admin_panel.reconciliation_target import (
    ReconciliationTargetScopeError,
    resolve_reconciliation_stage,
    terminal_index,
)


def test_terminal_index_rejects_year_and_ambiguous_values() -> None:
    assert terminal_index("1234") == "1234"
    assert terminal_index("1234 2025") is None
    assert terminal_index("2025") is None
    assert terminal_index("1234 (1) and 5678 (1)") is None


def test_stage_resolution_discovers_exactly_one_stage_only() -> None:
    assert resolve_reconciliation_stage(("13.1",), None) == "13.1"
    assert resolve_reconciliation_stage(("13.1",), "13.1") == "13.1"
    with pytest.raises(ReconciliationTargetScopeError, match="MISSING"):
        resolve_reconciliation_stage(("13.1",), "99.9")
    with pytest.raises(ReconciliationTargetScopeError, match="AMBIGUOUS"):
        resolve_reconciliation_stage(("13.1", "13.2"), None)
    with pytest.raises(ReconciliationTargetScopeError, match="EMPTY"):
        resolve_reconciliation_stage((), None)

"""Fail-closed target index and stage selection contracts."""

from __future__ import annotations

import pytest

from report_processor.admin_panel.reconciliation_target import (
    ReconciliationTargetScopeError,
    resolve_reconciliation_stage,
    terminal_index,
)


class _Sheet:
    def __init__(self, values):
        self.max_row = len(values)
        self._values = values

    def cell(self, row, column):
        from types import SimpleNamespace

        return SimpleNamespace(value=self._values[row - 1][column - 1])


class _Session:
    def __init__(self, values):
        self.formula_workbook = type("Workbook", (), {"worksheets": (_Sheet(values),)})()


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


def test_stage_enumeration_ignores_header_and_notes_without_index() -> None:
    from report_processor.admin_panel.reconciliation_target import enumerate_reconciliation_stages

    session = _Session(
        (("", "", "Этап"), ("", "", "Примечание"), ("", "1234", "Этап 13.1. Работы"))
    )

    assert enumerate_reconciliation_stages(session) == ("13.1",)

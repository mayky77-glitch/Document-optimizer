"""Synthetic and opt-in private-workbook acceptance for reconciliation."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from report_processor.admin_panel.reconciliation_execution import prepare_review
from report_processor.admin_panel.reconciliation_sources import (
    AllReconciliationSourcesUnusableError,
    ReconciliationSourceDescriptor,
    extract_reconciliation_sources,
)


def _ks2(path: Path, *, work_name: str = "Монтаж трубы") -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(("№", "Наименование работ", "Ед. изм.", "Количество", "Общая стоимость"))
    sheet.append(("1", work_name, "м", "1.25", "1250.50"))
    workbook.save(path)
    workbook.close()


def _source_input(path: Path, source_id: str, basename: str):
    return path, source_id, ReconciliationSourceDescriptor(basename)


def test_partial_source_failure_keeps_usable_synthetic_source_and_safe_guidance(
    tmp_path: Path,
) -> None:
    usable = tmp_path / "source-1234.xlsx"
    unusable = tmp_path / "bad-source.xlsx"
    _ks2(usable)
    unusable.write_bytes(b"not-an-xlsx")

    batch = extract_reconciliation_sources(
        (
            _source_input(unusable, "source:bad", "bad-source.xlsx"),
            _source_input(usable, "source:good", "source-1234.xlsx"),
        )
    )

    assert len(batch.rows) == 1
    assert batch.selections[0].safe_basename == "source-1234.xlsx"
    assert batch.issues[0].code == "WORKBOOK_UNREADABLE"
    assert batch.issues[0].safe_basename == "bad-source.xlsx"
    assert batch.issues[0].can_continue is True
    assert str(tmp_path) not in repr(batch.issues)


def test_all_bad_sources_return_only_controlled_safe_basename_guidance(tmp_path: Path) -> None:
    bad = tmp_path / "input.xlsx"
    bad.write_bytes(b"not-an-xlsx")

    with pytest.raises(AllReconciliationSourcesUnusableError) as raised:
        extract_reconciliation_sources((_source_input(bad, "source:bad", "input.xlsx"),))

    (issue,) = raised.value.issues
    assert issue.code == "WORKBOOK_UNREADABLE"
    assert issue.safe_basename == "input.xlsx"
    assert issue.comment and issue.repair_hint and issue.can_continue is True
    assert str(tmp_path) not in repr(issue)


def test_opt_in_real_workbooks_leave_all_input_bytes_unchanged() -> None:
    source_values = tuple(
        value
        for value in os.environ.get("RECONCILIATION_REAL_SOURCE_PATHS", "").split(os.pathsep)
        if value
    )
    target_value = os.environ.get("RECONCILIATION_REAL_TARGET_PATH")
    stage = os.environ.get("RECONCILIATION_REAL_STAGE")
    if not source_values or not target_value or not stage:
        pytest.skip(
            "set RECONCILIATION_REAL_SOURCE_PATHS, RECONCILIATION_REAL_TARGET_PATH "
            "and RECONCILIATION_REAL_STAGE"
        )

    sources = tuple(Path(value) for value in source_values)
    target = Path(target_value)
    assert all(path.is_file() for path in (*sources, target))
    before = {path: sha256(path.read_bytes()).hexdigest() for path in (*sources, target)}
    job = SimpleNamespace(
        sources=sources,
        source=sources[0],
        source_names=tuple(path.name for path in sources),
        source_digests=tuple(before[path] for path in sources),
        target=target,
        target_digest=before[target],
        stage=stage,
        rules_path=None,
    )

    result = prepare_review(job, ())

    assert result.state is not None or result.source_issues or result.target_error
    assert {path: sha256(path.read_bytes()).hexdigest() for path in (*sources, target)} == before

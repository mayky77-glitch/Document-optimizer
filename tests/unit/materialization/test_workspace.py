from pathlib import Path

import pytest

from report_processor.materialization.workspace import TemporaryWorkspace


def test_workspace_removed_after_success(tmp_path: Path):
    with TemporaryWorkspace(tmp_path) as workspace:
        marker = workspace / "marker.txt"
        marker.write_text("x", encoding="utf-8")
        assert workspace.exists()
    assert not workspace.exists()


def test_workspace_removed_after_exception(tmp_path: Path):
    workspace = None
    with pytest.raises(RuntimeError), TemporaryWorkspace(tmp_path) as current:
        workspace = current
        raise RuntimeError("boom")
    assert workspace is not None
    assert not workspace.exists()


def test_parallel_workspaces_do_not_conflict(tmp_path: Path):
    with TemporaryWorkspace(tmp_path) as first, TemporaryWorkspace(tmp_path) as second:
        assert first != second
        assert first.exists() and second.exists()

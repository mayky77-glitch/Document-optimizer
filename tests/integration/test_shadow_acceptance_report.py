"""Filesystem boundary checks for the Wave 9 shadow acceptance report."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from report_processor.reconciliation_patterns import acceptance, acceptance_report, replay


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _decision() -> acceptance.ShadowAcceptanceDecision:
    values = {
        "status": acceptance.ShadowAcceptanceStatus.FAIL,
        "reason_codes": ("BLOCKED",),
        "replay_fingerprint": _digest("replay"),
        "promotion_fingerprint": _digest("promotion"),
        "hard_gate_fingerprint": _digest("gates"),
        "threshold_fingerprint": _digest("thresholds"),
        "operational_fingerprint": _digest("operational"),
        "version": acceptance.RECONCILIATION_SHADOW_ACCEPTANCE_VERSION,
    }
    return acceptance.ShadowAcceptanceDecision(
        **values,
        fingerprint=replay.replay_fingerprint(values),
    )


def test_private_atomic_report_is_repeatable_and_mode_0600(tmp_path) -> None:
    target = tmp_path / "acceptance.json"
    first = acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=False)
    first_bytes = target.read_bytes()

    assert first == first_bytes
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    second = acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=True)
    assert second == first_bytes == target.read_bytes()


def test_report_writer_fails_closed_for_existing_symlink_and_unsafe_parent(tmp_path) -> None:
    target = tmp_path / "acceptance.json"
    destination = tmp_path / "destination.json"
    target.symlink_to(destination)
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=True)
    assert error.value.code == "REPORT_OUTPUT_UNSAFE"

    unsafe_parent = tmp_path / "unsafe"
    unsafe_parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            unsafe_parent / "acceptance.json", _decision(), overwrite=False
        )
    assert error.value.code == "REPORT_OUTPUT_UNSAFE"


def test_report_writer_rejects_existing_output_without_explicit_overwrite(tmp_path) -> None:
    target = tmp_path / "acceptance.json"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, 0o644)
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=False)
    assert error.value.code == "REPORT_OUTPUT_EXISTS"


def test_report_writer_rejects_nonregular_existing_output(tmp_path) -> None:
    target = tmp_path / "acceptance.json"
    target.mkdir()

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=True)

    assert error.value.code == "REPORT_OUTPUT_UNSAFE"


def test_report_writer_rejects_any_output_inside_git_worktree() -> None:
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            Path.cwd() / "shadow-acceptance-report.json", _decision(), overwrite=False
        )

    assert error.value.code == "REPORT_OUTPUT_UNSAFE"


def test_report_writer_rejects_non_bool_overwrite(tmp_path) -> None:
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            tmp_path / "acceptance.json",
            _decision(),
            overwrite=1,  # type: ignore[arg-type]
        )

    assert error.value.code == "REPORT_OUTPUT_UNSAFE"


def test_report_writer_keeps_verified_parent_fd_during_ancestor_swap(tmp_path, monkeypatch) -> None:
    safe_parent = tmp_path / "stable-parent"
    safe_parent.mkdir()
    git_parent = tmp_path / "git-parent"
    git_parent.mkdir()
    (git_parent / ".git").mkdir()
    held_parent = tmp_path / "held-parent"
    original_open = acceptance_report.os.open
    swapped = False

    def swap_after_opened_parent(name, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        descriptor = original_open(name, flags, mode, dir_fd=dir_fd)
        if name == "stable-parent" and not swapped:
            swapped = True
            safe_parent.rename(held_parent)
            safe_parent.symlink_to(git_parent, target_is_directory=True)
        return descriptor

    monkeypatch.setattr(acceptance_report.os, "open", swap_after_opened_parent)

    acceptance_report.write_shadow_acceptance_report(
        safe_parent / "acceptance.json", _decision(), overwrite=False
    )

    assert swapped
    assert (held_parent / "acceptance.json").is_file()
    assert not (git_parent / "acceptance.json").exists()


def test_report_writer_caps_payload_bytes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        acceptance_report,
        "shadow_acceptance_report_bytes",
        lambda decision, *, inputs=None: b"x" * (acceptance_report._MAX_REPORT_BYTES + 1),
    )

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            tmp_path / "acceptance.json", _decision(), overwrite=False
        )

    assert error.value.code == "REPORT_SCHEMA_INVALID"


def test_report_writer_rejects_ancestor_symlink_to_git(tmp_path) -> None:
    git_parent = tmp_path / "git-parent"
    git_parent.mkdir()
    (git_parent / ".git").mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(git_parent, target_is_directory=True)

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            linked_parent / "reports" / "acceptance.json", _decision(), overwrite=False
        )

    assert error.value.code == "REPORT_OUTPUT_UNSAFE"


def test_report_writer_never_clobbers_concurrent_output_without_overwrite(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "acceptance.json"
    original_link = acceptance_report.os.link
    raced = False

    def create_destination_before_link(src, dst, **kwargs):
        nonlocal raced
        raced = True
        descriptor = os.open(
            dst,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=kwargs["dst_dir_fd"],
        )
        os.write(descriptor, b"concurrent")
        os.close(descriptor)
        return original_link(src, dst, **kwargs)

    monkeypatch.setattr(acceptance_report.os, "link", create_destination_before_link)

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=False)

    assert raced
    assert error.value.code == "REPORT_OUTPUT_EXISTS"
    assert target.read_bytes() == b"concurrent"


def test_report_writer_rolls_back_if_open_parent_moves_under_git(tmp_path, monkeypatch) -> None:
    safe_parent = tmp_path / "stable-parent"
    safe_parent.mkdir()
    git_parent = tmp_path / "git-parent"
    git_parent.mkdir()
    (git_parent / ".git").mkdir()
    moved_parent = git_parent / "moved-parent"
    original_link = acceptance_report.os.link
    moved = False

    def move_parent_before_link(src, dst, **kwargs):
        nonlocal moved
        moved = True
        safe_parent.rename(moved_parent)
        return original_link(src, dst, **kwargs)

    monkeypatch.setattr(acceptance_report.os, "link", move_parent_before_link)

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(
            safe_parent / "acceptance.json", _decision(), overwrite=False
        )

    assert moved
    assert error.value.code == "REPORT_OUTPUT_UNSAFE"
    assert not (moved_parent / "acceptance.json").exists()


def test_overwrite_fsync_failure_never_removes_both_old_and_new_report(
    tmp_path, monkeypatch
) -> None:
    target = tmp_path / "acceptance.json"
    target.write_bytes(b"old")
    expected = acceptance_report.shadow_acceptance_report_bytes(_decision())
    original_fsync = acceptance_report.os.fsync
    calls = 0

    def fail_directory_fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("directory fsync failed")
        return original_fsync(descriptor)

    monkeypatch.setattr(acceptance_report.os, "fsync", fail_directory_fsync)

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.write_shadow_acceptance_report(target, _decision(), overwrite=True)

    assert error.value.code == "REPORT_OUTPUT_IO"
    assert target.read_bytes() in {b"old", expected}

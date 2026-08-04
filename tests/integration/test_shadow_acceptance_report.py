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
        "status": acceptance.ShadowAcceptanceStatus.PASS,
        "reason_codes": (),
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

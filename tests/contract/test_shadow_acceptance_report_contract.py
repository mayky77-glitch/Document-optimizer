"""Public privacy boundary for the Wave 9 shadow acceptance report."""

from __future__ import annotations

import hashlib
import json

import pytest

from report_processor.reconciliation_patterns import acceptance, acceptance_report, replay


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _decision(
    *, status: acceptance.ShadowAcceptanceStatus = acceptance.ShadowAcceptanceStatus.PASS
):
    values = {
        "status": status,
        "reason_codes": () if status is acceptance.ShadowAcceptanceStatus.PASS else ("BLOCKED",),
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


def test_report_is_canonical_controlled_aggregate_only() -> None:
    payload = acceptance_report.shadow_acceptance_report_bytes(_decision())

    assert payload == acceptance_report.shadow_acceptance_report_bytes(_decision())
    assert payload.endswith(b"\n")
    decoded = json.loads(payload)
    assert decoded == {
        "decision_fingerprint": _decision().fingerprint,
        "reason_codes": [],
        "schema_version": "ReconciliationShadowAcceptanceReport-1.0",
        "status": "PASS",
    }
    text = payload.decode("utf-8")
    for forbidden in ("replay", "promotion", "threshold", "operational", "path", "row", "formula"):
        assert forbidden not in text


def test_report_rejects_forged_or_raw_dto_without_echoing_raw_data() -> None:
    class ForgedDecision:
        status = acceptance.ShadowAcceptanceStatus.PASS
        reason_codes = ()
        fingerprint = _digest("forged")
        raw_workbook_path = "/restricted/report.xlsx"

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.shadow_acceptance_report_bytes(ForgedDecision())

    assert error.value.code == "REPORT_SCHEMA_INVALID"
    assert "/restricted/report.xlsx" not in str(error.value)


def test_report_rejects_raw_codes_and_fingerprint_tampering() -> None:
    decision = _decision(status=acceptance.ShadowAcceptanceStatus.FAIL)
    object.__setattr__(decision, "reason_codes", ("RAW_PATH_/restricted.xlsx",))
    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.shadow_acceptance_report_bytes(decision)
    assert error.value.code == "REPORT_SCHEMA_INVALID"


def test_report_rejects_pass_without_every_bound_evidence_fingerprint() -> None:
    decision = _decision()
    values = {
        field: getattr(decision, field)
        for field in (
            "status",
            "reason_codes",
            "replay_fingerprint",
            "promotion_fingerprint",
            "hard_gate_fingerprint",
            "threshold_fingerprint",
            "operational_fingerprint",
            "version",
        )
    }
    values["operational_fingerprint"] = None
    forged = acceptance.ShadowAcceptanceDecision(
        **values,
        fingerprint=replay.replay_fingerprint(values),
    )

    with pytest.raises(acceptance_report.ShadowAcceptanceReportError) as error:
        acceptance_report.shadow_acceptance_report_bytes(forged)

    assert error.value.code == "REPORT_SCHEMA_INVALID"

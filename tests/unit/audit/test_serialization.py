from __future__ import annotations

import pytest
from report_processor.audit import AuditRedactionError, canonical_json, redact


def test_canonical_json_is_sorted_utf8_safe_and_allowlist_is_strict() -> None:
    assert canonical_json({"count": 1, "run_id": "ид"}) == '{"count":1,"run_id":"ид"}'
    assert redact({"run_id": "r", "count": 1}) == {"count": 1, "run_id": "r"}
    with pytest.raises(AuditRedactionError):
        redact({"formula": "=A1"})


def test_nested_values_are_rejected_at_the_audit_boundary() -> None:
    with pytest.raises(AuditRedactionError, match="nested"):
        redact({"run_id": ["never", "export"]})

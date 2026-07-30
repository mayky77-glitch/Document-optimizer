"""Deterministic export, no-clobber and redaction evidence."""

from __future__ import annotations

from hashlib import sha256

import pytest
from report_processor.audit import (
    AuditExportError,
    AuditRedactionError,
    deterministic_bytes,
    export_snapshot,
    validate_bytes,
)

from fixtures.audit.builders import export_rows


@pytest.mark.parametrize("format", ("json", "jsonl", "csv"))
def test_reverse_order_exports_are_byte_identical_and_valid(format: str) -> None:
    forward = deterministic_bytes(export_rows(), format)
    reverse = deterministic_bytes(reversed(export_rows()), format)
    assert forward == reverse
    validate_bytes(forward, format, 2, sha256(forward).hexdigest())


def test_existing_destination_is_never_clobbered_and_temp_files_are_cleaned(tmp_path) -> None:
    destination = tmp_path / "audit.json"
    destination.write_bytes(b"preserve")
    with pytest.raises(AuditExportError, match="EXPORT_DESTINATION_EXISTS"):
        export_snapshot(export_rows(), destination, "json")
    assert destination.read_bytes() == b"preserve"
    assert not tuple(tmp_path.glob(".audit-*.tmp"))


def test_leak_canary_never_reaches_serialized_bytes_without_printing_it() -> None:
    canary = "CANARY-SECRET-DO-NOT-LOG"
    with pytest.raises(AuditRedactionError):
        deterministic_bytes(({"run_id": "safe", "raw_values": canary},), "json")

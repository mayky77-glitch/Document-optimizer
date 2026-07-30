"""Block 9 must never mutate the selected target workbook."""

from __future__ import annotations

from hashlib import sha256

from report_processor.schema import LogicalColumn, SheetType, WorkbookSchema
from report_processor.target_report import TargetReportReadRequest, read_target_report


def test_read_target_report_keeps_source_sha_and_stat_unchanged(
    workbook_session_factory, schema_factory
) -> None:
    with workbook_session_factory({"Целевой": [["Код"], ["0007"]]}) as (session, path):
        worksheet = schema_factory("Целевой", SheetType.KS6A, (LogicalColumn.OBJECT_CODE,))
        schema = WorkbookSchema("file-001", path.name, (worksheet,), {}, {}, 1.0, "OK")
        before_stat = path.stat()
        before = path.read_bytes()
        result = read_target_report(session, schema, TargetReportReadRequest())
        after_stat = path.stat()
        after = path.read_bytes()

    assert after == before
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
    assert result.schema.source_fingerprint.digest == sha256(before).hexdigest()

from __future__ import annotations

import hashlib


def _frame(value: str | None) -> bytes:
    payload = (value or "").encode("utf-8")
    return len(payload).to_bytes(4, "big") + payload


def make_line_id(
    *,
    source_file_id: str,
    document_type: str,
    document_period: str | None,
    object_code: str | None,
    subobject_code: str | None,
    position_code: str | None,
    basis_code: str | None,
    drawing_code: str | None,
    unit: str | None,
    work_name: str | None,
) -> str:
    digest = hashlib.sha256()
    for value in (
        source_file_id,
        document_type,
        document_period,
        object_code,
        subobject_code,
        position_code,
        basis_code,
        drawing_code,
        unit,
        work_name,
    ):
        digest.update(_frame(value))
    return digest.hexdigest()


def disambiguate_line_id(line_id: str, source_row_id: str) -> str:
    digest = hashlib.sha256()
    digest.update(_frame(line_id))
    digest.update(_frame(source_row_id))
    return digest.hexdigest()

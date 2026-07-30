from __future__ import annotations

import logging
from pathlib import Path

from report_processor.domain.exceptions import MaterializationError
from report_processor.domain.statuses import StatusCode

from .models import MaterializationRequest, MaterializedSource
from .regular_file import resolve_regular_file
from .zip_entry import materialize_zip_entry

LOGGER = logging.getLogger(__name__)


def materialize_source(
    request: MaterializationRequest,
    *,
    workspace: Path | None = None,
) -> MaterializedSource:
    entry = request.candidate.entry
    LOGGER.info(
        "Начало материализации: %s, размер=%s",
        "zip_entry" if entry.is_archive_entry else "regular_file",
        entry.size_bytes,
    )
    if entry.is_archive_entry:
        if workspace is None:
            raise MaterializationError(
                StatusCode.WORKSPACE_CREATION_FAILED,
                "Для ZIP-записи требуется временная область",
            )
        return materialize_zip_entry(
            entry,
            workspace,
            max_file_size_bytes=request.max_file_size_bytes,
            verify_crc=request.verify_zip_crc,
        )
    return resolve_regular_file(entry, max_file_size_bytes=request.max_file_size_bytes)

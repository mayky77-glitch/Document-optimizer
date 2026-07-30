from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from report_processor.inventory.file_manifest import file_manifest_entry_to_dict
from report_processor.selection.models import (
    SourceCandidate,
    SourceSelectionRequest,
    SourceSelectionResult,
)


def _atomic_write_json(data: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=output_path.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(data, temporary_file, ensure_ascii=False, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def selection_result_to_dict(
    result: SourceSelectionResult,
    request: SourceSelectionRequest,
) -> dict[str, Any]:
    return {
        "status": str(result.status),
        "request": {
            "target_index": request.target_index.normalized,
            "target_period": (request.target_period.normalized if request.target_period else None),
            "preferred_document_types": list(request.preferred_document_types),
            "allowed_document_types": list(request.allowed_document_types),
            "require_exact_period": request.require_exact_period,
            "allow_unknown_period": request.allow_unknown_period,
            "include_probable_copies": request.include_probable_copies,
            "include_outdated": request.include_outdated,
            "include_drafts": request.include_drafts,
        },
        "selected": _candidate_to_dict(result.selected) if result.selected else None,
        "candidates": [_candidate_to_dict(candidate) for candidate in result.candidates],
        "rejected": [_candidate_to_dict(candidate) for candidate in result.rejected],
        "warnings": list(result.warnings),
        "explanation": list(result.explanation),
    }


def save_selection_result_json(
    result: SourceSelectionResult,
    request: SourceSelectionRequest,
    output_path: Path,
) -> None:
    _atomic_write_json(selection_result_to_dict(result, request), output_path)


def _candidate_to_dict(candidate: SourceCandidate) -> dict[str, Any]:
    entry = candidate.entry
    return {
        "file_id": candidate.file_id,
        "entry": file_manifest_entry_to_dict(entry),
        "relative_path": entry.relative_path,
        "archive_path": entry.archive_path,
        "document_type": entry.document_type,
        "document_period": (entry.document_period.normalized if entry.document_period else None),
        "document_revision": (entry.document_revision.number if entry.document_revision else None),
        "score": candidate.score,
        "rank": candidate.rank,
        "accepted": candidate.accepted,
        "rejection_reasons": list(candidate.rejection_reasons),
        "score_components": [
            {
                "code": component.code,
                "points": component.points,
                "explanation": component.explanation,
            }
            for component in candidate.score_components
        ],
        "warnings": list(candidate.warnings),
    }

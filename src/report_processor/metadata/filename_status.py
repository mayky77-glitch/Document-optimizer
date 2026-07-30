from __future__ import annotations

import re
from dataclasses import dataclass

from report_processor.inventory.file_classifier import classify_file_by_name
from report_processor.metadata.revisions import (
    RevisionExtractionResult,
    extract_document_revision,
)


@dataclass(frozen=True, slots=True)
class FilenameStatusMetadata:
    is_temporary: bool
    is_probable_copy: bool
    is_probably_outdated: bool
    is_draft: bool
    is_final: bool
    is_approved: bool
    revision_result: RevisionExtractionResult


def extract_filename_status(filename: str) -> FilenameStatusMetadata:
    classification = classify_file_by_name(filename)
    revision = extract_document_revision(filename)
    value = revision.value
    has_copy_suffix = bool(re.search(r"\(\d{1,2}\)", filename))
    return FilenameStatusMetadata(
        is_temporary=classification.is_temporary,
        is_probable_copy=classification.is_probable_copy or has_copy_suffix,
        is_probably_outdated=classification.is_probably_outdated,
        is_draft=bool(value and value.is_draft),
        is_final=bool(value and value.is_final),
        is_approved=bool(value and value.is_approved),
        revision_result=revision,
    )

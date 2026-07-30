"""Public API for document-index handling."""

from report_processor.identifiers.document_index import (
    document_index_matches_parts,
    document_indexes_equal,
    extract_document_index,
    extract_index_from_filename,
    extract_index_from_path,
)
from report_processor.identifiers.models import (
    DocumentIndex,
    IndexCandidate,
    IndexExtractionResult,
)
from report_processor.identifiers.normalization import normalize_identifier_text

__all__ = [
    "DocumentIndex",
    "IndexCandidate",
    "IndexExtractionResult",
    "document_index_matches_parts",
    "document_indexes_equal",
    "extract_document_index",
    "extract_index_from_filename",
    "extract_index_from_path",
    "normalize_identifier_text",
]

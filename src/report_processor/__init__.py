"""Инструменты обработки строительных отчётов."""

from report_processor.identifiers import DocumentIndex, extract_document_index
from report_processor.inventory import (
    build_file_manifest,
    classify_file_by_name,
    load_manifest_json,
    save_manifest_json,
    scan_directory,
    scan_zip_archive,
)

__all__ = [
    "DocumentIndex",
    "build_file_manifest",
    "classify_file_by_name",
    "extract_document_index",
    "load_manifest_json",
    "save_manifest_json",
    "scan_directory",
    "scan_zip_archive",
]
__version__ = "0.5.0"

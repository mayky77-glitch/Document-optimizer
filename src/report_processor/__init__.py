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
from report_processor.processing import (
    PROCESSING_CONTRACT_VERSION,
    ProcessingExitCode,
    ProcessingResult,
    ProcessingState,
    ProcessMode,
    ProcessReportRequest,
    process_report,
    process_reports,
)

__all__ = [
    "PROCESSING_CONTRACT_VERSION",
    "DocumentIndex",
    "ProcessMode",
    "ProcessReportRequest",
    "ProcessingExitCode",
    "ProcessingResult",
    "ProcessingState",
    "build_file_manifest",
    "classify_file_by_name",
    "extract_document_index",
    "load_manifest_json",
    "process_report",
    "process_reports",
    "save_manifest_json",
    "scan_directory",
    "scan_zip_archive",
]
__version__ = "0.7.0"

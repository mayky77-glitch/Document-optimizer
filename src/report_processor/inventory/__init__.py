"""Публичный API инвентаризации источников данных."""

from report_processor.inventory.archive_scanner import scan_zip_archive
from report_processor.inventory.file_classifier import classify_file_by_name
from report_processor.inventory.manifest_builder import build_file_manifest
from report_processor.inventory.scanner import scan_directory
from report_processor.inventory.serialization import load_manifest_json, save_manifest_json

__all__ = [
    "build_file_manifest",
    "classify_file_by_name",
    "load_manifest_json",
    "save_manifest_json",
    "scan_directory",
    "scan_zip_archive",
]

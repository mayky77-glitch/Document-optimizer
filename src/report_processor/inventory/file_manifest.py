"""Совместимый публичный API манифеста блока 1.

Реализация разделена между ``manifest_builder`` и ``serialization``. Этот модуль
сохраняет импортные пути первой версии блока.
"""

from report_processor.inventory.manifest_builder import (
    build_file_manifest,
    build_manifest_summary,
)
from report_processor.inventory.serialization import (
    load_manifest_json,
    manifest_from_dict,
    manifest_to_dict,
    save_manifest_json,
)

__all__ = [
    "build_file_manifest",
    "build_manifest_summary",
    "load_manifest_json",
    "manifest_from_dict",
    "manifest_to_dict",
    "save_manifest_json",
]

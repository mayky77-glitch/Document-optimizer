from __future__ import annotations

import json
from datetime import UTC, datetime

from report_processor.domain.models import FileManifest
from report_processor.identifiers.document_index import extract_document_index
from report_processor.identifiers.manifest_enricher import (
    enrich_manifest_with_document_indexes,
)
from report_processor.inventory.file_manifest import (
    load_manifest_json,
    save_manifest_json,
)
from report_processor.metadata.periods import DocumentPeriod
from report_processor.selection.manifest_enricher import (
    enrich_manifest_with_document_metadata,
)
from report_processor.selection.models import SourceSelectionRequest
from report_processor.selection.selector import select_source_file
from report_processor.selection.serialization import save_selection_result_json


def test_selection_roundtrip_from_manifest(tmp_path, make_entry, make_manifest) -> None:
    manifest = make_manifest(
        [
            make_entry("1006 (682)_КС-6а июль 2026 ред2.xlsx"),
            make_entry("1006 (682)_КС-2 июль 2026.xlsx"),
        ]
    )
    manifest = enrich_manifest_with_document_metadata(
        enrich_manifest_with_document_indexes(manifest)
    )
    manifest_path = tmp_path / "manifest.json"
    save_manifest_json(manifest, manifest_path)
    loaded = load_manifest_json(manifest_path)
    request = SourceSelectionRequest(
        target_index=extract_document_index("1006 (682)").value,
        target_period=DocumentPeriod(2026, 7),
        preferred_document_types=("ks6a", "ks2"),
        allowed_document_types=("ks6a", "ks2"),
    )
    result = select_source_file(loaded, request)
    output = tmp_path / "selection.json"
    save_selection_result_json(result, request, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "OK"
    assert payload["selected"]["document_type"] == "ks6a"
    assert payload["selected"]["document_period"] == "2026-07"


def test_old_manifest_without_new_fields_loads_and_enriches(tmp_path) -> None:
    old_payload = {
        "source_path": "/data",
        "source_kind": "directory",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        "entries": [
            {
                "file_id": "1",
                "source_type": "file",
                "source_root": "/data",
                "relative_path": "1006 (682)_КС-6а июль 2026 ред2.xlsx",
                "filename": "1006 (682)_КС-6а июль 2026 ред2.xlsx",
                "extension": ".xlsx",
                "document_type": "ks6a",
            }
        ],
        "summary": {"total_entries": 1},
    }
    path = tmp_path / "old.json"
    path.write_text(json.dumps(old_payload, ensure_ascii=False), encoding="utf-8")
    loaded = load_manifest_json(path)
    assert isinstance(loaded, FileManifest)
    assert loaded.schema_version == "1.0"
    enriched = enrich_manifest_with_document_metadata(enrich_manifest_with_document_indexes(loaded))
    assert enriched.schema_version == "3.0"
    assert enriched.entries[0].document_period == DocumentPeriod(2026, 7)
    assert enriched.entries[0].document_revision.number == 2

#!/usr/bin/env python3
"""Validate the immutable vector and payload-index collection contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EXPECTED_PAYLOAD_SCHEMAS = {
    "tenant_id": ("keyword", {"type": "keyword", "is_tenant": True}),
    "project_id": ("keyword", None),
    "document_type": ("keyword", None),
    "taxonomy_version": ("keyword", None),
    "embedding_model_id": ("keyword", None),
    "embedding_model_revision": ("keyword", None),
    "active": ("bool", None),
    "embedding_dimensions": ("integer", None),
    "review_decision": ("keyword", None),
}


def fail(message: str) -> None:
    raise SystemExit(f"Invalid Qdrant collection contract: {message}")


def main() -> None:
    vector_only = sys.argv[1:2] == ["--vector-only"]
    input_position = 2 if vector_only else 1
    if len(sys.argv) != input_position + 1:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} [--vector-only] COLLECTION_JSON")
    response = json.loads(Path(sys.argv[input_position]).read_text(encoding="utf-8"))
    collection = response.get("result")
    if not isinstance(collection, dict):
        fail("missing result")

    vectors = collection.get("config", {}).get("params", {}).get("vectors")
    if not isinstance(vectors, dict):
        fail("unnamed vector config is missing")
    if vectors.get("size") != 312 or vectors.get("distance") != "Cosine":
        fail("vector must be size=312 and distance=Cosine")
    if vector_only:
        return

    payload_schema = collection.get("payload_schema")
    if not isinstance(payload_schema, dict):
        fail("payload_schema is missing")
    for field_name, (data_type, expected_params) in EXPECTED_PAYLOAD_SCHEMAS.items():
        schema = payload_schema.get(field_name)
        if not isinstance(schema, dict):
            fail(f"missing payload index {field_name}")
        if schema.get("data_type") != data_type:
            fail(f"payload index {field_name} must have data_type={data_type}")
        params = schema.get("params")
        if expected_params is not None and (
            not isinstance(params, dict)
            or any(params.get(key) != value for key, value in expected_params.items())
        ):
            fail(f"payload index {field_name} has unexpected params")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
COLLECTION_NAME="${QDRANT_COLLECTION:-confirmed_examples_v1}"
VECTOR_SIZE="${QDRANT_VECTOR_SIZE:-312}"

case "$QDRANT_URL" in http://127.0.0.1:*|http://localhost:*|https://127.0.0.1:*|https://localhost:*) ;; *)
  echo "QDRANT_URL must target loopback." >&2; exit 2;; esac
case "$COLLECTION_NAME" in *[!A-Za-z0-9_-]*|"") echo "Invalid collection name." >&2; exit 2;; esac
case "$VECTOR_SIZE" in *[!0-9]*|0|"") echo "Invalid vector size." >&2; exit 2;; esac

headers=(-H "api-key: $QDRANT_API_KEY" -H 'Content-Type: application/json')
error_file="$(mktemp -t qdrant-index.XXXXXX)"
trap 'rm -f -- "$error_file"' EXIT
ensure_index() {
  local field_name="$1"
  local field_schema="$2"
  if curl --fail --silent --show-error -X PUT "${headers[@]}" \
    --data "{\"field_name\":\"$field_name\",\"field_schema\":$field_schema}" \
    "$QDRANT_URL/collections/$COLLECTION_NAME/index" >/dev/null 2>"$error_file"; then
    return 0
  fi
  if rg --ignore-case --quiet 'already exists|already.*index' "$error_file"; then
    return 0
  fi
  cat "$error_file" >&2
  return 1
}
if curl --fail --silent --show-error "${headers[@]}" "$QDRANT_URL/collections/$COLLECTION_NAME" >/dev/null; then
  echo "Collection $COLLECTION_NAME already exists."
else
  curl --fail --silent --show-error -X PUT "${headers[@]}" \
    --data "{\"vectors\":{\"size\":$VECTOR_SIZE,\"distance\":\"Cosine\"}}" \
    "$QDRANT_URL/collections/$COLLECTION_NAME" >/dev/null
  echo "Created collection $COLLECTION_NAME."
fi
ensure_index tenant_id '{"type":"keyword","is_tenant":true}'
ensure_index project_id 'keyword'
ensure_index document_type 'keyword'
ensure_index taxonomy_version 'keyword'
ensure_index embedding_model_id 'keyword'
ensure_index embedding_model_revision 'keyword'
ensure_index active 'bool'
echo "Payload indexes are ready for $COLLECTION_NAME."

#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
COLLECTION_NAME="${QDRANT_COLLECTION:-confirmed_examples_v1}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"
VECTOR_SIZE="${QDRANT_VECTOR_SIZE:-$QDRANT_EXPECTED_VECTOR_SIZE}"

validate_qdrant_url "$QDRANT_URL"
validate_collection_name "$COLLECTION_NAME"
if [[ "$VECTOR_SIZE" != "$QDRANT_EXPECTED_VECTOR_SIZE" ]]; then
  echo "QDRANT_VECTOR_SIZE must equal $QDRANT_EXPECTED_VECTOR_SIZE." >&2
  exit 2
fi

headers=(-H "api-key: $QDRANT_API_KEY" -H 'Content-Type: application/json')
error_file="$(mktemp -t qdrant-index.XXXXXX)"
collection_file="$(mktemp -t qdrant-collection.XXXXXX)"
trap 'rm -f -- "$error_file" "$collection_file"' EXIT
ensure_index() {
  local field_name="$1"
  local field_schema="$2"
  if curl --fail --silent --show-error -X PUT "${headers[@]}" \
  --data "{\"field_name\":\"$field_name\",\"field_schema\":$field_schema}" \
    "$QDRANT_URL/collections/$COLLECTION_NAME/index?wait=true" >"$error_file" 2>&1; then
    return 0
  fi
  if grep -Eiq 'already exists|already.*index' "$error_file"; then
    return 0
  fi
  cat "$error_file" >&2
  return 1
}
if curl --fail --silent "${headers[@]}" \
  -o "$collection_file" "$QDRANT_URL/collections/$COLLECTION_NAME"; then
  echo "Collection $COLLECTION_NAME already exists."
  python3 "$SCRIPT_DIR/validate-collection.py" --vector-only "$collection_file"
else
  curl --fail --silent --show-error -X PUT "${headers[@]}" \
    --data "{\"vectors\":{\"size\":$VECTOR_SIZE,\"distance\":\"Cosine\"}}" \
    "$QDRANT_URL/collections/$COLLECTION_NAME?wait=true" >/dev/null
  echo "Created collection $COLLECTION_NAME."
fi
ensure_index tenant_id '{"type":"keyword","is_tenant":true}'
ensure_index project_id '"keyword"'
ensure_index document_type '"keyword"'
ensure_index taxonomy_version '"keyword"'
ensure_index embedding_model_id '"keyword"'
ensure_index embedding_model_revision '"keyword"'
ensure_index active '"bool"'
ensure_index embedding_dimensions '"integer"'
ensure_index review_decision '"keyword"'
curl --fail --silent --show-error "${headers[@]}" \
  -o "$collection_file" "$QDRANT_URL/collections/$COLLECTION_NAME"
python3 "$SCRIPT_DIR/validate-collection.py" "$collection_file"
echo "Payload indexes are ready for $COLLECTION_NAME."

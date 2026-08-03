#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
COLLECTION_NAME="${QDRANT_COLLECTION:-stage_embeddings}"
VECTOR_SIZE="${QDRANT_VECTOR_SIZE:-312}"

case "$QDRANT_URL" in http://127.0.0.1:*|http://localhost:*|https://127.0.0.1:*|https://localhost:*) ;; *)
  echo "QDRANT_URL must target loopback." >&2; exit 2;; esac
case "$COLLECTION_NAME" in *[!A-Za-z0-9_-]*|"") echo "Invalid collection name." >&2; exit 2;; esac
case "$VECTOR_SIZE" in *[!0-9]*|0|"") echo "Invalid vector size." >&2; exit 2;; esac

headers=(-H "api-key: $QDRANT_API_KEY" -H 'Content-Type: application/json')
if curl --fail --silent --show-error "${headers[@]}" "$QDRANT_URL/collections/$COLLECTION_NAME" >/dev/null; then
  echo "Collection $COLLECTION_NAME already exists."
  exit 0
fi
curl --fail --silent --show-error -X PUT "${headers[@]}" \
  --data "{\"vectors\":{\"size\":$VECTOR_SIZE,\"distance\":\"Cosine\"}}" \
  "$QDRANT_URL/collections/$COLLECTION_NAME" >/dev/null
echo "Created collection $COLLECTION_NAME."

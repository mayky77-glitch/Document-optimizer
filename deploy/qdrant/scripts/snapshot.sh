#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
COLLECTION_NAME="${QDRANT_COLLECTION:-confirmed_examples_v1}"

case "$QDRANT_URL" in http://127.0.0.1:*|http://localhost:*|https://127.0.0.1:*|https://localhost:*) ;; *)
  echo "QDRANT_URL must target loopback." >&2; exit 2;; esac
case "$COLLECTION_NAME" in *[!A-Za-z0-9_-]*|"") echo "Invalid collection name." >&2; exit 2;; esac

response="$(curl --fail --silent --show-error -X POST -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/$COLLECTION_NAME/snapshots")"
snapshot_name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])' <<<"$response")"
printf '%s\n' "$snapshot_name"

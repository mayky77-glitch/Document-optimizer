#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
COLLECTION_NAME="${QDRANT_COLLECTION:-confirmed_examples_v1}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

validate_qdrant_url "$QDRANT_URL"
validate_collection_name "$COLLECTION_NAME"

response="$(curl --fail --silent --show-error -X POST -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/$COLLECTION_NAME/snapshots")"
snapshot_name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])' <<<"$response")"
printf '%s\n' "$snapshot_name"

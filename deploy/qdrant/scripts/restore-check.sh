#!/usr/bin/env bash
set -euo pipefail

: "${QDRANT_API_KEY:?Set QDRANT_API_KEY in the environment.}"
: "${QDRANT_RESTORE_CHECK:?Set QDRANT_RESTORE_CHECK=1 to acknowledge this local disposable check.}"
if [[ "$QDRANT_RESTORE_CHECK" != "1" ]]; then
  echo "QDRANT_RESTORE_CHECK must equal 1." >&2
  exit 2
fi
QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
CHECK_COLLECTION="restore_check_$$_$(date +%s)"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
snapshot_file="$(mktemp -t qdrant-restore-check.XXXXXX.snapshot)"
collection_file="$(mktemp -t qdrant-restore-collection.XXXXXX)"
point_file="$(mktemp -t qdrant-restore-point.XXXXXX)"
count_file="$(mktemp -t qdrant-restore-count.XXXXXX)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

validate_qdrant_url "$QDRANT_URL"
cleanup() {
  curl --silent -X DELETE -H "api-key: $QDRANT_API_KEY" \
    "$QDRANT_URL/collections/$CHECK_COLLECTION" >/dev/null || true
  rm -f -- "$snapshot_file" "$collection_file" "$point_file" "$count_file"
}
trap cleanup EXIT

QDRANT_COLLECTION="$CHECK_COLLECTION" "$SCRIPT_DIR/create-collection.sh"
canary_vector="$(python3 -c 'import json; print(json.dumps([1.0] + [0.0] * 311))')"
canary_payload='{"tenant_id":"restore-check-tenant","project_id":"restore-check-project","document_type":"restore-check-document","taxonomy_version":"restore-check-taxonomy","embedding_model_id":"cointegrated/rubert-tiny2","embedding_model_revision":"e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae","active":true,"embedding_dimensions":312,"review_decision":"confirmed"}'
curl --fail --silent --show-error -X PUT -H "api-key: $QDRANT_API_KEY" \
  -H 'Content-Type: application/json' \
  --data "{\"points\":[{\"id\":314159,\"vector\":$canary_vector,\"payload\":$canary_payload}]}" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION/points?wait=true" >/dev/null
snapshot_name="$(QDRANT_COLLECTION="$CHECK_COLLECTION" "$SCRIPT_DIR/snapshot.sh")"
curl --fail --silent --show-error -H "api-key: $QDRANT_API_KEY" \
  -o "$snapshot_file" "$QDRANT_URL/collections/$CHECK_COLLECTION/snapshots/$snapshot_name"
curl --fail --silent --show-error -X DELETE -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION?timeout=30" >/dev/null
if curl --fail --silent -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION" >/dev/null; then
  echo "Disposable collection still exists after deletion." >&2
  exit 1
fi
curl --fail --silent --show-error -X POST -H "api-key: $QDRANT_API_KEY" \
  -F "snapshot=@$snapshot_file" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION/snapshots/upload?priority=snapshot&wait=true" >/dev/null
for _ in {1..30}; do
  if curl --fail --silent --show-error -H "api-key: $QDRANT_API_KEY" \
    -o "$collection_file" "$QDRANT_URL/collections/$CHECK_COLLECTION"; then
    break
  fi
  sleep 1
done
python3 "$SCRIPT_DIR/validate-collection.py" "$collection_file"
curl --fail --silent --show-error -H "api-key: $QDRANT_API_KEY" \
  -o "$point_file" "$QDRANT_URL/collections/$CHECK_COLLECTION/points/314159?with_vector=true"
curl --fail --silent --show-error -X POST -H "api-key: $QDRANT_API_KEY" \
  -H 'Content-Type: application/json' --data '{"exact":true}' \
  -o "$count_file" "$QDRANT_URL/collections/$CHECK_COLLECTION/points/count"
python3 - "$point_file" "$count_file" <<'PY'
import json
import sys
from pathlib import Path

point = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("result")
count = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")).get("result", {}).get("count")
expected_payload = {
    "tenant_id": "restore-check-tenant",
    "project_id": "restore-check-project",
    "document_type": "restore-check-document",
    "taxonomy_version": "restore-check-taxonomy",
    "embedding_model_id": "cointegrated/rubert-tiny2",
    "embedding_model_revision": "e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae",
    "active": True,
    "embedding_dimensions": 312,
    "review_decision": "confirmed",
}
if not isinstance(point, dict) or point.get("id") != 314159:
    raise SystemExit("Restored canary point is missing or has the wrong ID.")
if point.get("payload") != expected_payload:
    raise SystemExit("Restored canary payload does not match exactly.")
vector = point.get("vector")
if vector != [1.0] + [0.0] * 311:
    raise SystemExit("Restored canary vector does not match exactly.")
if count != 1:
    raise SystemExit(f"Restored collection count must be 1, got {count!r}.")
PY
echo "Snapshot restore check passed for disposable collection $CHECK_COLLECTION."

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

case "$QDRANT_URL" in http://127.0.0.1:*|http://localhost:*|https://127.0.0.1:*|https://localhost:*) ;; *)
  echo "QDRANT_URL must target loopback." >&2; exit 2;; esac
cleanup() {
  curl --silent -X DELETE -H "api-key: $QDRANT_API_KEY" \
    "$QDRANT_URL/collections/$CHECK_COLLECTION" >/dev/null || true
  rm -f -- "$snapshot_file"
}
trap cleanup EXIT

QDRANT_COLLECTION="$CHECK_COLLECTION" "$SCRIPT_DIR/create-collection.sh"
snapshot_name="$(QDRANT_COLLECTION="$CHECK_COLLECTION" "$SCRIPT_DIR/snapshot.sh")"
curl --fail --silent --show-error -H "api-key: $QDRANT_API_KEY" \
  -o "$snapshot_file" "$QDRANT_URL/collections/$CHECK_COLLECTION/snapshots/$snapshot_name"
curl --fail --silent --show-error -X POST -H "api-key: $QDRANT_API_KEY" \
  -F "snapshot=@$snapshot_file" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION/snapshots/upload?priority=snapshot" >/dev/null
curl --fail --silent --show-error -H "api-key: $QDRANT_API_KEY" \
  "$QDRANT_URL/collections/$CHECK_COLLECTION" >/dev/null
echo "Snapshot restore check passed for disposable collection $CHECK_COLLECTION."

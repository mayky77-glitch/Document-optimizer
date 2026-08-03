#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

for script in create-collection.sh snapshot.sh restore-check.sh; do
  if rg -n '(^|[[:space:]])curl[[:space:]]' "$SCRIPT_DIR/$script" >/dev/null; then
    echo "Authenticated curl bypasses qdrant_curl in $script." >&2
    exit 1
  fi
done

http_proxy=http://proxy.invalid:8080 \
https_proxy=https://proxy.invalid:8443 \
HTTP_PROXY=http://proxy.invalid:8080 \
HTTPS_PROXY=https://proxy.invalid:8443 \
ALL_PROXY=socks5://proxy.invalid:1080 \
all_proxy=socks5://proxy.invalid:1080 \
NO_PROXY=proxy.invalid \
no_proxy=proxy.invalid \
QDRANT_CURL_BIN="$SCRIPT_DIR/test-proxy-capture.sh" \
qdrant_curl --fail --silent -H 'api-key: test-only-key' \
  http://127.0.0.1:6333/collections/test

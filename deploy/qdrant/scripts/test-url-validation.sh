#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

for valid_url in \
  http://127.0.0.1:1 \
  https://127.0.0.1:6333 \
  http://localhost:6333 \
  https://localhost:6333 \
  'http://[::1]:6333' \
  'https://[::1]:65535'; do
  validate_qdrant_url "$valid_url"
done

for malicious_url in \
  http://127.0.0.1 \
  http://127.0.0.1:0 \
  http://127.0.0.1:65536 \
  http://127.0.0.1:6333/ \
  http://127.0.0.1:6333/path \
  'http://127.0.0.1:6333?redirect=http://evil.invalid' \
  http://127.0.0.1:6333#fragment \
  http://user@127.0.0.1:6333 \
  http://127.0.0.1:6333@evil.invalid \
  http://127.0.0.1.evil.invalid:6333 \
  'http://[::1]:6333/path'; do
  if validate_qdrant_url "$malicious_url" >/dev/null 2>&1; then
    echo "Unsafe URL accepted: $malicious_url" >&2
    exit 1
  fi
done

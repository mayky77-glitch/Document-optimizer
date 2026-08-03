#!/usr/bin/env bash

QDRANT_EXPECTED_VECTOR_SIZE=312
QDRANT_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

qdrant_curl() {
  local curl_bin="${QDRANT_CURL_BIN:-curl}"

  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u all_proxy \
    -u NO_PROXY -u no_proxy "$curl_bin" --noproxy '*' "$@"
}

validate_qdrant_url() {
  python3 "$QDRANT_LIB_DIR/validate-url.py" "$1"
}

validate_collection_name() {
  local collection_name="$1"

  case "$collection_name" in
    *[!A-Za-z0-9_-]*|"")
      echo "Invalid collection name." >&2
      return 2
      ;;
  esac
}

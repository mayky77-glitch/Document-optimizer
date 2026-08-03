#!/usr/bin/env bash

QDRANT_EXPECTED_VECTOR_SIZE=312
QDRANT_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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

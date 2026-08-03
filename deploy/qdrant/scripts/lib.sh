#!/usr/bin/env bash

QDRANT_EXPECTED_VECTOR_SIZE=312

validate_qdrant_url() {
  local url="$1"
  local port

  if [[ ! "$url" =~ ^https?://127\.0\.0\.1:([0-9]+)$ ]]; then
    echo "QDRANT_URL must be http(s)://127.0.0.1:<numeric-port> with no userinfo, path, query, or fragment." >&2
    return 2
  fi
  port="${BASH_REMATCH[1]}"
  if (( ${#port} > 5 || 10#$port < 1 || 10#$port > 65535 )); then
    echo "QDRANT_URL port must be in 1..65535." >&2
    return 2
  fi
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

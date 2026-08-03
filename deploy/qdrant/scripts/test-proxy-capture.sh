#!/usr/bin/env bash
set -euo pipefail

for proxy_var in \
  http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy NO_PROXY no_proxy; do
  if env | grep -F -q "${proxy_var}="; then
    echo "Proxy variable leaked to curl: $proxy_var" >&2
    exit 1
  fi
done

if [[ "${1:-}" != "--noproxy" || "${2:-}" != "*" ]]; then
  echo "curl did not receive forced --noproxy '*'." >&2
  exit 1
fi
shift 2

has_api_key=false
has_url=false
for argument in "$@"; do
  [[ "$argument" == "api-key: test-only-key" ]] && has_api_key=true
  [[ "$argument" == "http://127.0.0.1:6333/collections/test" ]] && has_url=true
done
if [[ "$has_api_key" != true || "$has_url" != true ]]; then
  echo "curl capture did not receive expected authenticated request." >&2
  exit 1
fi

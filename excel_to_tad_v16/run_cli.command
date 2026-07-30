#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

python3 excel_to_tad.py --interactive
STATUS=$?

echo
read -r -p "Нажмите Enter, чтобы закрыть окно..."
exit "$STATUS"

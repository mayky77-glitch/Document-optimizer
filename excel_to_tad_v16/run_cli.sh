#!/usr/bin/env sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR" || exit 1

python3 excel_to_tad.py --interactive
STATUS=$?

printf '\nНажмите Enter, чтобы закрыть окно...'
read _
exit "$STATUS"

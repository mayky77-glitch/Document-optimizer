#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run_cli.py --help
printf '\nУстановка завершена. Запуск пошагового меню:\n  source .venv/bin/activate\n  python run_cli.py\n\nПроверки разработчика:\n  pytest\n  ruff check .\n\n'

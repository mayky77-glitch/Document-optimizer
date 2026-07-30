#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Первый запуск: создаю окружение и устанавливаю зависимости…"
  bash scripts/setup_mac_linux.sh
fi
source .venv/bin/activate
python run_cli.py

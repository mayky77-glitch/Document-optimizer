#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p output work
python run_cli.py build-drawing-card \
  --inputs examples/0906_demo_input.xlsx \
  --template templates/карточка_остатков_шаблон.xlsx \
  --output output/demo_result.xlsx \
  --mode create \
  --rag-mode off \
  --strict \
  --work-dir work
python run_cli.py validate-drawing-card --card output/demo_result.xlsx

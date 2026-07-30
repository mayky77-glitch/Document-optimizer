$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
.\.venv\Scripts\Activate.ps1
New-Item -ItemType Directory -Force output, work | Out-Null
python run_cli.py build-drawing-card `
  --inputs examples/0906_demo_input.xlsx `
  --template templates/карточка_остатков_шаблон.xlsx `
  --output output/demo_result.xlsx `
  --mode create `
  --rag-mode off `
  --strict `
  --work-dir work
python run_cli.py validate-drawing-card --card output/demo_result.xlsx

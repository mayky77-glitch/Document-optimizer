$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python run_cli.py --help
Write-Host "`nУстановка завершена. Запуск пошагового меню:`n  python run_cli.py`n`nПроверки разработчика:`n  pytest`n  ruff check .`n"

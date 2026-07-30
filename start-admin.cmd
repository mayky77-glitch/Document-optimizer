@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo Не найден uv.
  echo Установите uv: https://docs.astral.sh/uv/getting-started/installation/
  echo Затем снова откройте этот файл.
  pause
  exit /b 1
)

uv sync --extra rag
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" (
  echo.
  echo Не удалось подготовить окружение. Сообщение об ошибке выше.
  pause
  exit /b %exit_code%
)

uv run report-processor admin
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" (
  echo.
  echo Панель завершилась с ошибкой. Сообщение об ошибке выше.
  pause
)

exit /b %exit_code%

@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 excel_to_tad.py --interactive
) else (
    python excel_to_tad.py --interactive
)
set STATUS=%ERRORLEVEL%
echo.
pause
exit /b %STATUS%

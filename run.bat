@echo off
chcp 65001 >nul
setlocal
set HERE=%~dp0
if exist "%HERE%.venv\Scripts\python.exe" (
    "%HERE%.venv\Scripts\python.exe" -m app.main
) else (
    python -m app.main
)
echo.
echo ============================================================
echo  App closed - check messages above if there was an error.
echo  Press any key to close this window.
echo ============================================================
pause >nul

@echo off
REM Start the local test REST API (for AWT-MT api_rest testing)
chcp 65001 >nul
setlocal
set HERE=%~dp0
if exist "%HERE%.venv\Scripts\python.exe" (
    "%HERE%.venv\Scripts\python.exe" "%HERE%scripts\sample_rest_api.py"
) else (
    python "%HERE%scripts\sample_rest_api.py"
)
echo.
echo Test API stopped. Press any key to close.
pause >nul

@echo off
REM AWT-MT 앱 실행 (더블클릭)
setlocal
set HERE=%~dp0
if exist "%HERE%.venv\Scripts\python.exe" (
    "%HERE%.venv\Scripts\python.exe" -m app.main
) else (
    python -m app.main
)

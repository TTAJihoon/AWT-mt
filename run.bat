@echo off
REM AWT-MT 앱 실행 (더블클릭)
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
echo  앱이 종료되었습니다. (오류가 있으면 위 메시지를 확인하세요)
echo  아무 키나 누르면 이 창이 닫힙니다.
echo ============================================================
pause >nul

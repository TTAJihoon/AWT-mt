@echo off
REM AWT-MT 원클릭 설치 (더블클릭 실행)
REM 옵션 전달 예: setup.bat -Full
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
pause

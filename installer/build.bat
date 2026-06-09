@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
echo.
echo ============================================================
echo  Build finished - review the log above.
echo  (Window stays open - press any key to close)
echo ============================================================
pause >nul

@echo off
REM AWT-MT .exe 빌드 (더블클릭 실행)
REM   - .ps1을 더블클릭하면 '실행'이 아니라 편집기로 열리므로 이 .bat으로 실행하세요.
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
echo.
echo ============================================================
echo  빌드가 끝났습니다. 위 출력을 확인하세요.
echo  (이 창은 자동으로 닫히지 않습니다 - 아무 키나 누르면 닫힘)
echo ============================================================
pause >nul

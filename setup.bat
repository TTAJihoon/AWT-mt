@echo off
REM AWT-MT 원클릭 설치 (더블클릭 실행)
REM 옵션 전달 예: setup.bat -Full
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
echo.
echo ============================================================
echo  설치 과정이 끝났습니다. 위 출력을 확인하세요.
echo  (이 창은 자동으로 닫히지 않습니다 - 아무 키나 누르면 닫힘)
echo ============================================================
pause >nul

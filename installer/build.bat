@echo off
REM AWT-MT .exe 빌드 (더블클릭 실행)
REM   - .ps1을 더블클릭하면 '실행'이 아니라 편집기로 열리므로, 이 .bat으로 실행하세요.
REM   - PyInstaller로 dist\AWT\ 생성, Inno Setup이 있으면 단일 설치파일(.exe)까지 생성.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
echo.
pause

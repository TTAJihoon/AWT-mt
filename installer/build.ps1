# AWT 빌드 스크립트 (PowerShell) — PyInstaller → Inno Setup
# 사용법: installer\build.bat 더블클릭 (또는 우클릭 → PowerShell에서 실행)

$ErrorActionPreference = "Stop"
# 콘솔 UTF-8 출력(한글 깨짐 방지)
try { $OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "=== AWT Build ===" -ForegroundColor Cyan
Set-Location $Root

# 1. 가상환경 확인
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[1/4] 가상환경 생성..." -ForegroundColor Yellow
    python -m venv .venv
}
& ".venv\Scripts\pip.exe" install -q -r requirements.txt
& ".venv\Scripts\pip.exe" install -q pyinstaller

# 2. Playwright 브라우저 설치
Write-Host "[2/4] Playwright 브라우저 설치..." -ForegroundColor Yellow
& ".venv\Scripts\playwright.exe" install chromium

# 3. PyInstaller 빌드
Write-Host "[3/4] PyInstaller 패키징..." -ForegroundColor Yellow
& ".venv\Scripts\pyinstaller.exe" --clean --noconfirm installer\awt.spec

# 4. Inno Setup 컴파일 (ISCC.exe가 PATH에 있어야 함)
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Write-Host "[4/4] Inno Setup 인스톨러 생성..." -ForegroundColor Yellow
    & $iscc "installer\awt_setup.iss"
    Write-Host "✅ 인스톨러: dist\installer\AWT_Setup_1.0.0.exe" -ForegroundColor Green
} else {
    Write-Host "[4/4] Inno Setup을 찾을 수 없습니다. dist\AWT\ 폴더를 직접 배포하세요." -ForegroundColor Yellow
}

Write-Host "=== 빌드 완료 ===" -ForegroundColor Cyan

# AWT 빌드 스크립트 — PyInstaller (+ Inno Setup)
# 실행:  installer\build.bat 더블클릭
#   build.bat -Fast          : Playwright chromium 다운로드 생략(웹 대상 미사용 시 빠름)
#   build.bat -SystemPython  : .venv 대신 시스템 python 사용(의존성 이미 설치 시 가장 빠름)
#   build.bat -Fast -SystemPython  : 가장 빠른 빌드
param(
    [switch]$Fast,
    [switch]$SystemPython
)
$ErrorActionPreference = "Stop"
try { $OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
Write-Host "=== AWT Build ===" -ForegroundColor Cyan

# 실행기 결정 (-SystemPython이면 시스템 python, 아니면 .venv)
if ($SystemPython) {
    $Py = "python"
    Write-Host "[0/4] 시스템 python 사용 (-SystemPython)" -ForegroundColor Yellow
} else {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "[1/4] 가상환경(.venv) 생성..." -ForegroundColor Yellow
        python -m venv .venv
    }
    $Py = ".venv\Scripts\python.exe"
}

Write-Host "[1/4] 의존성 설치 (requirements + pyinstaller)..." -ForegroundColor Yellow
& $Py -m pip install -q -r requirements.txt
& $Py -m pip install -q pyinstaller
if ($LASTEXITCODE -ne 0) { Write-Host "pip install 실패" -ForegroundColor Red; exit 1 }

# 2. Playwright chromium (웹 대상용) — -Fast면 생략
if ($Fast) {
    Write-Host "[2/4] Playwright chromium 생략 (-Fast)" -ForegroundColor Yellow
} else {
    Write-Host "[2/4] Playwright chromium 설치..." -ForegroundColor Yellow
    & $Py -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  (chromium 설치 실패 — 웹 대상에만 영향, 계속 진행)" -ForegroundColor Yellow
    }
}

# 3. PyInstaller 패키징
Write-Host "[3/4] PyInstaller 패키징..." -ForegroundColor Yellow
& $Py -m PyInstaller --clean --noconfirm installer\awt.spec
if ($LASTEXITCODE -ne 0) { Write-Host "PyInstaller 빌드 실패" -ForegroundColor Red; exit 1 }

# 4. Inno Setup 컴파일 (설치되어 있으면 단일 설치파일 생성)
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    Write-Host "[4/4] Inno Setup 설치파일 생성..." -ForegroundColor Yellow
    & $iscc "installer\awt_setup.iss"
    Write-Host "설치파일: dist\installer\AWT_Setup_1.0.0.exe" -ForegroundColor Green
} else {
    Write-Host "[4/4] Inno Setup 없음 — dist\AWT\ 폴더를 직접 배포하세요." -ForegroundColor Yellow
}

Write-Host "=== 빌드 완료: dist\AWT\AWT.exe ===" -ForegroundColor Cyan

# AWT 개발 환경 원클릭 셋업 스크립트
# 사용법: PowerShell 관리자 권한으로 실행
#   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser  # 최초 1회
#   .\setup_dev.ps1

param(
    [switch]$SkipDocker,
    [switch]$SkipPostgres,
    [switch]$SkipInnoSetup,
    [switch]$Mock          # Mock 모드 확인만 (API key 없이)
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  AWT 개발 환경 셋업" -ForegroundColor Cyan
Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------
function Step($msg) {
    Write-Host "▶ $msg" -ForegroundColor Green
}
function Ok($msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}
function Warn($msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}
function Fail($msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}
function CheckCmd($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# 1. Git
# ---------------------------------------------------------------------------
Step "Git 확인"
if (CheckCmd "git") {
    Ok "git $(git --version)"
} else {
    Warn "Git 미설치 — winget install Git.Git"
    winget install Git.Git --silent
}

# ---------------------------------------------------------------------------
# 2. Python 3.12
# ---------------------------------------------------------------------------
Step "Python 확인"
if (CheckCmd "python") {
    $pyver = python --version 2>&1
    Ok $pyver
    if ($pyver -notmatch "3\.1[2-9]|3\.[2-9][0-9]") {
        Warn "Python 3.12+ 권장. 현재: $pyver"
    }
} else {
    Warn "Python 미설치 — 설치 중..."
    winget install Python.Python.3.12 --silent
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path","User")
}

# ---------------------------------------------------------------------------
# 3. Docker Desktop (선택)
# ---------------------------------------------------------------------------
if (-not $SkipDocker) {
    Step "Docker 확인"
    if (CheckCmd "docker") {
        Ok "docker $(docker --version)"
    } else {
        Warn "Docker Desktop 미설치 — winget install Docker.DockerDesktop"
        Warn "설치 후 PC 재부팅 필요. 지금은 건너뜁니다."
        Warn "Phase 2 실전 실행 전에 설치하세요."
        # 자동 설치 안 함 — 재부팅이 필요하므로 사용자가 직접
    }
} else {
    Warn "Docker 건너뜀 (-SkipDocker)"
}

# ---------------------------------------------------------------------------
# 4. PostgreSQL (선택)
# ---------------------------------------------------------------------------
if (-not $SkipPostgres) {
    Step "PostgreSQL 확인"
    if (CheckCmd "psql") {
        Ok "psql $(psql --version)"
    } else {
        Warn "PostgreSQL 미설치 (GUI 앱 실행 시 필요)"
        Warn "필요하면: winget install PostgreSQL.PostgreSQL.17"
    }
} else {
    Warn "PostgreSQL 건너뜀 (-SkipPostgres)"
}

# ---------------------------------------------------------------------------
# 5. Python 의존성
# ---------------------------------------------------------------------------
Step "Python 의존성 설치 (requirements.txt)"
Set-Location $ProjectRoot
pip install -r requirements.txt -q
if ($LASTEXITCODE -eq 0) {
    Ok "pip install 완료"
} else {
    Fail "pip install 실패"
    exit 1
}

# ---------------------------------------------------------------------------
# 6. Playwright Chromium
# ---------------------------------------------------------------------------
Step "Playwright Chromium 설치"
playwright install chromium 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Ok "Playwright Chromium 설치 완료"
} else {
    Warn "Playwright install 실패 — 나중에 'playwright install chromium' 실행"
}

# ---------------------------------------------------------------------------
# 7. .env 파일
# ---------------------------------------------------------------------------
Step ".env 파일 확인"
if (Test-Path "$ProjectRoot\.env") {
    Ok ".env 존재"
} else {
    Copy-Item "$ProjectRoot\.env.example" "$ProjectRoot\.env"
    Warn ".env.example → .env 복사됨. ANTHROPIC_API_KEY를 직접 입력하세요:"
    Warn "  notepad $ProjectRoot\.env"
}

# ---------------------------------------------------------------------------
# 8. 동작 확인 (Mock 파이프라인)
# ---------------------------------------------------------------------------
Step "동작 확인 — Mock 파이프라인 실행"
$env:PYTHONIOENCODING = "utf-8"
$mockOutput = python scripts\run_stage123_mock.py 2>&1
$mockExit = $LASTEXITCODE
# ASCII-safe keywords only
$mockOutput | Where-Object { $_ -match "TC |INFERRED|0\." } | ForEach-Object {
    Ok $_.ToString().Trim()
}
if ($mockExit -eq 0) {
    Ok "Mock pipeline PASS"
} else {
    Fail "Mock pipeline FAILED — check output above"
}

# ---------------------------------------------------------------------------
# 9. 단위 테스트
# ---------------------------------------------------------------------------
Step "단위 테스트 (pytest)"
python -m pytest tests/ -q 2>&1 | Tee-Object -Variable testOutput | Out-Null
$lastLine = ($testOutput | Select-Object -Last 3) -join " "
if ($lastLine -match "passed") {
    Ok "테스트: $lastLine"
} else {
    Warn "테스트 결과: $lastLine"
}

# ---------------------------------------------------------------------------
# 완료
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  셋업 완료!" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor White
Write-Host "  1. .env 파일에 ANTHROPIC_API_KEY 입력" -ForegroundColor Yellow
Write-Host "     notepad $ProjectRoot\.env" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Stage 1~3 실행 (API key 필요)" -ForegroundColor Yellow
Write-Host "     python scripts\run_stage123.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Phase 2 실전 실행 (Docker 설치 후)" -ForegroundColor Yellow
Write-Host "     .\data\oss\gnuboard5\setup.ps1" -ForegroundColor Gray
Write-Host "     python scripts\run_full_pipeline.py ..." -ForegroundColor Gray
Write-Host ""
Write-Host "  자세한 내용: CONTINUE.md, SETUP.md" -ForegroundColor Gray
Write-Host ""

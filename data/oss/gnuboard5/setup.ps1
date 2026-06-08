# 그누보드5 로컬 환경 원클릭 셋업 스크립트
# 실행: .\data\oss\gnuboard5\setup.ps1
# 요구사항: Docker Desktop 실행 중, Git 설치됨

$ErrorActionPreference = "Stop"
$GnuDir = $PSScriptRoot

Write-Host "`n=== 그누보드5 로컬 환경 셋업 ===" -ForegroundColor Cyan

# 1. Docker 확인
try {
    docker info | Out-Null
    Write-Host "[1/4] Docker 실행 중 확인 ✅" -ForegroundColor Green
} catch {
    Write-Host "[1/4] ❌ Docker가 실행되고 있지 않습니다." -ForegroundColor Red
    Write-Host "     Docker Desktop을 실행한 후 다시 시도하세요."
    Write-Host "     (설치: winget install Docker.DockerDesktop)"
    exit 1
}

# 2. 소스 다운로드
$appDir = Join-Path $GnuDir "app"
if (Test-Path (Join-Path $appDir "index.php")) {
    Write-Host "[2/4] 그누보드5 소스 이미 존재 (스킵)" -ForegroundColor Yellow
} else {
    Write-Host "[2/4] 그누보드5 소스 다운로드 중..." -ForegroundColor Yellow
    if (-not (Test-Path $appDir)) { New-Item -ItemType Directory $appDir | Out-Null }
    git clone --depth=1 https://github.com/gnuboard/gnuboard5.git $appDir
    Write-Host "      소스 다운로드 완료 ✅" -ForegroundColor Green
}

# 3. data 디렉터리 생성 (그누보드5 업로드 폴더)
$dataDir = Join-Path $appDir "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory $dataDir | Out-Null
    Write-Host "[3/4] data/ 디렉터리 생성 ✅" -ForegroundColor Green
} else {
    Write-Host "[3/4] data/ 디렉터리 이미 존재 (스킵)" -ForegroundColor Yellow
}

# 4. Docker Compose 실행
Write-Host "[4/4] Docker Compose 시작 중..." -ForegroundColor Yellow
Set-Location $GnuDir
docker compose up -d

Write-Host "`n=== 셋업 완료 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor White
Write-Host "  1. 브라우저에서 http://localhost:8080/install 접속"
Write-Host "  2. 설치 정보 입력:"
Write-Host "       DB 서버:    db"
Write-Host "       DB 이름:    gnuboard5"
Write-Host "       DB 사용자:  gnuboard"
Write-Host "       DB 비밀번호: gnuboard"
Write-Host "       관리자 ID:  admin"
Write-Host "  3. 설치 완료 후 AWT 실행:"
Write-Host "       python scripts\run_full_pipeline.py --url http://localhost:8080 --auth-id admin --auth-pw <비밀번호>"
Write-Host ""

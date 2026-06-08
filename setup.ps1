# AWT-MT 원클릭 설치 (다른 PC 재현용)
#   더블클릭: setup.bat   |   직접 실행: powershell -ExecutionPolicy Bypass -File setup.ps1
#
# 수행: Python 확인/설치 → .venv 생성 + 의존성 설치 → .env 준비 →
#       인증 DB(Docker 우선, 없으면 psql) → 스키마 + 관리자 계정 → 스모크 테스트
#
# 옵션:
#   -Full                 playwright(chromium) + 선택 브리지(.NET/Java/GUI) 설치
#   -NoVenv               시스템 python 사용(기본은 .venv)
#   -SkipDb               DB 설정 건너뜀(나중에 직접)
#   -AdminUser/-AdminPass 비대화식 관리자 생성(미지정 시 대화식 입력)
param(
    [switch]$Full,
    [switch]$NoVenv,
    [switch]$SkipDb,
    [string]$AdminUser = "",
    [string]$AdminPass = "",
    [string]$AdminRole = "admin"
)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Step($m) { Write-Host "`n> $m" -ForegroundColor Green }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "  [X]  $m" -ForegroundColor Red }
function HasCmd($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  AWT-MT 원클릭 설치" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# 1) Python ------------------------------------------------------------------
Step "Python 확인"
if (-not (HasCmd "python")) {
    Warn "Python 미설치 — winget으로 설치 시도"
    if (HasCmd "winget") { winget install -e --id Python.Python.3.12 --silent }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}
if (-not (HasCmd "python")) { Fail "Python을 찾을 수 없습니다. https://python.org 설치 후 재실행"; exit 1 }
Ok (python --version 2>&1)

# 2) venv + 의존성 ----------------------------------------------------------
if ($NoVenv) {
    $Py = "python"
    Ok "시스템 python 사용(-NoVenv)"
} else {
    Step "가상환경(.venv) 생성"
    if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) { python -m venv .venv }
    $Py = "$Root\.venv\Scripts\python.exe"
    Ok ".venv 준비"
}
Step "Python 의존성 설치 (requirements.txt)"
& $Py -m pip install --upgrade pip -q
& $Py -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) { Fail "pip install 실패"; exit 1 }
Ok "의존성 설치 완료"

# 3) 선택 의존(-Full) -------------------------------------------------------
if ($Full) {
    Step "선택 구성요소 설치 (-Full)"
    & $Py -m playwright install chromium
    if ($LASTEXITCODE -ne 0) { Warn "playwright chromium 설치 실패(웹 대상용) — 나중에 재시도" }
    foreach ($pkg in @("pythonnet", "JPype1", "uiautomation", "pywinauto", "pytesseract", "opencv-python")) {
        & $Py -m pip install -q $pkg
        if ($LASTEXITCODE -ne 0) { Warn "$pkg 설치 실패(선택) — 해당 대상 사용 시 수동 설치" }
        else { Ok "$pkg" }
    }
}

# 4) .env -------------------------------------------------------------------
Step ".env 준비"
if (-not (Test-Path "$Root\.env")) {
    Copy-Item "$Root\.env.example" "$Root\.env"
    Ok ".env.example -> .env (DB 기본값/키는 필요시 편집)"
} else { Ok ".env 존재" }

# 5) 인증 DB ----------------------------------------------------------------
$dbReady = $false
if ($SkipDb) {
    Warn "DB 설정 건너뜀(-SkipDb)"
} else {
    Step "인증 DB 준비"
    $dockerOk = $false
    if (HasCmd "docker") {
        docker compose version 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
    }
    if ($dockerOk) {
        Ok "Docker 감지 — PostgreSQL 컨테이너 기동"
        docker compose -f "installer\docker-compose.auth.yml" up -d
        if ($LASTEXITCODE -ne 0) { Warn "docker compose 기동 실패 — 수동 DB 필요" }
    } elseif (HasCmd "psql") {
        Ok "psql 감지 — db_init.sql 실행(슈퍼유저 비밀번호 요구될 수 있음)"
        psql -U postgres -f "installer\db_init.sql"
    } else {
        Warn "Docker/psql 둘 다 없음 — DB를 직접 준비하세요(installer/db_init.sql 또는 Docker)."
    }
    # DB 접속 대기 (최대 60초)
    Step "DB 접속 대기"
    for ($i = 0; $i -lt 30; $i++) {
        & $Py -c "import psycopg2; from app.config.db_config import DBConfig as C; c=C.from_env(); psycopg2.connect(host=c.host,port=c.port,dbname=c.dbname,user=c.user,password=c.password).close()" 2>$null
        if ($LASTEXITCODE -eq 0) { $dbReady = $true; break }
        Start-Sleep -Seconds 2
    }
    if ($dbReady) { Ok "DB 접속 성공" } else { Warn "DB 접속 실패 — DB 기동 후 관리자 계정을 직접 생성하세요" }
}

# 6) 스키마 + 관리자 계정 ---------------------------------------------------
if ($dbReady) {
    Step "스키마 생성 + 관리자 계정"
    & $Py -m app.auth.admin_cli init
    if ($AdminUser -ne "" -and $AdminPass -ne "") {
        & $Py -c "from app.auth.db_client import DBClient; d=DBClient(); d.ensure_schema(); d.create_user('$AdminUser','$AdminPass','$AdminRole'); print('[OK] admin:','$AdminUser')"
    } else {
        Warn "관리자 계정을 생성합니다(대화식):"
        & $Py -m app.auth.admin_cli create-user
    }
}

# 7) 스모크 테스트 ----------------------------------------------------------
Step "스모크 테스트 (어댑터)"
& $Py -m pytest tests/test_api_rest_adapter.py tests/test_api_code_adapter.py tests/test_value_synth.py -q
if ($LASTEXITCODE -eq 0) { Ok "스모크 PASS" } else { Warn "스모크 일부 실패 — 위 출력 확인" }

# 완료 ----------------------------------------------------------------------
Write-Host "`n==============================================" -ForegroundColor Cyan
Write-Host "  설치 완료" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "앱 실행:  run.bat   (또는 .venv\Scripts\python.exe -m app.main)" -ForegroundColor White
Write-Host "API 키:   앱에서 새 실행 시 키 입력 다이얼로그(또는 설정 탭)" -ForegroundColor Gray
Write-Host "데모(키 불필요): .venv\Scripts\python.exe scripts\demo_full_pipeline.py" -ForegroundColor Gray

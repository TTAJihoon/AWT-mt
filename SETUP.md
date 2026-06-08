# AWT 환경 설정 가이드 (다른 PC 재현용)

> 이 문서 하나로 새 Windows PC에서 AWT 개발/실행 환경을 완전히 재현할 수 있다.  
> 최종 갱신: 2026-05-20 | 검증 OS: Windows 11 Pro 23H2

## ⚡ 원클릭 셋업 (권장)

```powershell
# 1. 저장소 클론
git clone https://github.com/TTAJihoon/AutoWebTesting.git -b AWT-claude C:\Projects\AWT
cd C:\Projects\AWT

# 2. 원클릭 셋업 스크립트 실행
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser   # 최초 1회
.\setup_dev.ps1
```

> `setup_dev.ps1` 이 자동으로: Python 패키지 설치 → Playwright 설치 → .env 생성 → Mock 파이프라인 검증 → pytest 실행

---

---

## 빠른 확인 (이미 설치된 PC)

```powershell
python --version        # 3.12.x 이상
git --version
docker --version        # Docker Desktop 설치 여부
psql --version          # PostgreSQL 클라이언트
playwright --version    # pip install 후
```

---

## 1. 필수 소프트웨어 설치

### 1-1. Python 3.12

```powershell
winget install Python.Python.3.12
# 설치 후 PATH 재로드
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
python --version   # 3.12.x 확인
```

### 1-2. Git

```powershell
winget install Git.Git
git --version
```

### 1-3. Docker Desktop (Gnuboard5 실행용)

```powershell
winget install Docker.DockerDesktop
```

> **설치 후 필수 작업:**
> 1. PC 재부팅
> 2. Docker Desktop 실행 → WSL 2 업데이트 허용
> 3. 트레이 아이콘에서 "Docker is running" 확인

```powershell
docker --version
docker compose version
```

### 1-4. PostgreSQL 17 (AWT 인증 DB)

```powershell
winget install PostgreSQL.PostgreSQL.17
```

> 설치 중 비밀번호 설정 창이 뜨면 `postgres` 비밀번호를 기억해둘 것.

```powershell
psql --version
```

### 1-5. Inno Setup 6 (선택 — 인스톨러 빌드 시)

```powershell
winget install JrsoftwareInnoSetup.InnoSetup
```

---

## 2. 프로젝트 체크아웃

```powershell
# 원하는 경로에 클론
git clone https://github.com/TTAJihoon/AutoWebTesting.git -b AWT-claude C:\Projects\AWT
cd C:\Projects\AWT
```

> OneDrive 동기화 방식으로 사용 중이라면: `C:\Users\<user>\OneDrive\Documents\AWT\`

---

## 3. Python 의존성 설치

```powershell
cd C:\Projects\AWT  # 또는 OneDrive 경로

# 가상환경 (선택 — 권장)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
playwright install chromium
```

설치 확인:
```powershell
python -c "import anthropic, playwright, psycopg2, PySide6, openpyxl; print('all ok')"
```

---

## 4. 환경변수 (.env 파일)

프로젝트 루트에 `.env` 파일 생성 (`.env.example` 복사 후 수정):

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` 내용:
```env
# Anthropic API Key (필수)
ANTHROPIC_API_KEY=sk-ant-...

# PostgreSQL (AWT 인증 DB)
AWT_DB_HOST=localhost
AWT_DB_PORT=5432
AWT_DB_NAME=awt
AWT_DB_USER=awt_user
AWT_DB_PASSWORD=changeme
```

---

## 5. AWT DB 초기화

```powershell
# PostgreSQL이 실행 중인지 확인
Get-Service postgresql*

# DB 초기화 SQL 실행
psql -U postgres -f installer\db_init.sql

# AWT 스키마 + admin 계정 생성
python -m app.auth.admin_cli init
python -m app.auth.admin_cli create-user
# → 사용자명: admin, 역할: admin 으로 설정 권장
```

---

## 6. Gnuboard5 실행 (Phase 2 시험 대상)

```powershell
# 소스 다운로드 (최초 1회)
git clone https://github.com/gnuboard/gnuboard5.git data\oss\gnuboard5\app

# 컨테이너 시작
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d

# 로그 확인
docker compose -f data\oss\gnuboard5\docker-compose.yml logs -f web
```

브라우저에서 `http://localhost:8080` 접속 후 설치:

| 항목 | 값 |
|---|---|
| DB 서버 | `db` |
| DB 이름 | `gnuboard5` |
| DB 사용자 | `gnuboard` |
| DB 비밀번호 | `gnuboard` |
| 관리자 ID | `admin` |
| 관리자 비밀번호 | (자유 설정, 메모 필수) |

---

## 7. AWT 실행

### 7-1. Stage 1~3 빠른 테스트 (Docker 없이 가능)

```powershell
# ANTHROPIC_API_KEY 환경변수 설정 후
python scripts\run_stage123.py
# → data\runs\<run_id>\ 에 tc_verified.json, tc_review.xlsx 생성
```

### 7-2. 전체 파이프라인 (GUI)

```powershell
python app\main.py
# → 로그인 → 대시보드 → 새 실행 마법사 → Stage 0~7
```

### 7-3. 전체 파이프라인 (CLI)

```powershell
python scripts\run_full_pipeline.py `
  --url http://localhost:8080 `
  --manual data\oss\gnuboard5\manual\gnuboard5_spec.md `
  --auth-id admin --auth-pw <비밀번호>
```

---

## 8. 빌드 (배포용 .exe)

```powershell
# Inno Setup이 설치되어 있어야 함
.\installer\build.ps1
# → dist\installer\AWT_Setup_1.0.0.exe 생성
```

---

## 9. 자주 쓰는 명령어

```powershell
# Gnuboard5 컨테이너 시작/정지
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d
docker compose -f data\oss\gnuboard5\docker-compose.yml down

# AWT DB 사용자 목록
python -m app.auth.admin_cli list-users

# Stage 1~3 단독 실행
python scripts\run_stage123.py

# 최근 실행 결과 확인
ls data\runs\ | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

---

## 10. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `docker: command not found` | Docker Desktop 미실행 | 트레이에서 Docker Desktop 실행 |
| `psycopg2.OperationalError` | PostgreSQL 미실행 또는 .env 오류 | `Get-Service postgresql*` 확인 |
| `anthropic.AuthenticationError` | API key 없거나 잘못됨 | `.env` 의 `ANTHROPIC_API_KEY` 확인 |
| `playwright._impl._errors.Error` | Chromium 미설치 | `playwright install chromium` |
| PySide6 import 오류 | pip 설치 누락 | `pip install -r requirements.txt` |
| `http://localhost:8080` 접속 불가 | 컨테이너 미실행 | `docker compose up -d` 확인 |

---

## 11. 버전 고정 (재현성 보장)

`requirements.txt`에 이미 최소 버전 명시됨. 정확한 버전 동결이 필요하면:

```powershell
pip freeze > requirements.lock
```

재설치 시:
```powershell
pip install -r requirements.lock
```

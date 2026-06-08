# AWT Desktop App 아키텍처 설계

**결정 근거:** D37(런타임 재정의)·D38(LLM 연동)·D39(Playwright 로컬)·D40(로그인)·D43(오케스트레이션)
**관계:** D25(Claude Code Skill)는 PoC·개발 환경으로만 유지. 본 문서는 프로덕션 대상.

---

## 1. 전체 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                     AWT Desktop App (.exe)                      │
│                                                                 │
│  ┌──────────┐   ┌──────────────────────────────────────────┐   │
│  │  Auth    │   │              Main Application             │   │
│  │  Layer   │   │                                          │   │
│  │          │   │  ┌────────┐  ┌────────┐  ┌────────────┐ │   │
│  │ DB 서버  │   │  │ Stage  │  │ Stage  │  │  Reviewer  │ │   │
│  │ 접속     │   │  │ 0~3    │  │ 4 Gate │  │  Stage 5~7 │ │   │
│  │ 인증     │   │  │        │  │ (UI)   │  │            │ │   │
│  └──────────┘   │  └────────┘  └────────┘  └────────────┘ │   │
│                 │       │            │            │         │   │
│                 │  ┌────▼────────────▼────────────▼──────┐ │   │
│                 │  │      Local Orchestrator (Python)     │ │   │
│                 │  └──────────┬──────────────┬───────────┘ │   │
│                 └─────────────┼──────────────┼─────────────┘   │
└───────────────────────────────┼──────────────┼─────────────────┘
                                │              │
                    ┌───────────▼──┐   ┌───────▼──────────┐
                    │ Anthropic API │   │ Local Playwright  │
                    │ (추론 단계만)  │   │ (Stage 0 · 5)    │
                    └──────────────┘   └──────────────────┘
```

---

## 2. 디렉터리 구조

```
AWT/
├── app/                         ← 프로덕션 앱 소스
│   ├── main.py                  ← 앱 진입점 (PyQt5)
│   ├── auth/
│   │   ├── db_client.py         ← DB 서버 접속·인증
│   │   └── session.py           ← 로그인 세션 관리
│   ├── ui/
│   │   ├── login_window.py
│   │   ├── dashboard.py         ← 프로젝트 목록
│   │   ├── wizard/              ← 새 프로젝트 설정 (URL, 파일 선택)
│   │   ├── pipeline_view.py     ← Stage 진행 상황 표시
│   │   └── reviewer_gate.py     ← Stage 4 게이트 (A/E/R/P 테이블 UI)
│   ├── core/
│   │   ├── orchestrator.py      ← Stage 0~7 전체 흐름 제어
│   │   ├── stage0_dom_scan.py   ← Playwright DOM 스캔
│   │   ├── stage1_ingest.py     ← 파일 파싱
│   │   ├── stage2_tc_design.py  ← LLM 호출 → TC 설계
│   │   ├── stage3_verify.py     ← V1~V5 로컬 검증 + 재호출
│   │   ├── stage5_execute.py    ← Playwright 자동 실행
│   │   ├── stage6_enhance.py    ← LLM 호출 → 실패 분석
│   │   └── stage7_output.py     ← Excel 생성
│   ├── api/
│   │   ├── llm_client.py        ← Anthropic API 래퍼 (stateless)
│   │   └── call_contracts.py    ← Call Contract 정의 (→ 10-llm-call-contracts.md)
│   ├── tools/
│   │   ├── excel_builder.py
│   │   ├── file_parser.py       ← PDF/DOCX/XLSX 파싱
│   │   └── cache.py             ← 입력 해시 기반 LLM 결과 캐시
│   └── config/
│       ├── settings.py          ← API 키 암호화 저장·로드
│       └── db_config.py         ← DB 서버 접속 설정
├── prompts/                     ← LLM Call Contract 프롬프트 템플릿
│   ├── dom_spec_synthesis.md
│   ├── tc_design.md
│   ├── tc_regen.md
│   └── failure_analysis.md
├── data/                        ← 실행 데이터 (런타임 생성)
│   └── runs/<run-id>/
│       ├── dom-scan/
│       ├── ingest/
│       ├── tc_raw/
│       ├── tc_verified/
│       ├── tc_gated/
│       ├── tc_executed/
│       └── report/
├── tools/                       ← PoC·개발용 스크립트 (build_tc_review_xlsx.py 등)
└── doc/                         ← 설계 문서
```

---

## 3. 실행 흐름

### 3.1. 앱 시작 및 로그인

```
앱 실행 (.exe)
    └→ LoginWindow
         ├→ 아이디/비번 입력
         ├→ DB 서버 접속 → 자격증명 검증
         │   ├─ FAIL → 오류 메시지 표시
         │   └─ OK   → Session 토큰 발급 (로컬 메모리 유지)
         └→ Dashboard (프로젝트 목록)
```

### 3.2. 새 프로젝트 실행

```
Dashboard → [새 프로젝트]
    └→ ProjectWizard
         ├─ Step 1: 대상 URL 입력 + 인증 정보 (있는 경우)
         ├─ Step 2: 매뉴얼 파일 선택 (optional)
         ├─ Step 3: 기능리스트 파일 선택 (optional)
         ├─ Step 4: 결함 샘플 파일 선택 (optional)
         └─ [실행] → PipelineView
```

### 3.3. 파이프라인 뷰 (Stage별 진행)

```
PipelineView
    ├─ Stage 0: DOM 스캔 (Playwright 로컬)
    │   └─ 진행률 표시 (페이지 N/M)
    ├─ Stage 1: 파일 파싱
    ├─ Stage 2: TC 설계 (LLM API — leaf별 진행률)
    │   └─ "Leaf 3/10 처리 중..." + 예상 잔여 토큰
    ├─ Stage 3: 검증 (대부분 로컬, 재생성 시 LLM)
    ├─ Stage 4: ★ Reviewer Gate ★
    │   └─ ReviewerGateWindow (별도 전환) → 사용자 검토 완료 대기
    ├─ Stage 5: 자동 실행 (Playwright 로컬)
    │   └─ TC별 통과/실패 실시간 업데이트
    ├─ Stage 6: 결과 보강 (LLM — 실패 TC만)
    └─ Stage 7: Excel 출력 + 저장 경로 표시
```

---

## 4. 인증 레이어 (D40)

### 4.1. DB 서버 접속

```python
# auth/db_client.py 의사코드
import hashlib, pymysql  # 또는 psycopg2

def authenticate(username: str, password: str) -> bool:
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = pymysql.connect(**DB_CONFIG)  # config에서 로드
    result = conn.execute(
        "SELECT 1 FROM users WHERE username=%s AND pw_hash=%s",
        (username, pw_hash)
    )
    return result.fetchone() is not None
```

**DB 테이블 최소 스키마:**
```sql
CREATE TABLE users (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    username    VARCHAR(64) UNIQUE NOT NULL,
    pw_hash     VARCHAR(64) NOT NULL,  -- SHA-256
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  DATETIME DEFAULT NOW()
);
```

### 4.2. 오프라인 처리

- 로그인 DB 서버 미접속 시 → 로그인 불가 (D40)
- 로그인 후 처리 중 서버 연결 끊김 → 현재 작업 계속 허용 (세션은 로컬 메모리 유지)

---

## 5. 로컬 Playwright (D39)

### 5.1. 설치 패키지 구성

```
installer/
├── setup.iss (Inno Setup 스크립트)
└── 포함 항목:
    ├── AWT.exe          ← PyInstaller 빌드 결과
    ├── install_deps.bat ← pip install playwright && playwright install chromium
    └── vcredist.exe     ← VC++ 런타임 (PyInstaller 의존)
```

**설치 순서 (install_deps.bat):**
```bat
pip install playwright
playwright install chromium
```

### 5.2. Playwright 호출 방식

```python
# core/stage0_dom_scan.py
from playwright.sync_api import sync_playwright

def scan_url(url: str, auth: dict = None) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if auth:
            page.goto(auth['login_url'])
            page.fill(auth['id_selector'], auth['username'])
            page.fill(auth['pw_selector'], auth['password'])
            page.click(auth['submit_selector'])
            page.wait_for_load_state('networkidle')
        page.goto(url)
        dom_data = page.evaluate("""() => {
            // form, input, button, nav 요소만 추출 (style 제외)
            ...
        }""")
        browser.close()
        return dom_data
```

---

## 6. LLM API 연동 (D38·D41)

LLM 호출은 `api/llm_client.py`가 전담. 각 호출은 완전 stateless.

```python
# api/llm_client.py
import anthropic

client = anthropic.Anthropic(api_key=settings.api_key)

def call(contract_name: str, variables: dict) -> dict:
    contract = load_contract(contract_name)  # prompts/*.md 로드
    prompt = contract.render(variables)      # 변수 치환
    response = client.messages.create(
        model=contract.model,
        max_tokens=contract.max_output_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return parse_json_response(response.content[0].text)
```

**호출 가능한 단계 (LLM 필요):**

| Call | 호출 단계 | 입력 크기 | 출력 크기 |
|---|---|---|---|
| `DOM_SPEC_SYNTHESIS` | Stage 0 | ~3,500 tok | ~2,000 tok |
| `TC_DESIGN` | Stage 2 | ~3,500 tok | ~3,000 tok |
| `TC_REGEN` | Stage 3 (V 실패 시) | ~2,000 tok | ~2,000 tok |
| `FAILURE_ANALYSIS` | Stage 6 | ~1,500 tok | ~800 tok |

**로컬 처리 (LLM 미사용):**

| 단계 | 처리 방식 |
|---|---|
| Stage 0 DOM 스캔 | Playwright Python 직접 |
| Stage 1 파일 파싱 | pypdf2 / python-docx / openpyxl |
| Stage 3 V1~V5 검증 | regex / 문자열 비교 |
| Stage 4 Gate UI | PyQt5 테이블 위젯 |
| Stage 5 실행 | Playwright Python 직접 |
| Stage 7 Excel 생성 | openpyxl 직접 |

---

## 7. 토큰 절약 전략 (D41)

상세 설계: `doc/03-architecture/10-llm-call-contracts.md`

핵심 원칙 요약:

1. **Per-leaf 처리** — Stage 2 TC 설계를 leaf 1개씩 호출 (10회). 전체 매뉴얼 1회 전송 금지.
2. **발췌 투입** — leaf 관련 매뉴얼 섹션만 추출(최대 1,500자). 나머지 섹션 미전송.
3. **JSON Schema 강제** — 자유 텍스트 응답 금지. `response_format`으로 스키마 고정.
4. **캐시** — 동일 leaf + 동일 매뉴얼 발췌 → 이전 결과 재사용. `cache.py`가 입력 SHA-256으로 판단.
5. **DOM 사전 필터** — Playwright 수집 후 `id, name, type, placeholder, aria-label, text` 만 남기고 style·class 제거. API 전송 전 전처리.

**예상 토큰 소비 (10 leaf 기준):**

| 단계 | 호출 수 | 예상 토큰 | 비고 |
|---|---|---|---|
| Stage 0 | 페이지당 1회 × N | 5K/페이지 | 페이지 10개 기준 50K |
| Stage 2 | 10회 | 6.5K/leaf × 10 = 65K | leaf당 독립 |
| Stage 3 re-gen | 0~3회 | 4K/회 × 최대 3 = 12K | V 실패 시만 |
| Stage 6 | 실패 TC수 × 1회 | 2.3K/실패 × N | |
| **합계** | | **~145K** | 실패 TC 5개 기준 |

---

## 8. API 키 관리 (D42)

```python
# config/settings.py
from cryptography.fernet import Fernet
import os, json

def save_api_key(api_key: str):
    key = _get_machine_key()         # 머신 고유 키 (HWID 기반)
    encrypted = Fernet(key).encrypt(api_key.encode())
    config_path = _config_file()
    json.dump({"api_key": encrypted.decode()}, open(config_path, 'w'))

def load_api_key() -> str:
    key = _get_machine_key()
    data = json.load(open(_config_file()))
    return Fernet(key).decrypt(data["api_key"].encode()).decode()
```

- 키는 머신 고유값 기반 Fernet 암호화 저장 (로컬 config 파일)
- 서버로 전송되지 않음

---

## 9. PoC와의 관계

| 항목 | PoC (Claude Code) | 프로덕션 (Desktop App) |
|---|---|---|
| 오케스트레이션 | Claude Code 대화 흐름 | Python orchestrator.py |
| Playwright | Claude Code Playwright MCP | 로컬 playwright Python |
| LLM 호출 | Claude Code 내장 | Anthropic API 직접 |
| UI | 터미널 + Excel 파일 | PyQt5 GUI |
| 배포 | 개인 환경 | Windows .exe 설치 패키지 |
| **프롬프트** | **동일** (재사용) | **동일** (재사용) |

→ PoC에서 개발·검증된 프롬프트 템플릿이 `prompts/` 디렉터리에 그대로 들어감.
→ PoC 완료 전 앱 개발 시작 불필요.

---

## 10. 미결 설계 항목 (PoC 완료 후 결정)

| 항목 | 내용 |
|---|---|
| DB 서버 스택 | MySQL vs PostgreSQL vs SQLite 중앙 서버 |
| UI 프레임워크 확정 | PyQt5 vs PySide6 (라이선스 차이) |
| 설치 패키지 도구 | Inno Setup vs NSIS |
| 에러 핸들링 정책 | API 호출 실패 시 재시도 횟수·간격 |
| 앱 업데이트 메커니즘 | 수동 재설치 vs 자동 업데이트 |

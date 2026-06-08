# 다른 PC에서 이어 작업하기 — 환경 설정 + 현재 상태 인수인계

> 작성: 2026-05-29 · 갱신: 2026-06-01 (커밋 `07f03c7` 기준)
> 작업 PC가 바뀌어도 이 문서만 따라가면 동일한 상태로 복원 가능합니다.
> **빠른 시작은 아래 §0 을 그대로 복사·실행하세요.**

---

## 0. 빠른 시작 (복사해서 그대로 실행)

```powershell
# 1) 클론 + 브랜치
git clone https://github.com/TTAJihoon/AutoWebTesting.git AWT
cd AWT
git checkout AWT-claude
git pull

# 2) Python 환경
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium

# 3) .env 작성 (LLM 키 — Google 권장)
Copy-Item .env.example .env
notepad .env        # GOOGLE_API_KEY 채우기

# 4) gnuboard5 시험 대상 기동 (Docker Desktop 실행 중이어야 함)
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d
# data 디렉터리 생성 (최초 1회) + 설치 자동화 + 픽스처 생성
docker exec gnuboard5_web bash -c "mkdir -p /app/data && chmod 707 /app/data"
python scripts\install_gnuboard5.py --admin-pw "Gnuboard5!"

# 5) Stage 4~7 파이프라인 실행 (Stage 1~3 산출물이 있을 때)
python scripts\run_stage47.py --url http://localhost:8080 --auth-id admin --auth-pw "Gnuboard5!"
```

---

## 1. 저장소 / 브랜치

| 항목 | 값 |
|---|---|
| **GitHub** | https://github.com/TTAJihoon/AutoWebTesting |
| **작업 브랜치** | `AWT-claude` |
| **최신 커밋** | `46068f3` — fix(ui): 사용자 피드백 5종 반영 (D62) |

```powershell
git clone https://github.com/TTAJihoon/AutoWebTesting.git AWT
cd AWT
git checkout AWT-claude
git pull
```

---

## 2. 환경 요구사항

| 항목 | 권장 / 현재 사용 |
|---|---|
| **Python** | **3.14.x** (현재 3.14.4) — 3.11+ 도 동작 가능성 있음 |
| **OS** | Windows 11 (개발 PC). macOS/Linux도 동작 (스크린샷 자동 폴더 열기는 OS별 분기 처리됨) |
| **GUI** | PySide6 6.7+ — 디스플레이 필요 (헤드리스 서버 X) |
| **브라우저** | Playwright Chromium (자동 설치) |
| **DB** | PostgreSQL — AWT 인증 DB (로그인용) |

---

## 3. 설치 절차 (5분)

### 3.1 가상환경 + Python 패키지

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # PowerShell
# 또는 .venv\Scripts\activate.bat (cmd)

pip install -r requirements.txt
```

### 3.2 Playwright Chromium 다운로드 (필수)

```powershell
playwright install chromium
```

> 설치 안 하면 Stage 0 DOM 스캔과 Stage 5 자동 실행이 모두 실패합니다.

### 3.3 `.env` 파일 작성

```powershell
Copy-Item .env.example .env
# 그 다음 .env를 편집 — 아래 7가지 값 채우기
notepad .env
```

`.env` 채워야 할 값:

```env
LLM_PROVIDER=google                        # anthropic / openai / google
GOOGLE_API_KEY=AIza...                     # 선택한 provider 키만 필수
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...

AWT_DB_HOST=localhost
AWT_DB_PORT=5432
AWT_DB_NAME=awt
AWT_DB_USER=awt_user
AWT_DB_PASSWORD=changeme
```

### 3.4 PostgreSQL 인증 DB

로그인 화면을 통과하려면 PostgreSQL 인스턴스와 AWT 사용자 테이블이 필요합니다.
새 PC에서 DB 마이그레이션 스크립트는 별도 정리 필요 (현재 SOP: 기존 admin/reviewer 계정의 hash를 이관하거나 새로 만듦).

---

## 4. LLM API 키 발급

| Provider | 발급 페이지 | 무료 한도 |
|---|---|---|
| **Google Gemini** (권장) | https://aistudio.google.com/app/apikey | 모델당 일 20회 |
| Anthropic Claude | https://console.anthropic.com/ | $5 크레딧 (시간 한정) |
| OpenAI GPT | https://platform.openai.com/api-keys | 없음 (유료) |

> 현재 기본은 `gemini-2.5-flash`. 무료로 시작하려면 Google 권장.

---

## 5. 시험 대상 서버 (GnuBoard5 데모) — 설치 자동화

로컬 시험 대상으로 GnuBoard5 Docker 컨테이너 사용. **새 PC에서는 아래 순서로 0부터 자동 구축**됩니다.

```powershell
# (1) 컨테이너 기동 — db(MariaDB) + web(PHP-Apache). app/은 git clone으로 채워짐
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d

# app/ 소스가 없으면 (최초 1회):
#   git clone https://github.com/gnuboard/gnuboard5.git data\oss\gnuboard5\app

# (2) data 업로드 디렉터리 생성 (설치 마법사 통과에 필요)
docker exec gnuboard5_web bash -c "mkdir -p /app/data && chmod 707 /app/data"

# (3) 웹 설치 3단계 마법사 자동 실행 (Playwright)
python scripts\install_gnuboard5.py --admin-pw "Gnuboard5!"
#   → DB: db / gnuboard5 / gnuboard / gnuboard,  관리자: admin / Gnuboard5!
```

**픽스처 헬퍼 (`awt_fixture.php`) — 자동 마운트됨:**
- `docker-compose.yml`이 `./awt_fixture.php:/app/awt_fixture.php:ro`로 마운트
- Stage 5 실행 시 테스트 계정(`awt01`)·테스트 게시글을 gnuboard5 내부함수로 직접 생성 (CAPTCHA 우회)
- ⚠️ 로컬/사설 IP 전용. 프로덕션 배포 금지
- 정상 동작 확인: `Invoke-WebRequest "http://localhost:8080/awt_fixture.php?action=check_member&mb_id=awt01"` → JSON 응답

웹 접근: http://localhost:8080  ·  admin: `admin / Gnuboard5!`  ·  test: `awt01 / Awt1234!`

> **컨테이너는 `restart: unless-stopped`** — Docker Desktop만 켜면 localhost:8080 자동 응답.
> 설치·픽스처는 DB 볼륨(`db_data`)이 유지되는 한 1회만 하면 됨.

---

## 6. 실행

```powershell
python -m app.main
```

흐름:
1. 로그인 창 → 계정 입력
2. 대시보드 (빈 상태면 "+ 첫 실행 시작" CTA)
3. 마법사 Step 1~3 → URL/파일/인증/옵션
4. PipelineView → "Stage 1~3 실행" → 페이지 선택 다이얼로그 → Stage 0~3 진행
5. Reviewer Gate → 승인/수정/거부 결정 (필요 시 거부 TC AI 재생성)
6. Stage 5~7 실행 → tc_final.xlsx 생성

---

## 7-A. Stage 5 실제 실행 + 결함 분류 정밀화 (D63 ~ D70, 2026-06-01)

> 4인 페르소나 토론으로 도출. gnuboard5 5회 실측 검증. 모두 푸시 완료.

| 결정 | 핵심 |
|---|---|
| **Feature D** | Stage 6B — real_defect TC → 결함 카탈로그 자동 피드백 (PATTERN_EXTRACT, 중복 방지) |
| **D63** | FAILURE_ANALYSIS v2.1 — exec_mode(D39_keyword/D40_scenario)별 판정 우선순위 분리 |
| **D64 (Phase A)** | execution_log 기록 + URL/요소 기반 구조화 assertion (키워드 매칭은 fallback) |
| **D65** | tc_final.xlsx "커버리지" 시트 — leaf별 TC수·기법·결과 + 색상 경고 |
| **D66 (Phase B)** | 미커버 leaf 5개 실제 액션 (2.5삭제/6.1권한/6.2비밀글/8.1길이/8.2업로드) |
| **D67** | `awt_fixture.php` 픽스처 헬퍼 복원 + `install_gnuboard5.py` 설치 자동화 |
| **D68** | V6 경로 INFERRED 가드 (가공명세 FAIL → fictional_positive) |
| **D69** | Phase B assertion 정밀도 보강 (1.3/2.5/6.3/8.3) |
| **D70** | execution_log 분류 게이트 — 중간 단계 실패면 real_defect 아닌 scenario_error/selector_broken |

**5회 실측 추이:** PASS 82→96, FAIL 18→5, **결함 카탈로그 오탐 14→0**.
**결론:** gnuboard5 자동 검출 진짜 제품 결함 = 0건 (FAIL 5건 전부 자동화 시나리오/셀렉터 한계).
상세는 `CONTINUE.md` §1 참조.

---

## 7. 현재까지 추가된 주요 기능 (D52 ~ D62)

> 13개 커밋 / 모두 푸시 완료

| 분야 | 핵심 기능 |
|---|---|
| **온보딩** | 대시보드 빈 상태 환영 화면 + 빠른 가이드 + 큰 CTA |
| **마법사 Step 1** | URL + 매뉴얼 첨부 + Stage 0 건너뜀 옵션 |
| **마법사 Step 2** | 인증 시퀀스 (한글 콤보 동작/선택자) + 🎯 시각적 CSS 셀렉터 피커 (팝업 브라우저) |
| **마법사 Step 3** | 모델 선택 / INFERRED 임계값(매뉴얼 미첨부 시 자동 조정) / max_leaves(50 기본) / 헤드풀 옵션 + 슬로우 모드 ms |
| **페이지 선택** | URL BFS만 빠르게 수집 → 사용자 체크 선택 → 선택된 페이지만 DOM 분석. shift+click 범위 선택 지원. 탐색 깊이 0~5. |
| **DOM 캐시 재사용** | 같은 target_url의 최근 run에서 URL별 features 재사용 (♻ 표시). meta.json에 출처 기록 |
| **Stage 안정성** | Gemini 빈 응답 분류 (SAFETY/RECITATION/MAX_TOKENS), leaf 단건 실패 허용, 일일 쿼터 시 부분 결과 보존, max_leaves=0인데 leaves>100이면 자동 100개 제한 |
| **로그 UX** | hanging indent (긴 메시지 줄바꿈 시 시간 영역만큼 들여쓰기), 🔍 검색 + ↑↓ 이동, 📋 상세 로그 토글 (raw 메시지) |
| **진행 상태** | 윈도우 타이틀에 stage·진행률, ⠋⠙⠹ 스피너 + ⏱ MM:SS 실시간 경과시간, 시스템 트레이 알림 (검토 대기/완료/오류), 대시보드 10초 자동 새로고침 |
| **Stage 원 클릭** | 1~7 원 클릭 시 해당 stage 스냅샷(tc_raw/verified/gated/executed.json) 테이블에 로드 + 노란 배지 + "↺ 최신 상태" 복귀 버튼 |
| **TC 상세 패널** | 행 더블클릭 → 비모달 다이얼로그. 좌: 스크린샷+메타, 우: 시나리오/예상 vs 실제/실패 원인 4축/리뷰어 노트/원본 JSON |
| **Stage 5 제어** | ⏸ 일시정지 (다음 TC 시작 전 협력적) / ⏹ 중단 (확인 후 종료, 부분 결과 보존) |
| **이력 관리 (admin)** | 첫 컬럼 체크박스 → 다중 삭제, 우클릭 → 복제/재개/삭제 |
| **재개 (Resume)** | 우클릭 → "🔄 Stage 4부터 재개" (tc_verified.json) 또는 "🔄 Stage 5~7부터 재개" (tc_gated.json, Gate 결정 보존) |
| **거부 TC 재생성** | Reviewer Gate "🔄 거부 TC 재생성" 버튼 → reviewer_note를 LLM에 전달 → 새 TC로 교체 (pending 상태로 재검토 대기) |
| **산출물** | 기능목록 CSV (대/중/소 분류) + 스크린샷 폴더 열기 + 최종 Excel "제한사항" 시트 (시험 환경/캐시/분석 누락 leaf 명시) |
| **설정 탭** | API Key 보이기/숨기기 토글 (👁/🙈) |

---

## 8. 알려진 제약·주의사항

| 항목 | 내용 |
|---|---|
| **Gemini 무료 한도** | 모델당 일 20회. 540개 leaf 처리는 불가능. `max_leaves` 50 이하 권장 |
| **max_leaves 안전 가드** | 0으로 두면 자동 100개로 제한. 정말 전체 처리하려면 9999 입력 |
| **헤드풀 모드** | 별도 Chromium 창이 떠 자동화 동작 표시. 사용자 마우스/키보드와 분리. 속도 2~3배 느림 |
| **캐시 재사용** | URL 완전 일치 기준. 사이트가 업데이트됐을 가능성 있으면 메타에 기록된 캐시 출처 확인 필요 |
| **PostgreSQL 의존** | 로그인은 외부 DB 필수. DB 없으면 앱 시작 불가 |
| **PySide6-WebEngine** | 마법사 Step 2의 🎯 시각 선택자 피커에 필요. 미설치 시 graceful fallback (수동 입력 유지) |

---

## 9. 트러블슈팅 모음 (자주 발생)

| 증상 | 원인 / 해결 |
|---|---|
| `playwright not found` | `playwright install chromium` 실행 안 함 |
| Stage 2 첫 호출에서 `JSONDecodeError: Expecting value` | Gemini 빈 응답 (SAFETY 차단 가능). D54 이후 명확한 메시지로 분류됨. 재시도 또는 다른 모델로 |
| `loadFinished` 후 Selector picker 안 됨 | PySide6-WebEngine 미설치 → `pip install PySide6-WebEngine` |
| 캐시가 옛 페이지 데이터 사용 | 페이지 선택 다이얼로그에서 ♻ 체크 해제 → 새로 분석 |
| Stage 5에서 첫 시도부터 차단 | 헤드리스 검출 사이트 가능성 → 헤드풀 옵션 체크 |
| 마법사 Step 3 임계값이 자동 1.00 | 매뉴얼 미첨부 시 정상 동작 — DOM 단독 추론 모드 |

---

## 10. 다음 작업 후보 (이어가기 시 참고)

박정훈/이지수 4인 페르소나 토론 결과 우선순위:

| # | 항목 | 상태 |
|---|---|---|
| ✅ A | 최종 Excel 제한사항 시트 | 완료 (D61) |
| ✅ B | Stage 중간 재개 UI | 완료 (D61) |
| ✅ C | 거부 TC 재생성 | 완료 (D61) |
| ✅ D | 결함 카탈로그 자동 피드백 | 완료 (Feature D + D68/D70 정밀화) |
| 🔲 E | 공식 PDF 시험 성적서 템플릿 (발주처용) | **다음 1순위** |
| 🔲 F | LLM 호출 병렬화 (유료 플랜 한정) | 미시작 |
| 🔲 G | Stage 5 동시성·파일첨부 시나리오 | 진짜 결함 검출 영역 확대 (난이도 상) |
| 🔲 H | 약한 PASS 24건 정밀도 (키워드 fallback → URL/요소 assertion) | 미시작 |

---

## 11. 디렉토리 빠른 안내

```
AWT/
├── app/
│   ├── main.py                    # 진입점
│   ├── ui/                        # PySide6 화면
│   │   ├── login_window.py
│   │   ├── dashboard.py
│   │   ├── wizard.py              # 3단계 마법사 + 🎯 셀렉터 피커
│   │   ├── page_picker.py         # URL 수집 + 선택 다이얼로그 (D55)
│   │   ├── pipeline_view.py       # Stage 0~7 실행 창
│   │   ├── reviewer_gate.py       # Stage 4 + 거부 TC 재생성 (D61)
│   │   ├── failure_detail.py      # TC 통합 상세 패널 (D59)
│   │   └── theme.py               # APPLE_QSS 전역 스타일
│   ├── core/                      # Stage 0~7 + 헬퍼
│   │   ├── orchestrator.py        # 파이프라인 흐름 제어
│   │   ├── stage0_url_collect.py  # BFS URL 수집 (D55)
│   │   ├── stage0_dom_scan.py     # DOM 스캔 + LLM
│   │   ├── stage1_ingest.py       # 파일 파싱
│   │   ├── stage2_tc_design.py    # TC 설계
│   │   ├── stage3_verify.py       # V1~V5 검증
│   │   ├── stage5_execute.py      # Playwright 실행 (+ 일시정지/중단 D57)
│   │   ├── stage5_gnuboard.py     # GnuBoard5 전용 엔진
│   │   ├── stage6_enhance.py      # 실패 원인 분석
│   │   ├── stage7_output.py       # Excel 산출 (+ 제한사항 시트 D61)
│   │   ├── dom_cache.py           # URL별 DOM 캐시 (D55)
│   │   ├── regenerate_rejected.py # 거부 TC 재생성 (D61)
│   │   └── messages.py            # 로그 humanize 규칙
│   ├── api/
│   │   ├── llm_client.py
│   │   └── providers/             # anthropic / openai / gemini
│   ├── tools/excel_builder.py
│   ├── auth/db_client.py          # PostgreSQL 클라이언트
│   ├── config/                    # settings, db_config
│   ├── assets/                    # invariants / defect_catalog
│   └── validation/                # V1~V10 검증 규칙
├── prompts/                       # LLM contracts (frontmatter + 본문)
├── data/runs/                     # run별 산출물 (gitignored)
├── doc/                           # 설계 문서
├── requirements.txt
├── .env.example
└── .env                           # gitignored — 실제 키
```

---

## 12. 핵심 한 줄 요약

> "**python -m app.main → 로그인 → '+ 첫 실행 시작' → URL 입력 → 페이지 선택(BFS) → 자동 시험 → Reviewer 검토 → Excel 산출**" 의 7단계 흐름이 모두 구현되어 있으며, 현재 시점 추적성·재현성·UX 모두 발주처 시험 보고에 사용 가능한 수준입니다.

문서 끝.

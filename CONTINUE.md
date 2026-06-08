# 이어서 작업하기 (다른 PC / 다른 세션)

> `git pull` 후 이 문서부터 읽으면 곧바로 작업에 복귀할 수 있다.

---

## 1. 지금 어디까지 했나 (Last updated: 2026-06-02)

### ✅ 2026-06-02 세션 — 로그인 편중 해소 + 생성 시간 단축 + 검토 부담 완화 + UX

브랜치 `AWT-claude`에 단계별 커밋 완료(전부 push됨). 설계 근거: `doc/06-decisions.md` D51~D58, 상세 `doc/08~10`.

**구현 완료 (모두 옵트아웃 가능 — 회귀 없음):**
- **D51 전역 컴포넌트 dedup** (`stage0_dom_scan`): 헤더 로그인 등 ≥40% 페이지 공통 요소를 `__global__`로 1회만 명세 → 로그인 편중 1순위 원인 해소.
- **D52 카테고리 통제 어휘** (`app/core/taxonomy.py`): 대분류 12종 고정 + 중/소분류 한글 생성(dom_spec). 인증 분열(User Management/Authentication/Account) 통합.
- **D53 기능 확정 게이트** (`app/ui/feature_gate.py`, opt-in): Stage1↔2 사이 도메인(대분류) 단위 집계·제외. 기본 접힘.
- **D54 페이지 그룹 TC 설계**(`TC_DESIGN_GROUP`)+**교차 페이지 시나리오**(`TC_FLOW`): leaf 1개씩→source_url 그룹 → 호출 급감 + 기능 관계 인식.
- **D55 LLM 병렬화** (`llm_client` Lock + ThreadPoolExecutor): `RunConfig.concurrency`(기본6, =1 순차), 결과 입력순 병합=결정성.
- **D56 V10 보완 배치** (`TC_V10_GROUP`): gap당 순차(777)→페이지 배치, 증식 상한 6/leaf, screenshot 전파.
- **D57 Reviewer Gate 리스크 버킷**: 위험점수(신뢰도+근거+기법)로 🔴/🟡/🟢, 🟢 일괄승인, 위험군 진행률. DOM-only도 동작.
- **D58 상세 패널**: 스크린샷·전후이동·키보드(A/E/R) — failure_detail 재사용.
- **UX**: 원클릭 자동 실행(`RunConfig.auto_pages` 기본 ON — 페이지선택 생략·새 BFS), TC목록 대/중/소분류 컬럼·Excel, 기능리스트 한글·병합셀, **실행 정보 다이얼로그**(`run_info.py` — 설정·수집요소 조회/수정/복제재실행).
- **Mock 회귀 복구**: MockLLMClient에 신규 contract 핸들러 추가 → `scripts/run_stage123_mock.py` Stage2 79개·INFERRED 0% 보존, 호출 26+→6.

**⚠️ 다음 작업자 주의:**
- **캐시 재사용 = 옛(영어·미정리) feature**. D51/D52는 *새 스캔*에만 적용 → 깨끗한 결과는 "페이지 선택 자동 진행"(기본 ON)으로 새로 스캔.
- **라이브 미검증**: 전부 mock(가짜 LLM) 단위/통합 검증만. 실 GnuBoard5+실 LLM end-to-end 검증 필요(확인 포인트: MANUAL.md 헤더 "최근 변경").
- 앱 재시작 필수(`python app/main.py`).

**다음 행동 후보:** ① 라이브 재실행으로 인증비율·생성시간·기능 수 실측 ② cap(12)·동시성(6)·버킷 임계값 튜닝 ③ stage0/stage6 병렬화 확장 ④ 기능 수 여전히 많으면 leaf 단위 dedup 강화.

---

### ✅ D69·D70 — Phase B 보강 + 분류 게이트 (카탈로그 오탐 0 달성) (2026-06-01)

**5회 반복 실행으로 결함 카탈로그 오탐을 0으로 수렴 (run `2c9b0cc4`):**

| | 1차 | 2차 | 3차 | 4차 | 5차 |
|---|---|---|---|---|---|
| PASS | 82 | 92 | 96 | 96 | 96 |
| FAIL | 18 | 9 | 5 | 5 | 5 |
| 카탈로그 오탐 | 14 | 7 | 2 | 1 | **0** |

**D69 (Phase B assertion 보강, `stage5_gnuboard.py`):**
- 2.5 삭제(셀렉터 `a[onclick^=del]`), 6.3 IP차단(`_action_ip_block`), 1.3 정보수정(confirm 로그), 8.3 중복(메시지 기반 판정)
- FAIL 9→5

**D70 (execution_log 분류 게이트, `stage6_enhance.py`):**
- `_reclassify_real_defect_by_log()`: real_defect 판정 전 execution_log 검사
  - navigate/login_state fail → selector_broken
  - confirm/action 등 fail → scenario_error
  - 중간 단계 모두 ok → real_defect 유지
- V6 경로 + LLM 경로 양쪽 적용 → **자동화 한계가 real_defect로 새는 것 차단**

**최종 결론 — gnuboard5 자동 검출 진짜 제품 결함 = 0건:**
- FAIL 5건 전부 자동화 시나리오/셀렉터 한계 또는 INFERRED(가공명세)
- 결함 카탈로그는 PoC 시드 5건(001~005)만 유지 (오탐 누적 없음)
- 진짜 결함을 잡으려면 Stage 5 시나리오가 동시성/파일첨부까지 커버해야 함 (구조적 한계)

**남은 FAIL 5건 (전부 진짜 결함 아님, 검수 게이트에서 거절 대상):**
- TC-003-001 (1.3): member_confirm 비번확인 폼 제출 자동화 미통과 → scenario_error
- TC-026-001 (8.3): 중복 아이디 약관/AJAX 단계 미완성 → scenario_error
- TC-006-005·010-003 (동시성, INFERRED) → fictional_positive
- TC-011-001 (2.7 파일첨부): 실제 파일 업로드 미구현

---

### ✅ Phase A/B 실측 검증 + D66·D67·D68 (2026-05-31)

**gnuboard5 실제 실행으로 Phase A/B 효과 정량 검증 (run `2c9b0cc4`):**

| | 1차 (픽스처 X) | 2차 (픽스처 O) |
|---|---|---|
| PASS | 82 | 92 |
| FAIL | 18 | 9 |
| BLOCKED | 1 | 0 |
| 강한 PASS (URL/상태 판정) | 61 | 68 |
| exec_mode | D40_scenario 101/101 | 동일 |
| execution_log | 101/101 | 동일 |

**핵심 발견 — 진짜 제품 결함은 0건:**
- 1차 자동 생성 결함 14건 → 2차 교차검증
  - 7건 false positive (픽스처 부재가 원인) → 삭제
  - 7건 재현 → 정밀 분석 결과 **전부 판정/시나리오 한계**(진짜 결함 아님)
    - fictional_positive 2건 (INFERRED 동시성 시나리오, 자동화 재현 불가)
    - scenario_error 4건 / selector_broken 1건
- 결함 카탈로그는 PoC 시드 5건(001~005)만 유지

**구현 (D66~D68):**

| 결정 | 파일 | 내용 |
|---|---|---|
| **D66 Phase B** | `app/core/stage5_gnuboard.py` | 미커버 leaf 5개 실제 액션 (2.5삭제/6.1권한/6.2비밀글/8.1길이/8.2업로드) + assertion |
| **D67** | `data/oss/gnuboard5/awt_fixture.php` (신규) | 픽스처 헬퍼 복원 — gnuboard5 내부함수로 계정/게시글 직접 생성 (CAPTCHA 우회, 로컬 전용) |
| **D67** | `docker-compose.yml` | awt_fixture.php 마운트 |
| **D67** | `scripts/install_gnuboard5.py` (신규) | 3단계 설치 마법사 자동화 |
| **D68** | `app/core/stage6_enhance.py` | V6 경로 INFERRED 가드 — app_defect→real_defect 변환 시 source=INFERRED면 fictional_positive로 보정 |

**남은 한계 (다음 작업 후보):**
- 약한 PASS 24건: 여전히 키워드 fallback 의존
- Phase B assertion 정밀도: 정보수정 confirm 단계, 삭제 버튼 인식, 8.3 비로그인 상태 시작 등 보강 필요
- Stage 5 시나리오가 더 정밀해져야 진짜 결함 검출 가능

---

### ✅ 4인 페르소나 토론 + D63·D64·D65 구현 (2026-05-31)

4인 전문가 패널(UX/개발/QA/PM) 토론 결과 우선순위대로 즉시 구현:

| 결정 | 파일 | 내용 |
|---|---|---|
| **Feature D** | `app/core/stage6b_defect_feedback.py` (신규) | real_defect TC → 결함 카탈로그 자동 피드백. PATTERN_EXTRACT 호출, suggestedInvariant YAML 추가, 중복 TC ID 체크 |
| **Feature D** | `app/assets/defect_catalog.py` | `next_defect_id()` 추가 (DEF-YYYY-BRD-NNN 자동 채번) |
| **Feature D** | `app/ui/pipeline_view.py` | `defects_found` 시그널 + 트레이 알림 |
| **D63** | `prompts/failure_analysis.md` v2.1 | `exec_mode` 필드 추가, D39/D40 모드별 판정 우선순위 분리 |
| **D63** | `app/core/stage5_execute.py` | `tc["exec_mode"]` 기록 (D39_keyword_match / D40_scenario) |
| **D63** | `app/core/stage6_enhance.py` | exec_mode → LLM 전달 |
| **D64** | `app/core/stage5_gnuboard.py` | `_log()` / `_structured_assert()` / `_format_actual()` 추가, `execute_tc()` 개선 |
| **D64** | `app/core/stage6_enhance.py` | execution_log → LLM actual_output으로 사용 |
| **D65** | `app/tools/excel_builder.py` | `커버리지` 시트 자동 생성 (TC-Leaf 매트릭스, 색상 경고) |

**커버리지 시트 내용:**
- 소분류별 TC 수 / 설계기법 분포 / 실행 결과
- 연두(4개+) / 노랑(2~3개) / 빨강(0~1개) 색상 경고
- 하단 요약: 전체 leaf 수 / TC 수 / 커버리지 등급별 개수

**재실행 방법:**
```powershell
# gnuboard5 컨테이너 구동 확인
docker compose -f data\oss\gnuboard5\docker-compose.yml ps

# Stage 4~7 재개 (기존 tc_verified.json 있을 때)
python scripts\run_stage47.py --url http://localhost:8080 --auth-id admin --auth-pw Gnuboard5!
```

---

### ⏸ 다음 예정 (우선순위 순)

| 순위 | 항목 | 예상 기간 |
|---|---|---|
| 1 | **Phase B** — 미커버 leaf 확장 (6.1/6.2/2.5 negative/8.1/8.2) | 2주 |
| 2 | **E** — 공식 PDF 시험 성적서 템플릿 | 미정 |
| 3 | **F** — LLM 호출 병렬화 (유료 플랜 한정) | 미정 |

---

### ✅ Phase 2 end-to-end 완료 — Stage 0~7 전체 검증 (2026-05-21)

**최종 결과 (run: `data/runs/c0995b8b/`):**

| 단계 | 상태 | 내용 |
|---|---|---|
| Stage 1 | ✅ | leaf 26개 추출 |
| Stage 2 | ✅ | TC 111개 생성 (gemini-3.1-flash-lite) |
| Stage 3 | ✅ | INFERRED 30.6% |
| Stage 4 | ✅ | 111개 전체 자동 승인 |
| Stage 5 | ✅ | PASS 5 / FAIL 106 / BLOCKED 0 |
| Stage 6 | ✅ | V6 사전 분류: app_defect 100 / oracle_mismatch 5 / selector_unstable 1 |
| Stage 7 | ✅ | `tc_final.xlsx` 생성 |

**Stage 5 결과 해석:**
- FAIL 106건은 gnuboard5 자체 버그가 아님 — Stage 5 shallow 실행(메인 페이지 키워드 매칭) 한계
- Stage 5는 현재 `page.goto(base_url)` + `inner_text("body")` 키워드 검사만 수행
- 실제 TC 시나리오(폼 입력, 네비게이션, 액션 수행)는 Phase 3 고도화 대상

**재실행 방법 (다음 세션):**
```powershell
# gnuboard5 이미 설치됨 — 컨테이너만 재시작하면 됨
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d

python scripts\run_stage47.py --url http://localhost:8080 --auth-id admin --auth-pw Gnuboard5!
```

**주요 신규 스크립트:**
- `scripts/run_stage47.py` — Stage 3 산출물에서 Stage 4~7 재개 원클릭
- `scripts/resume_gemini_run.py` — Gemini Stage 1~3 재개

---

### ✅ Stage 1~3 실전 실행 완료 — INFERRED 29.7% (2026-05-20)

| 단계 | 상태 | 내용 |
|---|---|---|
| Stage 1 | ✅ | 그누보드5 매뉴얼 파싱 — leaf 26개 추출 |
| Stage 2 | ✅ | TC 101개 생성 (gemini-3.1-flash-lite, 캐시 재사용) |
| Stage 3 | ✅ | INFERRED **29.7%** ≤ 30% 임계값 통과 |

**최종 run: `data/runs/2c9b0cc4/`**
- `tc_raw.json` — Stage 2 원본 101개 (INFERRED 33개)
- `tc_verified.json` — Stage 3 검증 101개 (INFERRED **30개**)
- `tc_review.xlsx` — Reviewer Gate용 Excel ← **다음 단계 입력**

**TC_REGEN 5개 버그 수정 (이번 세션):**

| 커밋 | 버그 | 효과 |
|---|---|---|
| `c2a2f27` | V3 REGEN 대상 TC 선별 오류 (tc_id="ALL" 매칭 실패) | REGEN 활성화 |
| `be53402` | TC_REGEN에 manual_excerpt 없음 → MANUAL 인용 불가 | INFERRED→MANUAL 변환 가능 |
| `39b2341` | REGEN이 MANUAL source_quote를 INFERRED로 강등 | MANUAL TC 보호 |
| `fb1d910` | TC_REGEN 캐시 히트로 재시도 전부 무효 | use_cache=False |
| `5e6ddd5` | max_retry_exceeded가 MANUAL TC를 INFERRED로 강제 마킹 | V1 전용 마킹으로 제한 |

**REGEN 효과: raw 33개 → verified 30개 (TC-003-002·004-004·005-004 MANUAL 변환)**

---

### 🟡 Gemini 3.5 Flash 실전 실행 — Stage 2 중단 (2026-05-20, 참고용)

| 단계 | 상태 | 내용 |
|---|---|---|
| Stage 1 | ✅ | 그누보드5 매뉴얼 파싱 — leaf 26개 추출 |
| Stage 2 | 🟡 22/26 | F001-F022 완료, F023-F026 일일 quota 소진으로 중단 |
| Stage 3 | ❌ 미실행 | Stage 2 완료 후 실행 필요 |

**재개 방법 (quota 리셋 후):**
```powershell
# gemini-3.5-flash quota: 20 req/day, UTC 자정 리셋
# https://aistudio.google.com/quota 에서 잔여량 확인

python scripts\resume_gemini_run.py
# → F001-F022: 캐시 히트 (API 호출 0)
# → F023-F026: API 호출 4회 (13초 간격 자동 대기)
# → Stage 3: V1~V10 검증 + TC 보완
```

**Gemini 통합 주요 변경사항:**

| 파일 | 변경 내용 |
|---|---|
| `app/api/llm_client.py` | `model_override` 지원, RPM 스로틀링 (gemini-3.5-flash=13s), 503/429 재시도, JSON Extra data 파싱 |
| `app/api/providers/gemini_provider.py` | `ThinkingConfig(thinking_budget=0)` — thinking 토큰이 JSON 예산 잠식 방지 |
| `app/core/orchestrator.py` | `RunConfig.model_override` 추가 |
| `app/core/stage2_tc_design.py` | TC ID 강제 정규화 (`TC-{leaf_num}-{tc_idx:03d}`) |
| `scripts/resume_gemini_run.py` | Gemini 재개 원클릭 스크립트 (신규) |

**캐시 현황:**
- `data/llm_cache/` — 35개 캐시 파일
- `data/runs/gemini35_run_01/` — 진행 중인 run 디렉터리
- 캐시된 leaf: F001~F022 (TC_DESIGN 22회 분)
- API 키: `~/.awt/settings.enc` 에 암호화 저장 (google provider)

**주요 해결된 문제:**

| 오류 | 원인 | 수정 |
|---|---|---|
| JSON 중간 절단 | Gemini 2.5/3.5 Flash thinking 토큰이 max_output_tokens 잠식 | `thinking_budget=0` 추가 |
| TC ID 형식 오류 (`TC-001-001-01`) | Gemini가 프롬프트 형식 불이행 | stage2에서 강제 재부여 |
| JSON Extra data | Gemini 재시도 후 중복 데이터 | `raw_decode()` 첫 객체만 파싱 |
| 5 RPM 한도 초과 | gemini-3.5-flash free tier | `_MIN_INTERVAL=13초` 자동 슬립 |
| 일일 quota 소진 | free tier 20 req/day | 캐시로 22개 보존, quota 리셋 후 4개만 추가 |

---

### ✅ 외부 제안 #4·#5 적용 완료 (2026-05-20)

| 구성 요소 | 파일 | 상태 |
|---|---|---|
| 설계 (D49 negative_category 5enum) | `doc/03-tc-schema.md` §7, `doc/06-decisions.md` | ✅ |
| 설계 (D50 failure_category 5enum) | `doc/03-tc-schema.md` §6, `doc/06-decisions.md` | ✅ |
| LLM Contract 갱신 | `doc/02-llm-contracts.md` 입출력 스키마 | ✅ |
| V10 모듈 | `app/validation/v10_negative_coverage.py` | ✅ |
| Stage 2 — negative_categories 입력 | `app/core/stage2_tc_design.py` | ✅ |
| Stage 3 — V10 호출 | `app/core/stage3_verify.py` (V1~V10) | ✅ |
| Stage 6 — V6+LLM 통합 분류 | `app/core/stage6_enhance.py` | ✅ |
| Prompt — tc_design v2.1 | `prompts/tc_design.md` (D49 강제 추가) | ✅ |
| Prompt — failure_analysis v2.0 | `prompts/failure_analysis.md` (D50 enum 강제) | ✅ |
| Mock 클라이언트 갱신 | `app/api/mock_llm_client.py` (auto-infer 카테고리 + D50 정확 enum) | ✅ |
| 단위 테스트 V10 | `tests/test_v10_negative_coverage.py` (12 PASS) | ✅ |
| 단위 테스트 D50 | `tests/test_failure_classification.py` (14 PASS) | ✅ |
| 매뉴얼 갱신 | `MANUAL.md` §6.2·6.4·6.5, 부록 A·B | ✅ |

회귀 검증:
- pytest 전체 **108개 PASS** (64 → +12 V10 + +14 D50 + 추가 baseline)
- Mock 파이프라인 TC 79개·INFERRED 0% baseline 유지
- V10 진단 결과: 26 leaf 중 8 PASS / 18 FAIL / 8 skip
  - injection_or_security: 0건 (Mock 한계)
  - 실 LLM 호출 시 prompt 강제로 카테고리 보강 예정

### ✅ LLM Provider 추상화 완료 (2026-05-20)

| 구성 요소 | 파일 | 상태 |
|---|---|---|
| 설계 문서 | `doc/07-llm-providers.md` (신규) | ✅ |
| 결정 등록 | `doc/06-decisions.md` → **D48** | ✅ |
| 추상 인터페이스 | `app/api/providers/base.py` (`LLMProvider`, `ChatResult`) | ✅ |
| Anthropic provider | `app/api/providers/anthropic_provider.py` | ✅ |
| OpenAI provider | `app/api/providers/openai_provider.py` | ✅ |
| Gemini provider | `app/api/providers/gemini_provider.py` | ✅ |
| 라우터 | `app/api/providers/__init__.py` (모델 prefix → provider) | ✅ |
| LLMClient 리팩토링 | `app/api/llm_client.py` (provider 라우팅 + 캐시 키에 model 포함) | ✅ |
| settings.py 확장 | `app/config/settings.py` (provider별 키 + active provider) | ✅ |
| UI provider 토글 | `app/ui/dashboard.py` (드롭다운 + 선택된 provider 키만 입력) | ✅ |
| 환경변수 | `.env.example`, `requirements.txt` | ✅ |
| 단위 테스트 | `tests/test_provider_routing.py` (28개 PASS) | ✅ |

회귀 검증:
- pytest 전체 **64개 PASS** (V6 36 + provider 28)
- Mock 파이프라인 재실행: **TC 79개·INFERRED 0%·기법 분포 동일** — baseline 100% 유지
- 모델명 prefix(`claude-*`/`gpt-*`/`gemini-*`)로 자동 라우팅 — 기존 `prompts/*.md` 그대로 사용

### 사용 예
```powershell
# Anthropic (기본)
$env:LLM_PROVIDER="anthropic"; $env:ANTHROPIC_API_KEY="sk-ant-..."
python scripts\run_stage123.py

# OpenAI로 전환 (prompts의 model 필드 일괄 변경 필요)
$env:LLM_PROVIDER="openai"; $env:OPENAI_API_KEY="sk-..."
# prompts/*.md 의 model: claude-sonnet-4-6 → gpt-4o 로 일괄 수정
python scripts\run_stage123.py
```



### ✅ 완료
- **설계 동결** — `doc/` 7개 문서 작성 완료 (D1~D43 확정)
- **PoC-α** — Stage 1~3 시뮬레이션, TC 41개 산출
- **PoC-β** — Reviewer Gate 검토 완료, approved 41/41, PASS
- **PoC-γ** — 자동 실행 41/41, PASS 32 / FAIL 9 (BUG-1~5 검출), PASS
- **Q-INFRA-1~3 결정** — D44(PostgreSQL) D45(PySide6) D46(Inno Setup)

### ✅ Phase 1 완료 (2026-05-19)

| 태스크 | 파일 | 상태 |
|---|---|---|
| T1: 스캐폴드 | `requirements.txt`, 디렉터리 구조 | ✅ |
| T2: Prompts | `prompts/dom_spec.md` 외 3종 | ✅ |
| T3: config + tools | `app/config/`, `app/tools/` | ✅ |
| T4: api | `app/api/llm_client.py`, `call_contracts.py` | ✅ |
| T5: core | `app/core/stage0~7.py`, `orchestrator.py` | ✅ |
| T6: auth | `app/auth/db_client.py`, `admin_cli.py` | ✅ |
| T7: UI | `app/ui/` 5개 창 (PySide6) | ✅ |
| T8: main + installer | `app/main.py`, `installer/` | ✅ |

### ✅ Q-PROD-1 해소 + Phase 2 환경 준비 완료 (2026-05-19)
- **D47: 그누보드5 선정** — [gnuboard/gnuboard5](https://github.com/gnuboard/gnuboard5)
- Docker Compose: `data/oss/gnuboard5/docker-compose.yml`
- 기능 명세서: `data/oss/gnuboard5/manual/gnuboard5_spec.md` (Stage 1 입력)
- 원클릭 셋업: `data/oss/gnuboard5/setup.ps1`
- 실행 스크립트: `scripts/run_stage123.py` (Docker 없이 Stage 1~3 가능)
- 실행 스크립트: `scripts/run_full_pipeline.py` (Stage 0~7 CLI)
- 환경 재현 가이드: `SETUP.md` (다른 PC에서 이 파일 먼저 읽기)
- 의존성 동결: `requirements.lock` (pip freeze 결과)
- Python 의존성: 모두 설치 완료 (이 PC)
- Playwright Chromium: 설치 완료 (이 PC)

### ✅ Mock 파이프라인 실행 완료 (2026-05-19)
- `python scripts\run_stage123_mock.py` 성공
- TC 79개 / V1~V5 모두 PASS (1회) / INFERRED 0% / 0.1초
- 기법: happy_path 23 / negative_basic 28 / equivalence 17 / boundary 9 / state_transition 2
- 산출물: `data/runs/822c7f56/` (tc_verified.json, tc_review.xlsx)
- 버그 수정: `stage2_tc_design.py` — expected_output→expected, technique→design_technique 필드 정규화

### ⚠ 이 PC에서 남은 작업
- **Docker Desktop 미설치** → `winget install Docker.DockerDesktop` 후 재부팅 필요
- **PostgreSQL 미설치** → `winget install PostgreSQL.PostgreSQL.17` 필요 (GUI 앱 실행 시)
- Stage 5~7은 Docker + gnuboard5 설치 후 가능

### ✅ 자산 저장소 (Asset Store) 구현 완료 (2026-05-20)

외부 검토 그룹 제안서(`proposal-for-awt-claude/`) 분석 후 채택·구현:

| 구성 요소 | 파일 | 상태 |
|---|---|---|
| 결함 카탈로그 (PoC-γ 시드 5건) | `data/assets/defect-catalog/BOARD_CMS/` | ✅ |
| 도메인 불변규칙 YAML | `data/assets/domain-invariants/BOARD_CMS.yaml` (8건) | ✅ |
| 도메인 불변규칙 YAML | `data/assets/domain-invariants/USER_AUTH.yaml` (4건) | ✅ |
| 제품 유형 분류기 | `app/assets/product_types.py` (7종) | ✅ |
| 불변규칙 로더 | `app/assets/invariants_loader.py` | ✅ |
| 결함 카탈로그 API | `app/assets/defect_catalog.py` | ✅ |
| PATTERN_EXTRACT Contract | `prompts/pattern_extract.md` (5번째 LLM Contract) | ✅ |
| TC_DESIGN v2 업그레이드 | `prompts/tc_design.md` → invariants + past_defects 주입 | ✅ |
| Stage 2 자산 주입 | `app/core/stage2_tc_design.py` | ✅ |
| Stage 3 V2·V3 3단계 출처 | `app/core/stage3_verify.py` (MANUAL/INVARIANT/INFERRED) | ✅ |
| 자산 이벤트 로그 DB | `app/auth/db_client.py` → `awt_asset_events` 테이블 | ✅ |

Mock 파이프라인 재검증 결과 (2026-05-20):
- TC 79개 생성, V1~V5 모두 PASS (1회차)
- **INFERRED 0%** (목표 <30% 대비 최상)
- source_quote 분포: **MANUAL 92.4% / INVARIANT 7.6% / INFERRED 0%**

핵심 설계 결정:
- D38 Stateless = "API 호출 간 대화 기록 없음" (파일 자산과 별개)
- 3단계 source_quote: INVARIANT 출처는 V3 INFERRED 비율에서 제외
- patternProposal은 AI 자동 생성 → 검수자가 승인/거절만 (30초)
- 제품 유형별 별도 YAML 파일 (`BOARD_CMS.yaml`, `USER_AUTH.yaml` 등)
- 추적성: 파일 `_meta` 블록 + PostgreSQL `awt_asset_events` 테이블

### ✅ V6 선택자 안정성 점수 구현 완료 (2026-05-20)

| 파일 | 내용 |
|---|---|
| `app/validation/v6_selector_stability.py` | 선택자 9계층 점수 + oracle 명료성 + 실패 분류 |
| `app/core/stage5_execute.py` | Stage 5 완료 후 v6_annotate() 자동 연동 |
| `tests/test_v6_selector_stability.py` | 단위 테스트 36개 전체 PASS |

기능 요약:
- `selector_stability_score`: text_exact(0.92) > data_testid(0.88) > url(0.82) > id(0.78) > class(0.62) > xpath(0.32)
- `oracle_clarity_score`: 기대 결과 검증 가능성 (인용문 +0.20, 추상표현 -0.15)
- `classify_failure`: `selector_unstable` | `oracle_mismatch` | `app_defect` | `blocked`
- `exec_confidence`: stability×0.50 + clarity×0.35 + retry_penalty×0.15
- XPath 오분류 방지 3중 필터 (부정형 후방탐색, HTML태그 차단목록, XPath 부분문자열 검사)

### ⏸ 다음 예정
- **Phase 2** — 그누보드5 실전 AWT 실행 (Stage 0~7 end-to-end)

---

## 2. 다음 행동

**→ 새 PC라면 `SETUP.md`를 먼저 읽어라.**

### 다음 작업 후보

Phase A(D64)·Phase B 액션(D66)·픽스처(D67)·INFERRED 가드(D68)·
Phase B 보강(D69)·분류 게이트(D70) 완료. 결함 카탈로그 오탐 0 수렴.

| # | 항목 | 설명 |
|---|---|---|
| 1 | **E — 공식 PDF 시험 성적서** | tc_final.xlsx → 발주처 제출용 PDF 템플릿 |
| 2 | Stage 5 동시성/파일첨부 시나리오 | 진짜 결함 검출 가능 영역 확대 (구조적 난이도 상) |
| 3 | 약한 PASS 24건 정밀도 | 키워드 fallback → leaf별 URL/요소 assertion |
| 4 | F — LLM 호출 병렬화 | 유료 플랜 한정, Stage 2 속도 |

**환경 재실행 (gnuboard5 설치+픽스처는 1회만):**
```powershell
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d
# 최초 설치 시: python scripts\install_gnuboard5.py --admin-pw "Gnuboard5!"
python scripts\run_stage47.py --url http://localhost:8080 --auth-id admin --auth-pw "Gnuboard5!"
```

---

### (구) Phase 2 — Stage 4 Reviewer Gate → Stage 5~7 실행

**Stage 1~3 완료** — 다음 단계:

```powershell
# Stage 4: Reviewer Gate (GUI 앱 또는 Excel 직접 검토)
# → data\runs\2c9b0cc4\tc_review.xlsx 열어서 A/E/R/P 결정

# Stage 5~7: Docker + gnuboard5 필요
winget install Docker.DockerDesktop     # 설치 후 재부팅
.\data\oss\gnuboard5\setup.ps1         # gnuboard5 Docker 셋업
# → http://localhost:8080/install 에서 초기 설치

python scripts\run_full_pipeline.py `
    --url http://localhost:8080 `
    --manual data\oss\gnuboard5\manual\gnuboard5_spec.md `
    --auth-id admin --auth-pw <비밀번호>
```

### Phase 2 전체 실행 순서

```powershell
# 옵션 A-1: Gemini 재개 (현재 권장)
python scripts\resume_gemini_run.py

# 옵션 A-2: 새 run으로 처음부터 (Gemini)
python scripts\resume_gemini_run.py --new-run

# 옵션 B: Anthropic으로 Stage 1~3
set ANTHROPIC_API_KEY=sk-ant-...
python scripts\run_stage123.py

# 옵션 C: Stage 0~7 전체 (Docker + 그누보드5 설치 필요)
.\data\oss\gnuboard5\setup.ps1          # 그누보드5 Docker 셋업
# → http://localhost:8080/install 에서 초기 설치
python scripts\run_full_pipeline.py `
    --url http://localhost:8080 `
    --manual data\oss\gnuboard5\manual\gnuboard5_spec.md `
    --auth-id admin --auth-pw <비밀번호>

# 옵션 D: GUI 앱 (PostgreSQL + Docker 모두 필요)
python -m app.auth.admin_cli init       # 최초 1회
python -m app.auth.admin_cli create-user
python app\main.py
```

**추천: 옵션 A-1** — Gemini quota 리셋 확인 후 원클릭 재개

---

## 3. 문서 읽기 우선순위

**처음이라면 (전체 파악):**
```
1. README.md                        ← 프로젝트 개요
2. doc/README.md                    ← 설계 진입점
3. doc/01-architecture.md           ← 전체 흐름 (Stage 0~7)
4. doc/06-decisions.md              ← 왜 이렇게 됐는지 (주제별 결정 이력)
5. doc/05-poc-plan.md               ← 현재 어디까지 했는지
```

**개발 진입 직전 (Phase 1 본 개발 준비):**
```
1. doc/01-architecture.md §2-§4    ← 디렉터리 + Stage 책임
2. doc/02-llm-contracts.md          ← API 호출 4종 Contract
3. doc/03-tc-schema.md              ← TC 컬럼·검증 규칙
4. doc/06-decisions.md §9           ← 미해결 (Q-INFRA-1~3 결정 필요)
```

**ISO 관련 검수가 필요할 때:**
```
- doc/04-iso-mapping.md             ← 25010/25023/25051/25059 × Layer 매트릭스
```

---

## 4. 핵심 결정 사항 (요약)

진입 전 알고 있어야 할 5가지:

| | 내용 | 근거 |
|---|---|---|
| **무엇** | ISO/IEC 25023 기반 웹 SW 시험 자동화 도구 | D1·D2·D7·D8 |
| **어떻게 (PoC)** | Claude Code 환경에서 prompt 품질 검증 | D25 (PoC 한정) |
| **어떻게 (프로덕션)** | Python Windows 데스크탑 앱 (.exe) | **D37** ← 최신 |
| **LLM** | Anthropic API stateless 호출, 정형화 Call Contract | D38·D41 |
| **인증** | 중앙 DB 서버(PostgreSQL), 처리는 로컬 | D40·**D44** |
| **UI** | PySide6 (LGPL, Qt6 공식) | **D45** |
| **설치** | Inno Setup + PyInstaller | **D46** |
| **LLM Provider** | Anthropic/OpenAI/Gemini 추상화 (모델 prefix 자동 라우팅) | **D48** |

상세는 `doc/06-decisions.md` 참조.

---

## 5. 환경 설정

### 5.1. PoC 환경 (현재)

```bash
# Claude Code 설치되어 있어야 함
# Python (Excel 빌더용)
pip install openpyxl
```

PoC 산출물 재생성:
```bash
python tools/build_tc_review_xlsx.py
# → data/poc/2026-05-19/output/tc_review.xlsx 갱신
```

### 5.2. Phase 1 환경 (구현 완료)

```bash
# PostgreSQL DB 초기화 (최초 1회)
psql -U postgres -f installer/db_init.sql
python -m app.auth.admin_cli init
python -m app.auth.admin_cli create-user   # admin 계정 생성

# 앱 실행
pip install -r requirements.txt
playwright install chromium
python app/main.py

# Windows .exe 빌드 (Inno Setup 설치 필요)
.\installer\build.ps1
```

환경변수 (`.env` 또는 시스템):
```
AWT_DB_HOST=localhost
AWT_DB_PORT=5432
AWT_DB_NAME=awt
AWT_DB_USER=awt_user
AWT_DB_PASSWORD=changeme
```

---

## 6. 단계별 산출물 위치

| 단계 | 산출 | 위치 |
|---|---|---|
| PoC mockup | 미니 게시판 HTML + 합성 매뉴얼 | `data/poc/2026-05-19/sample-board/` |
| PoC-α 산출 | TC 41개 (CSV/Excel/MD) | `data/poc/2026-05-19/output/` |
| PoC-β 진행 | 사용자 검토 결과 | `data/poc/2026-05-19/result.md` (직접 작성) |
| Phase 1 산출 | 데스크탑 앱 소스 | `app/` (완성) |
| Phase 1 인스톨러 | Inno Setup .iss + PyInstaller .spec | `installer/` |

---

## 7. 작업이 막혔을 때

| 상황 | 참조 |
|---|---|
| 설계 의도가 모호 | `doc/06-decisions.md` 주제별 결정 이력 |
| 이전 PoC 방향 vs 현재 차이 | `doc/archive/` (D25 이전 자료) |
| 4인 토론·이론 근거 | `doc/archive/01-theory/01-four-person-debate.md` |
| ISO 매핑 디테일 | `doc/archive/02-iso-25023-mapping/` (요약은 `doc/04-iso-mapping.md`) |
| 폐기된 결정 이유 | `doc/06-decisions.md` 의 ~~취소선~~ 항목 |

---

## 8. 개발 지침 (불변)

1. **설계 우선** — 코딩 전 `doc/`에서 합의·동결
2. **수정계획 제시** — 즉시 코딩 금지, 변경안 사전 제시
3. **추측 금지** — 모르면 묻기
4. **Skill화 고려** — 분리 배포 가능한 단위로 설계 (Phase 2)
5. **디렉터리 확인** — 새 파일 작성 전 위치 확인
6. **단계 제안** — 단계 완료 시마다 다음 후보 + 추천 + 이유 명시

---

## 9. 이 파일 갱신 규칙

PoC 단계가 진행될 때마다 §1 (지금 어디까지 했나)와 §2 (다음 행동) 업데이트.
큰 변경 시 git commit 메시지에 `[CONTINUE]` 태그 포함.

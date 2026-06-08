# AWT 사용자 매뉴얼

> AI-driven Web Testing for SW Certification — **실제로 어떻게 쓰는지** 한 문서로 정리.
> 최종 갱신: 2026-06-02 | 대상 OS: Windows 11 Pro 23H2

> **최근 변경 (2026-06-02, D51~D58)** — 사용법에 영향:
> - **TC 생성 속도 대폭 개선**: 기능을 **페이지 그룹 단위**로 설계(D54) + **LLM 호출 병렬화**(D55, 마법사에서 동시성 설정). 기존 leaf 1개씩 순차(수 시간) → 그룹·병렬로 단축.
> - **로그인 편중 완화**: 전역 컴포넌트(헤더 로그인 등) 중복 제거(D51) + 대분류 통제 어휘(D52).
> - **기능 확정 게이트**(D53): 마법사 체크 시 Stage 1 후 불필요 기능 제외 가능.
> - **Reviewer Gate 개편**(D57·D58): 위험도 버킷(🔴/🟡/🟢)·🟢 일괄승인·키보드(A/E/R)·스크린샷·전후이동. → §7.
> - **기능리스트 한글 생성 + Excel 병합셀**, **TC 목록에 대/중/소분류 컬럼·Excel 저장**.

이 매뉴얼은 다음 문서들을 종합한 **사용자 진입점**이다.
- 설치·환경 → `SETUP.md`
- 작업 이어가기 → `CONTINUE.md`
- 설계·결정 근거 → `doc/`
- 외부 검토 제안 → `proposal-for-awt-claude/`

---

## 목차

1. [AWT는 무엇인가](#1-awt는-무엇인가)
2. [3가지 사용 모드](#2-3가지-사용-모드)
3. [최소 설치 (30분)](#3-최소-설치-30분)
4. [Provider 선택과 API 키 (D48)](#4-provider-선택과-api-키-d48)
5. [실행 시나리오 5가지](#5-실행-시나리오-5가지)
6. [결과 해석 — 무엇을 보고 무엇을 신뢰하나](#6-결과-해석--무엇을-보고-무엇을-신뢰하나)
7. [Reviewer Gate 사용법](#7-reviewer-gate-사용법)
8. [자주 묻는 질문](#8-자주-묻는-질문)
9. [트러블슈팅](#9-트러블슈팅)
10. [다음 단계로 가는 길](#10-다음-단계로-가는-길)

---

## 1. AWT는 무엇인가

**한 줄 정의:** 매뉴얼·기능리스트·URL을 받아 **TC 설계 → 검토 → 자동 실행 → 결과 판정**까지 수행하는 ISO/IEC 25023 기반 웹 SW 시험인증 자동화 도구.

**누가 쓰는가:** SW 시험인증 시험원 (시험소 내부 사용 — D6 신뢰 프레임)

**무엇을 자동화하는가:**
| 단계 | 입력 | 출력 |
|---|---|---|
| Stage 0 | URL + (선택) 인증정보 | DOM 기반 기능 명세 초안 |
| Stage 1 | 매뉴얼 파일 (md/pdf/docx) | leaf 기능 목록 (예: 26개) |
| Stage 2 | leaf 기능 + 매뉴얼 발췌 + 자산 (결함카탈로그·invariants) | TC 목록 (예: 79개) |
| Stage 3 | TC 목록 | V1~V5·V10 검증 + 누락 카테고리 TC 자동 추가 |
| Stage 4 | TC + Reviewer Gate (사람) | approved / edited / rejected / pending 결정 |
| Stage 5 | approved/edited TC + Playwright | 실제 브라우저 자동 실행 + PASS/FAIL |
| Stage 6 | FAIL TC + LLM | 실패 원인 4축 분석 |
| Stage 7 | 모두 종합 | `tc_final.xlsx` 시험소 표준 산출물 |

**무엇을 자동화하지 않는가:**
- Reviewer 결재 (D22: 자동 실행 *이전* 사람 게이트 강제)
- 신규 패턴 승인 (자산 누적 시 사람이 candidate → active 승격)
- ISO 매트릭스의 시험소 정합성 검수 (Q-MX-1~4)

---

## 2. 3가지 사용 모드

| 모드 | 누가 | 무엇을 | 필요 환경 |
|---|---|---|---|
| **A. Mock 파이프라인** | 개발자·검토자 | API 호출 없이 코드 회귀 검증 | Python 3.12+, `openpyxl` 정도 |
| **B. CLI Stage 1~3** | 시험원 (간이) | 매뉴얼 → TC 설계까지만, API 1종 사용 | + API 키 1개 |
| **C. GUI 풀스택** | 시험원 (실무) | Stage 0~7 end-to-end | + PostgreSQL + Docker + 시험 대상 |

**오늘 처음 만진다면 A → B → C 순으로 진입한다.**

---

## 3. 최소 설치 (30분)

### 3.1 모드 A 전용 (회귀 검증만)
```powershell
git clone https://github.com/TTAJihoon/AutoWebTesting.git -b AWT-claude C:\Projects\AWT
cd C:\Projects\AWT
pip install -r requirements.txt
```

검증:
```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts\run_stage123_mock.py
```
→ TC 79개, INFERRED 0%, MANUAL 92.4%/INVARIANT 7.6% 분포가 나오면 정상.

### 3.2 모드 B (Stage 1~3 실 API)
모드 A 위에 다음만 추가:
```powershell
Copy-Item .env.example .env
notepad .env
```
`.env`에서 최소 한 줄만 채우면 된다 (provider 1개 선택):
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### 3.3 모드 C (GUI 풀스택)
모드 B 위에 다음을 추가 — **`SETUP.md` §1·§5·§6 참조**. 핵심만:
```powershell
winget install Docker.DockerDesktop      # 재부팅 필요
winget install PostgreSQL.PostgreSQL.17  # 비밀번호 메모 필수
playwright install chromium

psql -U postgres -f installer\db_init.sql
python -m app.auth.admin_cli init
python -m app.auth.admin_cli create-user  # admin 계정 생성
```

그누보드5 시험 환경:
```powershell
git clone https://github.com/gnuboard/gnuboard5.git data\oss\gnuboard5\app
docker compose -f data\oss\gnuboard5\docker-compose.yml up -d
# 브라우저: http://localhost:8080 에서 초기 설치
```

GUI 실행:
```powershell
python app\main.py
```

---

## 4. Provider 선택과 API 키 (D48)

### 4.1 어느 LLM을 쓸 수 있나
| Provider | 추천 모델 | 4K tok 호출당 | 특징 |
|---|---|---:|---|
| **Anthropic** | claude-sonnet-4-6 | ~$0.045 | 기본값. TC 품질 균형 |
| **Anthropic** | claude-haiku-4-5 | ~$0.012 | FAILURE_ANALYSIS용 저비용 |
| **OpenAI** | gpt-4o | ~$0.035 | JSON mode 강제력 가장 강함 |
| **OpenAI** | gpt-4o-mini | ~$0.002 | 실험용 저비용 |
| **Google** | gemini-1.5-flash | ~$0.001 | 가장 저렴 (~30배 절감 가능) |
| **Google** | gemini-1.5-pro | ~$0.018 | 긴 컨텍스트 강점 |

**전체 5개 Contract 전부 호출 시 예상 비용** (10 leaf · 페이지 10 · 실패 5TC 기준):
- claude-sonnet-4-6 전부: ~$0.60
- gemini-1.5-flash 전부: ~$0.015 (검증 필요)
- 혼합(설계는 sonnet, 분석은 haiku): ~$0.40

### 4.2 어떻게 provider를 바꾸나

**방식 1: prompts/*.md 의 model 필드 변경** (영구·세밀 — D48 권장)
```yaml
# prompts/tc_design.md 첫 줄
---
contract_id: TC_DESIGN
version: v2.0
model: gpt-4o           # ← claude-sonnet-4-6 에서 변경
max_input_tokens: 4000
max_output_tokens: 3000
---
```
prefix `gpt-*` 자동 감지 → OpenAI provider 라우팅. Contract마다 다른 provider 가능.

**방식 2: GUI에서 토글** (실험·간편)
1. 로그인 → 대시보드 → 설정 탭
2. **LLM Provider 드롭다운**에서 선택 (Anthropic/OpenAI/Google)
3. 선택한 provider의 API Key 1줄만 입력 → 저장
4. Provider별로 키가 따로 저장됨 (전환 시 재입력 불필요)

**방식 3: 환경변수** (CLI·CI)
```powershell
$env:LLM_PROVIDER="openai"
$env:OPENAI_API_KEY="sk-..."
python scripts\run_stage123.py
```
환경변수가 GUI 저장값보다 우선.

### 4.3 API 키는 어디에 저장되나
- **GUI 저장:** `%USERPROFILE%\.awt\settings.enc` — Fernet AES 암호화 (머신 고유 MAC+hostname으로 파생된 키). 다른 PC로 복사해도 복호화 불가 (D42).
- **환경변수:** `.env` 파일 또는 시스템 환경변수. `.env`는 `.gitignore` 포함됨.

### 4.4 토큰 절약 — 4가지 자동 작동 (D41)
1. **per-leaf 처리** — TC_DESIGN은 1개 leaf씩 호출 (전체 매뉴얼 안 보냄)
2. **발췌 투입** — manual_excerpt ≤ 1500자, defect_patterns ≤ 500자
3. **JSON Schema 강제** — 자유 텍스트 금지 → 출력 토큰 절약
4. **캐시** — 같은 (contract, model, inputs) → API 미호출. `data/llm_cache/<hash>.json`

캐시 무효화: model 또는 version 변경 시 자동.

---

## 5. 실행 시나리오 5가지

### 5.1 시나리오 1 — Mock으로 코드 회귀 확인 (가장 빠름)
```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts\run_stage123_mock.py
```
**기대 결과:** `data/runs/<run_id>/` 에 `tc_verified.json`, `tc_review.xlsx`. TC 79개, INFERRED 0%, MANUAL 92.4%.

**언제 쓰나:** 코드 변경 후 회귀 확인 / 새 PC 환경 검증 / pytest 보강용.

### 5.2 시나리오 2 — Stage 1~3 실 API (Docker 없이)
```powershell
# .env에 LLM_PROVIDER + 해당 키 설정 후
python scripts\run_stage123.py
```
**옵션:**
| 플래그 | 기본값 | 설명 |
|---|---|---|
| `--manual <path>` | `data/oss/gnuboard5/manual/gnuboard5_spec.md` | 입력 매뉴얼 |
| `--url <url>` | `http://localhost:8080` | 대상 URL (메타데이터로만 사용) |
| `--threshold <float>` | `0.30` | V3 INFERRED 임계 |

**언제 쓰나:** 새 매뉴얼로 TC 품질 검증 / 자산 저장소 효과 측정 / Mock과 실 API 갭 확인.

### 5.3 시나리오 3 — Stage 0~7 CLI 풀 파이프라인
```powershell
python scripts\run_full_pipeline.py `
  --url http://localhost:8080 `
  --manual data\oss\gnuboard5\manual\gnuboard5_spec.md `
  --auth-id admin --auth-pw <비밀번호>
```
**선결 조건:** Docker로 그누보드5 기동 + 관리자 계정 생성 (3.3 참조).

**언제 쓰나:** Phase 2 실전 검증 / end-to-end 동작 확인 / 시험소 표준 산출물(`tc_final.xlsx`) 생성.

### 5.4 시나리오 4 — GUI 풀 워크플로 (시험원 실무)
```powershell
python app\main.py
```
1. 로그인 (DB 계정)
2. 대시보드 → "새 실행" → 마법사
3. 매뉴얼 파일 + 대상 URL + 인증 입력. 마법사 3단계에서:
   - **"페이지 선택 자동 진행"**(기본 ON): 켜면 실행 버튼 한 번으로 **페이지를 자동 수집(BFS)해 바로 진행** — 수동 선택·캐시 재사용 프롬프트 없음. 매번 **새로 스캔**하므로 전역 컴포넌트 중복 제거(D51)·한글 생성(D52)이 적용됨. 끄면 페이지를 직접 선택하거나 기존 분석(캐시)을 재사용(비용 절감, 단 옛 캐시는 영어·미정리일 수 있음).
   - **동시성**(D55): 기본 6. 상용(Claude/OpenAI) 모델은 그대로 두면 병렬로 빨라짐. Gemini 무료는 1~2 권장.
   - **"Stage 1 후 기능 확정 게이트"**(D53, 선택): 체크 시 기능 통합 후 **도메인(대분류) 단위**로 보여주고(기본 접힘) 시험 안 할 도메인을 통째로 제외 가능. 미체크면 전체 진행(기존 동작).
4. Stage 진행 표시 (Pipeline View). TC 목록에 **대/중/소분류 컬럼** + **⬇ Excel** 저장 버튼.
5. (게이트 체크 시) Stage 1 후 **기능 확정 창** → 확정하면 Stage 2~3 진행.
6. Stage 3 완료 시 **Reviewer Gate** 자동 표시 — 위험도 버킷으로 집중 검토(§7).
7. 결정 입력 → Stage 5 자동 실행
8. 완료 시 대시보드 이력에서 `tc_final.xlsx` 열기

**언제 쓰나:** 실제 시험 작업 / 다수 사용자 협업 / 재시험 (`Q-SCH-3` 정책 적용 시).

### 5.5 시나리오 5 — Provider 비교 실험 (실험적)
같은 매뉴얼·같은 입력으로 provider만 바꿔서 TC 품질 비교:
```powershell
# 1차: Anthropic
$env:LLM_PROVIDER="anthropic"; $env:ANTHROPIC_API_KEY="sk-ant-..."
python scripts\run_stage123.py
# → data/runs/<run_id_A>/

# 2차: prompts/*.md model을 gpt-4o로 일괄 변경 후
$env:LLM_PROVIDER="openai"; $env:OPENAI_API_KEY="sk-..."
python scripts\run_stage123.py
# → data/runs/<run_id_B>/

# 캐시는 model이 다르면 자동 분리 — 다른 모델은 새 API 호출
```
**언제 쓰나:** 비용/품질 trade-off 측정 (Q-LLM-2) / 새 vendor 평가.

---

## 6. 결과 해석 — 무엇을 보고 무엇을 신뢰하나

### 6.1 산출물 위치
```
data/runs/<run_id>/
├── meta.json              # 실행 메타 (provider, model, 시각)
├── ingest.json            # Stage 1 결과
├── tc_raw.json            # Stage 2 결과 (검증 전)
├── tc_verified.json       # Stage 3 결과 (V1~V5 통과)
├── tc_review.xlsx         # Reviewer Gate용 Excel
├── tc_gated.json          # Stage 4 결정 적용 후
├── tc_executed.json       # Stage 5 Playwright 결과
├── tc_final.xlsx          # Stage 7 시험소 표준 산출물
└── llm/<ts>_<contract>.json  # 각 API 호출 로그 (provider·model·tokens·raw)
```

### 6.2 핵심 지표 — 어떻게 읽나
| 지표 | 의미 | 기준값 | 위반 시 |
|---|---|---|---|
| **TC 수** | 매뉴얼 leaf당 평균 3~6개 | ≥ 50 | manual 부실 또는 prompt 약함 |
| **INFERRED %** | 매뉴얼 근거 없는 TC 비율 | ≤ 30% (PoC 환경) / ≤ 10% (OSS 실전) | 매뉴얼 보강 또는 자산 추가 |
| **source_quote 출처** | MANUAL / INVARIANT / INFERRED 분포 | MANUAL ≥ 80% | invariants YAML 보강 |
| **기법 분포** | 7기법 다양성 | happy_path ≤ 50% | TC_DESIGN prompt 강화 |
| **selector_stability_score** | V6 — 자동 실행 안정성 | ≥ 0.62 (data-testid 또는 text_exact 기반) | DOM 안정 selector 권고 |
| **oracle_clarity_score** | V6 — 기대값 명료도 | ≥ 0.65 | 추상 표현 제거, 구체값 |
| **exec_confidence** | 자동 실행 결과 신뢰도 | ≥ 0.70 | retry 또는 manual 재검토 |
| **negative_category 커버리지 (V10)** | leaf 적용 카테고리 중 충족 비율 (D49) | ≥ 60%, 각 카테고리당 ≥ 1 TC | TC_DESIGN 재호출로 누락 카테고리 TC 자동 추가 |
| **failure_category (D50)** | FAIL TC 5enum 분류 | `selector_broken` / `scenario_error` / `expected_mismatch` / `real_defect` / `fictional_positive` | 분류별 후속 조치 (§6.4) |

### 6.3 source_quote 3단계 출처 (자산 저장소)
- `MANUAL: ...` — 매뉴얼에서 직접 인용. **신뢰도 최상**
- `INVARIANT: ...` — `data/assets/domain-invariants/*.yaml` 의 회사 정책. **신뢰도 상**
- `INFERRED: ...` — LLM 추론. **신뢰도 하** (V3 임계로 제한)

Mock 베이스라인은 MANUAL 92.4% / INVARIANT 7.6% / INFERRED 0% — 자산 저장소가 잘 작동하는 증거.

### 6.4 V10 negative 카테고리 (D49 — 제안 #4 채택)

LLM이 음성 케이스를 *깊이 있게* 만들도록 5카테고리 강제. 각 leaf의 적용 카테고리당 ≥ 1 TC 필수.

| 카테고리 | 의미 | 예시 |
|---|---|---|
| `validation_failure` | 입력 형식·필수값 위반 | 이메일 형식 오류, 빈 필드 |
| `duplicate_or_conflict` | 중복·동시성·충돌 | 중복 아이디, 동시 수정 |
| `permission_denied` | 권한 거부 | 비로그인, 권한 없는 사용자 |
| `boundary_violation` | 경계값 초과 | 최대 길이 +1, 0/음수 |
| `injection_or_security` | 보안 공격 패턴 | SQL/XSS/Path traversal |

**leaf 유형별 적용 카테고리:**
- 입력 폼 (가입·로그인·작성·수정·삭제) → `validation_failure` + `duplicate_or_conflict` + `boundary_violation`
- 조회·검색·필터 → `permission_denied` + `injection_or_security`
- 권한·인증 관리 → `permission_denied` + `validation_failure`
- 파일 업로드 → `validation_failure` + `boundary_violation` + `injection_or_security`
- 결제·주문 → `validation_failure` + `duplicate_or_conflict` + `permission_denied`

V10이 누락 카테고리를 식별하면 **누락 카테고리 TC만 추가 생성**한다. (D56부터는 `TC_V10_GROUP`으로 부족 leaf를 **페이지 그룹 단위 배치**로 보완 — gap마다 순차 호출하던 병목 제거, leaf당 보완 상한 6개. `TC_REGEN`은 기존 TC 수정용이라 미사용.) 강제 적용 안 되는 leaf (read-only 등)는 V10 skip.

### 6.5 failure_category 5분류 (D50 — 제안 #5 채택)

FAIL TC를 자동으로 5enum으로 분류. V6 정적 + LLM 동적 통합:

| enum | 의미 | 판정자 | 다음 조치 |
|---|---|---|---|
| `selector_broken` | 셀렉터 깨짐·timeout·NoSuchElement | V6 우선 → LLM | data-testid로 selector 보강 |
| `scenario_error` | TC 시나리오 자체가 모순·매뉴얼 misread | LLM 전용 | `TC_REGEN` 대상 |
| `expected_mismatch` | 기대값 추상·잘못된 값 | V6 우선 → LLM | invariants 보강 + `expected` 수정 |
| `real_defect` | 진짜 제품 결함 (actual ≠ expected) | V6 우선 → LLM | `defect-catalog` 적재 |
| `fictional_positive` | spec hallucination (source_quote=INFERRED인데 FAIL) | LLM 전용 | TC 폐기 + 매뉴얼 보강 권고 |

**통합 흐름:**
1. Stage 5 직후 V6가 셀렉터 점수 기반으로 `selector_broken`/`expected_mismatch`/`real_defect` 사전 마킹
2. Stage 6에서 V6 미마킹 FAIL만 LLM이 5enum 부여 (토큰 절약)
3. `failure_category_source` 필드로 출처 추적 (`v6_static` / `llm_failure_analysis` / `inferred_fallback`)

---

## 7. Reviewer Gate 사용법

### 7.1 Gate 진입 시점
Stage 3 검증 완료 후 자동 진입 (D22: 사전 게이트). `tc_review.xlsx` 또는 GUI에서.

### 7.2 위험도 버킷 — "다 보지 말고 위험한 것부터" (D57)
TC를 **위험점수**로 자동 3분류한다. 위험점수 = 생성 신뢰도(주축) + 근거 출처(MANUAL/INVARIANT 가산)·기법(happy_path 가산, negative_deep/cross_feature 감산)·민감도(보안/권한 감산) 보정. **참고문서가 없어 모두 INFERRED인 DOM-only 시험에서도** 신뢰도·기법으로 동작한다(전수 검토 아님).

| 버킷 | 기준 | 의미 | 검토 방법 |
|---|---|---|---|
| 🔴 **집중 검토** | 위험점수 < 0.45 | 저신뢰·추론 강함 = 거짓 가능성↑ | **여기에 집중**. 한 건씩 정독 |
| 🟡 **빠른 확인** | 0.45 ~ 0.75 | 중간 | 스폿 체크 |
| 🟢 **안전** | ≥ 0.75 | 고신뢰·근거 확실 | **일괄 승인 후보** |

- 상단 **버킷 칩**(건수 표시) 클릭 → 해당 버킷만 필터. "전체"로 복귀.
- **🟢 안전 일괄 승인** 버튼 → 안전 버킷을 한 번에 승인 → 검토 대상이 🔴에 집중됨.
- 상단 요약에 **"🔴 집중검토 N/M 완료"** 진행률 → 끝이 보임.
- 상세 패널 상단 **"[검토 안내]"** 한 줄이 *이 TC를 왜/얼마나 봐야 하는지* 설명.

> 부담 줄이는 흐름: ① 🟢 일괄 승인 → ② 🔴만 정독 → ③ 🟡 스폿 체크. 임계값은 시험 정책에 맞게 조정 가능(코드 상수).

### 7.3 빠른 검토 — 스크린샷·전후이동·키보드 (D58)
- **더블클릭** → TC 상세 팝업: **페이지 스크린샷** + **◀이전/다음▶** + **←/→ 키**로 연속 훑기.
- **키보드 단축키**(표에 포커스): **A** 승인 · **E** 수정 · **R** 거부 → 적용 후 자동으로 다음 행. **↑↓** 행 이동.
- 마우스 없이 🔴 버킷을 키보드로 빠르게 처리 가능.

### 7.4 4가지 결정
| 결정 | 의미 | 다음 단계 |
|---|---|---|
| **A (approved)** | TC 그대로 사용 | Stage 5 실행 |
| **E (edited)** | TC 일부 수정 후 사용 | 수정 내용 입력 → Stage 5 |
| **R (rejected)** | TC 폐기 | Stage 5 제외 |
| **P (pending)** | 보류 (정보 부족) | 매뉴얼 보강 후 재실행 |

**PoC-β 기준치 (D20):** TC당 평균 ≤ 60초, pending ≤ 5%, 재사용 의향 ≥ 3/5.

### 7.5 자주 하는 결정 패턴
- INFERRED인데 시나리오가 합리적 → **A** (단 reviewer_note에 근거 메모)
- happy_path인데 사전조건이 모호 → **E**로 사전조건 보강
- 같은 leaf에서 비슷한 TC 다수 → 중복 1개만 **A**, 나머지 **R**
- selector_stability < 0.4 (XPath) → **E**로 data-testid 또는 text 기반으로 교체

---

## 8. 자주 묻는 질문

**Q1. Mock과 실 API 결과가 다르면?**
A. Mock은 사전 정의된 TC만 반환한다 (그누보드5 26개 leaf 전용). 실 API는 매뉴얼 내용에 따라 다양해진다. **Mock은 회귀 검증용, 실 API는 품질 측정용**.

**Q2. provider를 바꾸면 캐시는?**
A. 캐시 키에 model이 포함되므로 (D48) 자동으로 별도 캐시. 같은 입력을 두 provider로 보내면 둘 다 새로 호출됨.

**Q3. 토큰을 어떻게 줄이나?**
A. 4가지 자동 작동(§4.4). 추가로:
- `prompts/*.md` 의 model을 `gemini-1.5-flash`로 → ~30배 절감 (품질 검증 필요)
- 같은 매뉴얼 재실행은 캐시 히트로 무료
- 매뉴얼 발췌 1500자 상한 — 길게 쓰면 무시됨

**Q4. PoC-α의 INFERRED 41.5% → 현재 0%, 어떻게?**
A. 자산 저장소 도입(2026-05-20). `data/assets/domain-invariants/BOARD_CMS.yaml` 의 12개 invariants가 매뉴얼 외 근거를 제공 → V3에서 INFERRED 비율에서 제외됨.

**Q5. 그누보드5 외 다른 OSS로 시험하려면?**
A.
1. 매뉴얼 파일을 markdown으로 작성 (그누보드5 spec 참고)
2. 해당 제품 유형에 맞는 invariants YAML 작성 (예: `USER_AUTH.yaml`)
3. `--manual <path>`로 지정 실행

**Q6. 결함 카탈로그는 어떻게 누적되나?**
A. Phase 2 운영 중. 현재 5건 시드(`data/assets/defect-catalog/BOARD_CMS/`). `patternProposal` 강제 여부는 미해결(`proposal-for-awt-claude/06-questions-to-resolve.md`).

**Q7. GUI 없이 CLI만으로 가능한가?**
A. 가능. `scripts/run_full_pipeline.py` (CLI) 사용. 단 Reviewer Gate는 Excel 직접 편집 후 `apply_gate_decisions` 호출 필요.

**Q8. .env와 GUI 저장 둘 다 있으면?**
A. **.env(환경변수)가 우선**. 운영 시는 GUI 저장 권장, CI/CD에서는 .env 사용.

---

## 9. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'anthropic'` | requirements 미설치 | `pip install -r requirements.txt` |
| `UnicodeEncodeError: 'cp949' codec` | Windows 콘솔 한글 인코딩 | `$env:PYTHONIOENCODING="utf-8"` 후 실행 |
| `ValueError: Unknown model prefix` | prompts/*.md 의 model 필드가 미지원 prefix | `claude-*`/`gpt-*`/`o1-*`/`o3-*`/`gemini-*` 중 선택 |
| `Anthropic API key is empty` | LLM_PROVIDER=anthropic인데 키 미설정 | `.env`에 `ANTHROPIC_API_KEY` 추가 또는 GUI 저장 |
| `Gemini provider requires 'google-genai' package` | 신 SDK 미설치 | `pip install google-genai>=0.3.0` |
| `playwright._impl._errors.Error` | Chromium 미설치 | `playwright install chromium` |
| `psycopg2.OperationalError` | PostgreSQL 미실행 또는 .env 오류 | `Get-Service postgresql*` 확인 |
| `http://localhost:8080` 접속 불가 | 그누보드5 컨테이너 미실행 | `docker compose up -d` |
| Reviewer Gate 색상이 모두 회색 | 모든 TC가 confidence 0.85+ | 정상 — 자산 저장소 효과. 빠른 검토 OK |
| Mock 회귀가 79가 아님 | 코드 변경으로 baseline 깨짐 | git log에서 마지막 정상 commit 확인 |

상세는 `SETUP.md` §10 참조.

---

## 10. 다음 단계로 가는 길

| 지금 | 다음 | 가이드 |
|---|---|---|
| 설치 마쳤음 | 시나리오 1 (Mock) 실행 | §5.1 |
| Mock 회귀 OK | API 키 발급 → 시나리오 2 (Stage 1~3) | §3.2, §5.2 |
| Stage 1~3 OK | Docker 설치 → 그누보드5 셋업 → 시나리오 3 | §3.3, §5.3 |
| Stage 0~7 OK | PostgreSQL + GUI 시나리오 4 | §5.4 |
| 시험원으로 실무 사용 | 다중 사용자 + 자산 누적 | Phase 2 운영 |
| Vendor 비교 실험 | provider 토글로 시나리오 5 | §5.5 |

### 미해결 결정 (운영 시 다뤄야 함)
- **patternProposal 강제 여부** (proposal-for-awt-claude 핵심) — 자산화 vs 단순 목록
- **Q-LLM-1~4** — provider별 토큰 계산 / ensemble / 캐시 분리 / UI 토글 정책
- **Q-MX-1~4** — 25023·25051·25059 매트릭스의 시험소 정합성

### 작업 이어가기
**`CONTINUE.md` §1 — Last updated** 를 매번 확인. 거기에 가장 최신 완료 항목과 다음 행동이 정리되어 있다.

---

## 부록 A. 핵심 결정 요약 (D1~D48)

| ID | 결정 |
|---|---|
| D1·D2·D7·D8 | ISO/IEC 25023:2016 + 25051:2014 기반, AI agent 역할 = end-to-end 자동화 |
| D22 | Reviewer Gate = 자동 실행 *이전* (사전 게이트 모델) |
| D37 | 프로덕션 = Windows 데스크탑 앱. Claude Code는 PoC·개발 환경 |
| D38 | LLM = stateless 호출, 대화 히스토리 없음 |
| D41 | 토큰 절약 4축 — per-leaf, 발췌, JSON Schema, 캐시 |
| D44·D45·D46 | PostgreSQL + PySide6 + Inno Setup |
| D47 | Phase 2 OSS = 그누보드5 |
| **D48** | **LLM provider 추상화 — Anthropic/OpenAI/Gemini, 모델 prefix 자동 라우팅** |
| **D49** | **negative_category 5enum + V10 강제 — leaf 적용 카테고리당 ≥ 1 TC (제안 #4)** |
| **D50** | **failure_category 5enum — V6 정적 + LLM 동적 통합 (제안 #5)** |
| **D51** | **전역 컴포넌트 dedup — 헤더 로그인 등 다(多)페이지 공통 요소를 1회만 명세(로그인 편중 완화)** |
| **D52** | **카테고리 통제 어휘 — 대분류 12종 고정(인증 도메인 분열 통합), 중/소분류 한글 생성** |
| **D53** | **기능 확정 게이트 — Stage1↔2 사이 도메인 집계·leaf 제외(opt-in)** |
| **D54** | **페이지 그룹 TC 설계 + 교차 페이지 시나리오 — 호출 급감 + 기능 관계 인식** |
| **D55** | **LLM 호출 병렬화 — 동시성 기본 6, 결정성 유지(=1이면 순차)** |
| **D56** | **V10 보완 배치 재설계 — gap당 순차→페이지 그룹 배치, 증식 상한** |
| **D57** | **Reviewer Gate 리스크 버킷 — 위험점수 3분류, 🟢 일괄승인, 위험군 진행률** |
| **D58** | **Reviewer Gate 상세 강화 — 스크린샷·전후이동·키보드(A/E/R)** |

전체 결정 이력: `doc/06-decisions.md`

---

## 부록 B. 외부 검토 제안 채택 현황 (`proposal-for-awt-claude/`)

| # | 권고 | 상태 |
|---|---|---|
| 1 | 결함 카탈로그 스키마 + 적재 | ✅ 완료 (5건 시드) |
| 2 | domain-invariants YAML 채널 | ✅ 완료 (BOARD_CMS·USER_AUTH) |
| 3 | V6 selector 안정성 점수 | ✅ 완료 (36 tests PASS) |
| 4 | negative 카테고리별 minimum count 강제 | ✅ 완료 (D49 — V10 + 5enum + 12 tests PASS) |
| 5 | 실패 TC 4분류 → 5분류 enum | ✅ 완료 (D50 — V6+LLM 통합 + 14 tests PASS) |

### 핵심 미결정 (제안서가 가장 자주 빠뜨리는 결정으로 식별)
- **patternProposal 작성을 프로젝트 종료 게이트에 강제할 것인가?**
  - Yes → 결함 카탈로그가 *학습 자산* 이 됨
  - No → 결함 목록에 그침
  - 운영 정책 결정 시 처리

---

## 부록 C. 개발 지침 (불변)

코드·문서 변경 시 모든 사용자가 지켜야 할 규칙:

1. **설계 우선** — 코딩 전 `doc/` 합의·동결
2. **수정계획 제시** — 즉시 코딩 금지, 변경안 사전 제시
3. **추측 금지** — 모르면 묻기
4. **Skill화 고려** — 분리 배포 단위로 설계 (Phase 2)
5. **디렉터리 확인** — 새 파일 작성 전 위치 확인
6. **단계 제안** — 단계 완료 시마다 다음 후보 + 추천 + 이유 명시

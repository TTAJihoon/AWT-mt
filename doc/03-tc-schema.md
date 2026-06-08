# TC 스키마 + 설계 기법 + 검증 규칙

> Stage 2 (TC 설계) + Stage 3 (V1~V5) + Stage 4 (Reviewer Gate) 산출의 컬럼·타입·검증 통합 정의.

---

## 1. 스키마 개요

TC 1행 = 시험 1건. 5개 그룹 컬럼:

| 그룹 | 컬럼 | 채워지는 시점 |
|---|---|---|
| **G1. 표준 양식** | tc_id, 대분류, 중분류, 소분류, scenario(시나리오), precondition, expected | Stage 2 |
| **G2. 설계 근거** | requirement_id, design_technique, source_quote | Stage 2 |
| **G3. 신뢰도** | gen_confidence, exec_confidence | Stage 2 / Stage 5 |
| **G4. Gate** | review_status, reviewer_note, reviewer_id | Stage 4 |
| **G5. 실행 결과** | actual, result, failure_reason | Stage 5 / Stage 6 |

---

## 2. 컬럼 정의

### G1. 표준 양식

| 컬럼 | 타입 | 필수 | 설명 | 예시 |
|---|---|---|---|---|
| `tc_id` | string | ✓ | `TC-XXX-YYY` 형식. XXX=leaf 일련번호, YYY=변형 번호. (D9·D17·D18·D19) | `TC-007-002` |
| `대분류` | string | ✓ | 기능리스트 대분류명 | `회원관리` |
| `중분류` | string | ✓ | 기능리스트 중분류명 | `비밀번호` |
| `소분류` | string | ✓ | 기능리스트 최하위(leaf) 분류명 | `변경` |
| `scenario` | string | ✓ | 테스트 시나리오 (자연어 한 문장) | `현재 비밀번호 입력 후 새 비밀번호로 변경` |
| `precondition` | string | ✓ | 사전입력조건. 없으면 "없음" | `회원가입 완료 + 로그인 상태` |
| `expected` | string | ✓ | 기대 출력 값. 객관 검증 가능한 형태 | `"비밀번호가 변경되었습니다" 토스트 + 로그아웃` |

### G2. 설계 근거

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `requirement_id` | string | ✓ | 기능리스트의 해당 행 식별자 (대>중>소 경로) |
| `design_technique` | enum | ✓ | §3의 7가지 중 하나 |
| `source_quote` | string | ✓ | 매뉴얼 원문 발췌 + 위치, 또는 `INFERRED: <근거>` |

### G3. 신뢰도

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `gen_confidence` | float [0,1] | ✓ | TC 생성 시 신뢰도. source_quote 명료성 + 명세 강도. 소수점 2자리 |
| `exec_confidence` | float [0,1] | 실행 후 ✓ | 실행 시 신뢰도. 셀렉터 안정성 + 재시도 + oracle 명료성 |

### G4. Reviewer Gate

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `review_status` | enum | ✓ | `approved` / `edited` / `rejected` / `pending` |
| `reviewer_note` | string | 선택 | 검토자 메모 |
| `reviewer_id` | string | 변경 시 ✓ | 검토자 식별 |

### G5. 실행 결과

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `actual` | string | 실행 후 ✓ | 실제 출력 |
| `result` | enum | 실행 후 ✓ | `pass` / `fail` / `blocked` / `not_executed` |
| `failure_reason` | string | result=fail 시 ✓ | 4축: 실제출력 / 차이 / 원인후보 / 재시도이력 |
| `failure_category` | enum | result=fail 시 ✓ | §6 5분류 enum (D50). V6 정적 + LLM 분석 통합 |
| `failure_category_source` | enum | failure_category 있을 시 ✓ | `v6_static` / `llm_failure_analysis` / `merged` |

### G6. 음성 카테고리 (D49)

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `negative_category` | enum | technique이 negative_* 시 ✓ | §7 5카테고리 중 하나 (`validation_failure` / `duplicate_or_conflict` / `permission_denied` / `boundary_violation` / `injection_or_security`) |

---

## 3. 7가지 설계 기법 (design_technique enum)

| 기법 | 정의 | 적용 가이드 |
|---|---|---|
| `happy_path` | 정상 흐름. 명세대로 입력 → 명세대로 출력 | leaf당 최소 1개 |
| `equivalence` | 등가 분할. 입력 도메인 별 대표값 | 도메인 2개 이상이면 도메인별 1개 |
| `boundary` | 경계값. min/max ± 1, 빈 입력, 길이 상한 | 수치·길이 제약 있으면 양 경계 |
| `negative_basic` | 기본 부정. 명세 위반 입력에 대한 에러 | leaf당 1개 이상 |
| `negative_deep` | 심층 부정. 권한 우회, XSS, 메시지 적절성 | 위험 영역 1개 이상 |
| `state_transition` | 상태 전이. 다단계 워크플로 step 누락·역순 | 워크플로 기능 시 |
| `cross_feature` | 기능 결합. 의미 연관 기능과의 조합 | 기능 간 연관 시 |

**원칙:** 적용 불가능한 기법은 강제하지 않음. 단 `happy_path`는 모든 leaf에 필수.

**TC 수 가이드 (강제 아님):**
- 단순 CRUD: 3~8개
- 입력 검증 포함: 8~20개
- 다단계 워크플로: 15~40개
- 제품당 약 200~500개

---

## 4. 데이터 타입·형식 규칙

| 항목 | 규칙 |
|---|---|
| 인코딩 | UTF-8 (Excel은 BOM 포함) |
| 줄바꿈 | `\n` (Excel wrap text) |
| 셀 최대 길이 | Excel 한도 32,767자 |
| `tc_id` 정규식 | `^TC-\d{3}-\d{3}$` |
| enum 표기 | snake_case (소문자 + `_`) |
| confidence 범위 | `[0.0, 1.0]`, 소수점 2자리 |
| 빈 셀 정책 | 필수 컬럼 비면 V1 reject. 선택 컬럼은 빈 문자열 허용 |

---

## 5. V1~V10 검증 규칙 (Stage 3 자동 실행)

| # | 검증 | 대상 | 규칙 | 실패 시 |
|---|---|---|---|---|
| **V1** | 필수 컬럼 | G1 + G2 + G3의 gen_confidence | 빈 셀 금지 | 행 reject + 재호출 |
| **V2** | source_quote 실재성 | G2.source_quote | 매뉴얼 텍스트에 substring 일치 (공백·줄바꿈 정규화) | `INFERRED: verification failed` 마킹 + Gate 우선 |
| **V3** | INFERRED 비율 | G2.source_quote | 전체 TC 중 INFERRED 비율 ≤ 임계 | 임계 초과 시 재호출 (PoC-α 결과 41.5% → 임계 정량은 PoC-β 후 결정) |
| **V4** | 기법 분포 | G2.design_technique | `happy_path` 비율 ≤ 50% | 초과 시 "기법 다양화" prompt 재호출 |
| **V5** | leaf 커버리지 | G2.requirement_id | 기능리스트의 모든 leaf에 최소 1개 TC | 누락 leaf 명시 재호출 |
| **V6** | selector 안정성 | exec_metadata.selectors | 9계층 점수 ≥ 0.62 | `failure_category=selector_broken` 자동 마킹 |
| **V10** | 음성 카테고리 커버리지 (D49) | G6.negative_category | leaf 적용 가능 카테고리 중 ≥ `min_coverage` 충족. 단, 카테고리당 ≥ 1 TC | 미충족 카테고리 명시 재호출 (TC_REGEN) |

> V7~V9는 외부 제안서(`proposal-for-awt-claude`)에서 *Jaccard 중복도·invariants 실재 확인·TestPattern 적용 완전성*으로 예약. Phase 2 도입 대상.

**재호출 prompt 패턴 (TC_REGEN Contract 사용):**
실패 TC만 추출 + 실패 사유 명시 + 수정 지침. 동일 사이클 최대 3회.

**3회 초과 처리:**
- 해당 항목 `INFERRED: max_retry_exceeded` 마킹
- Reviewer Gate 강제 검토 대상으로 표시

---

## 6. Excel 4시트 구조

`data/runs/<run-id>/tc_final.xlsx`:

| 시트 | 컬럼 | 목적 |
|---|---|---|
| **표준 양식** | G1 + G5 핵심 | 시험원이 익숙한 형태 (인증 산출물 추출용) |
| **AWT_Meta** | G2 + G3 + G4 | 설계 근거 + 신뢰도 + Gate 결정 |
| **Layer3_Aids** | 수동 시험 보조 자료 인덱스 | L3 영역 시험원 참고 |
| **Metrics** | 25023 메트릭 % 자동 계산 | Phase 2 |

→ 시트 1은 `tc_id`로 다른 시트와 join. 인증 제출 시 시트 1만 추출 가능.

---

## 7. Stage별 적용 시점 정리

| Stage | 채워지는 컬럼 | 채우는 주체 |
|---|---|---|
| Stage 2 종료 | G1 + G2 + G3.gen_confidence | LLM (TC_DESIGN) |
| Stage 3 종료 | G2.source_quote 보강 (V2 실패 시 INFERRED 마킹) | AWT 로컬 |
| Stage 4 종료 | G4 (review_status, reviewer_note, reviewer_id) | 사용자 |
| Stage 5 종료 | G3.exec_confidence + G5 (actual, result) | Playwright 로컬 |
| Stage 6 종료 | G5.failure_reason | LLM (FAILURE_ANALYSIS) |
| Stage 7 종료 | 모든 컬럼 동결 | AWT 로컬 |

---

## 6. failure_category enum (D50) — Stage 6 LLM 분석 + V6 정적 통합

| enum | 의미 | 판정 기준 | 다음 조치 |
|---|---|---|---|
| `selector_broken` | 셀렉터 깨짐·불안정 | V6 stability_score < 0.40, 또는 LLM이 NoSuchElement·timeout 식별 | V6 점수 재계산 + selector 보강 (data-testid 권장) |
| `scenario_error` | 시나리오 자체 모순 | precondition·steps 불일치, 또는 매뉴얼 misread | `TC_REGEN` 대상 |
| `expected_mismatch` | 기대값 부정확 | 실제 출력은 정상이나 expected가 추상·잘못된 값 | invariants 보강 + `expected` 수정 |
| `real_defect` | 진짜 제품 결함 | actual ≠ expected, oracle 명료, selector 안정 | `defect-catalog` 적재 ✓ |
| `fictional_positive` | spec hallucination | source_quote=INFERRED 인데 FAIL → TC가 가공된 명세 검증 의심 | TC 폐기 + 매뉴얼 보강 권고 |

### 6.1 통합 흐름
1. **Stage 5 직후 (V6 정적)** — selector 점수가 명백히 낮으면 `selector_broken` 사전 부여 (`failure_category_source = v6_static`)
2. **Stage 6 (LLM 분석)** — V6가 마킹 안 한 FAIL에 한해 LLM이 5분류 enum 부여 (`failure_category_source = llm_failure_analysis`)
3. **충돌 시** — V6 결과 우선 (정적 분석이 더 신뢰됨), `failure_category_source = merged` + 부가 정보 `actual_output_summary`에 LLM 의견 보존

### 6.2 V6 4분류 ↔ D50 5enum 매핑

| V6 (정적) | D50 (LLM 통합) | 비고 |
|---|---|---|
| `selector_unstable` | `selector_broken` | 명명 통일 |
| `oracle_mismatch` | `expected_mismatch` | 명명 통일 |
| `app_defect` | `real_defect` | 명명 통일 |
| `blocked` | (별도 `result=blocked`로 처리) | failure_category 부여 안 함 |
| (없음) | `scenario_error` | LLM만 판정 가능 |
| (없음) | `fictional_positive` | LLM만 판정 가능 |

---

## 7. negative_category enum (D49) — Stage 2 TC 설계 강제

`design_technique`이 `negative_basic` 또는 `negative_deep`인 TC는 `negative_category` 1개 필수.

| 카테고리 | 의미 | 예시 시나리오 |
|---|---|---|
| `validation_failure` | 입력 형식·필수값 위반 | 이메일 형식 오류, 필수 필드 비움, 길이 미달 |
| `duplicate_or_conflict` | 중복·동시성·충돌 | 중복 아이디 가입, 동시 수정, 이미 존재하는 키 |
| `permission_denied` | 권한 거부 | 비로그인 접근, 권한 없는 사용자 시도, 만료 토큰 |
| `boundary_violation` | 경계값 초과 | 최대 길이 +1, 0/음수, 파일 크기 상한 초과 |
| `injection_or_security` | 보안 공격 패턴 | SQL injection, XSS, Path traversal, CSRF |

### 7.1 leaf 유형별 적용 가능 카테고리 (단순화)

| leaf 유형 추정 | 적용 가능 (필수 ≥ 1) | 비고 |
|---|---|---|
| 입력 폼 (가입·로그인·작성·수정) | `validation_failure`, `duplicate_or_conflict`, `boundary_violation` | 권한·보안은 leaf 성격상 추가 |
| 조회·검색·필터 | `permission_denied`, `injection_or_security` | validation은 옵션 |
| 권한·인증 관리 | `permission_denied`, `validation_failure` | 거의 항상 필요 |
| 파일 업로드 | `validation_failure`, `boundary_violation`, `injection_or_security` | 5종 모두 적용 가능 |
| 결제·주문 | `validation_failure`, `duplicate_or_conflict`, `permission_denied` | state_transition 동반 |

### 7.2 V10 동작
- `min_coverage` 기본 0.6 (적용 가능 카테고리 중 60% 충족)
- 각 카테고리당 ≥ 1 TC 필수 (강제)
- 카테고리 누락 시 `TC_REGEN`에 누락 카테고리 명시
- 강제 적용 안 되는 leaf (read-only 조회 등): V10 skip (적용 가능 0개)

---

## 8. 미해결 (운영 단계 결정)

| ID | 질문 |
|---|---|
| Q-SCH-1 | `precondition`을 별도 시트로 정규화할지 (반복 제거) |
| Q-SCH-2 | `steps`의 DSL화 — Playwright 자동 변환 위해 정형 단계 형식 도입할지 |
| Q-SCH-3 | `failure_reason` 4축의 컬럼 분리 vs 한 컬럼 |
| Q-SCH-4 | `reviewer_id` 익명화 여부 |
| Q-PA-1 | source_quote grep의 fuzzy 허용 범위 (한자↔한글, 띄어쓰기) |
| Q-PA-2 | V3 INFERRED 임계 정량 (PoC-β 후 확정) |
| Q-PA-3 | 재호출 3회 상한 적정성 |

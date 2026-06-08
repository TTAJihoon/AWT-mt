# TC 스키마 — 컬럼 정의 (PoC-무관 부분)

**작성일:** 2026-05-18
**상태:** **확정.** D25(Standalone pivot) 후 D28에 따라 *기존 skill 호환성 검토 불요*. §4·§5는 AWT 자체 정의로 완결.

> **이 문서의 범위:** TC 산출물의 컬럼 정의·타입·검증 규칙. D25 후 AWT가 모든 컬럼을 자유롭게 정의하므로 외부 호환성 제약 없음.

---

## 1. 스키마 개요

TC 1행 = 시험 1건. 다음 4개 그룹의 컬럼으로 구성:

| 그룹 | 컬럼들 | 출처 |
|---|---|---|
| **G1. 기존 (보존)** | tc_id, precondition, steps, expected | 기존 skill 자산 (`00-existing-method-interview.md` D, F6) |
| **G2. AWT E1·E2 (추가)** | requirement_id, design_technique, source_quote | `05-prompt-augmentation.md` §3.1 |
| **G3. AWT E3·E4 (추가 — 후속 설계)** | oracle_reason, gen_confidence, exec_confidence | E3·E4 설계 후 확정 |
| **G4. Reviewer Gate (추가)** | review_status, reviewer_note, reviewer_id, rerun_flag | `00b-gap-analysis.md` E5 |
| **G5. 실행 결과 (기존 보강)** | actual, result, failure_reason | actual은 기존, result/failure_reason은 E3 보강 |

---

## 2. 컬럼 정의 (각각 PoC 결과와 무관하게 확정 가능한 부분)

### G1. 기존 보존

| 컬럼 | 타입 | 필수 | 설명 | 예시 |
|---|---|---|---|---|
| `tc_id` | string | ✓ | `TC-XXX-YYY` 형식 (D9·D17·D18·D19). XXX=기능 최하위 분류 일련번호, YYY=동일 기능 내 TC 변형 번호. 3자리 + 3자리 고정. | `TC-007-002` |
| `precondition` | string | ✓ | 시험 전 만족돼야 할 조건. 한국어 자연 서술. 없으면 "없음". | `회원가입 완료 + 로그인 상태` |
| `steps` | string | ✓ | 실행 단계. 번호 매긴 줄. Playwright MCP가 해석 가능한 수준 (D24). | `1. 마이페이지 접속\n2. 비밀번호 변경 버튼 클릭\n3. 현재 비밀번호 입력 …` |
| `expected` | string | ✓ | 기대 결과. 객관적 검증 가능한 형태. | `"비밀번호가 변경되었습니다" 토스트 노출 + 로그아웃 처리` |

### G2. AWT E1·E2 (추가)

| 컬럼 | 타입 | 필수 | 설명 | 예시 |
|---|---|---|---|---|
| `requirement_id` | string | ✓ | 기능리스트의 해당 행 식별자. 대분류·중분류·소분류 경로 그대로 표기. | `회원관리 > 비밀번호 > 변경` |
| `design_technique` | enum | ✓ | 7가지 중 하나. `happy_path` / `equivalence` / `boundary` / `negative_basic` / `negative_deep` / `state_transition` / `cross_feature` | `boundary` |
| `source_quote` | string | ✓ | 매뉴얼·기능리스트 원문 발췌 + 위치. 추론은 `INFERRED: <근거 한 줄>` 형식. | `manual.pdf p.12 §3.2 "비밀번호는 8자 이상 16자 이하"` |

### G3. AWT E3·E4 (추가 — 후속 설계 대기)

| 컬럼 | 타입 | 필수 | 설명 | 결정 시점 |
|---|---|---|---|---|
| `oracle_reason` | string | ✓ | PASS/FAIL 판정의 *근거* — 어떤 source/rule로 expected를 결정했나 | E3 설계 |
| `gen_confidence` | float [0,1] | ✓ | TC 생성 시 confidence. source_quote 명료성 + 기능 명세 강도. | E4 설계 |
| `exec_confidence` | float [0,1] | ✓ | 실행 시 confidence. 셀렉터 안정성 + 재시도 횟수 + oracle 명료성. | E4 설계 |

### G4. Reviewer Gate (추가)

| 컬럼 | 타입 | 필수 | 설명 | 예시 |
|---|---|---|---|---|
| `review_status` | enum | ✓ | `pending` / `approved` / `edited` / `rejected` | `approved` |
| `reviewer_note` | string | 선택 | 검토자가 남긴 메모 | `expected를 한 줄 보강함` |
| `reviewer_id` | string | ✓ if 변경 | 검토자 식별 | `kim.j` |
| `rerun_flag` | boolean | 선택 | 자동실행에서 *재실행 대상*인지 (D23 활용) | `false` |

### G5. 실행 결과

| 컬럼 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `actual` | string | 실행 후 ✓ | 실제 출력 (기존 컬럼 보존, F6) |
| `result` | enum | 실행 후 ✓ | `pass` / `fail` / `blocked` / `not_executed` |
| `failure_reason` | string | result=fail 일 때 ✓ | 실패 원인 4축: 실제출력 / 차이 / 원인후보 / 재시도이력 (E3) |

---

## 3. 데이터 타입·형식 규칙 (PoC-무관)

### 3.1. 문자열

- 인코딩: UTF-8
- 줄바꿈: `\n` (Excel에서는 wrap text)
- 최대 길이: 별도 제한 없음 (Excel cell 32,767자 한도까지)

### 3.2. ID 형식

- `tc_id` 정규식: `^TC-\d{3}-\d{3}$`
- 위반 시 자동 reject

### 3.3. enum 값

- 모든 enum은 소문자 + 언더스코어 (snake_case)
- 미정의 값은 자동 reject

### 3.4. confidence (E4 확정 후)

- 범위 `[0.0, 1.0]`, 소수점 2자리
- threshold 후보: 0.4 / 0.7 / 0.9 (Phase 1 ⑪ Reviewer 시간 budget 분석 참조)

### 3.5. 빈 셀 정책

- 필수 컬럼이 비어있으면 자동 reject
- 선택 컬럼은 비워둘 수 있음 (빈 문자열로 통일)

---

## 4. 시험소 표준 양식과의 통합 (D25 후 확정)

D28에 따라 AWT가 모든 컬럼을 정의함. 시험소 표준 Excel 양식을 *base layout*으로 채택하고, AWT 추가 컬럼은 다음 원칙으로 배치:

- **시트 1: 시험소 표준 양식** (G1 + G5 핵심 컬럼)
  - tc_id, precondition, steps, expected, actual, result — 시험원이 익숙한 컬럼만
- **시트 2: AWT_Meta** (G2 + G3 + G4)
  - tc_id로 join, requirement_id, design_technique, source_quote, oracle_reason, gen_confidence, exec_confidence, review_status, reviewer_note, reviewer_id
- **시트 3: Layer3_Aids** (보조 자료 인덱스)
- **시트 4: Metrics** (Phase 2의 25023 메트릭 % 자동 계산 결과)

**이유:**
- 시험원이 *익숙한 시트만* 보고도 시험 가능
- AWT 메타는 *별도 시트*로 분리되어 시험소 표준 산출물에 영향 없음
- tc_id join으로 두 시트를 *논리적으로 묶음*
- 인증 산출물 제출 시 *시트 1만* 추출 가능

---

## 5. 검증 규칙 자동화 (D25 후 확정)

`05-prompt-augmentation.md` §4의 V1~V5 검증 + 본 §2 컬럼 정의의 통합 사양.

| 검증 | 대상 컬럼 | 규칙 | 위반 시 |
|---|---|---|---|
| V1 | G1·G2·G3 필수 컬럼 | 빈 셀 금지 | 행 reject + 재호출 |
| V2 | G2 source_quote | 매뉴얼 grep M2 정규화 일치 | INFERRED 마킹 + Gate 우선 |
| V3 | G2 source_quote | INFERRED 비율 ≤ 5% (또는 PoC-α 결정 임계) | 5~15% 경고, 15%+ 재호출 |
| V4 | G2 design_technique | happy_path ≤ 50% | 기법 다양화 prompt 재호출 |
| V5 | G2 requirement_id | 기능리스트 leaf set과 비교, 누락 없음 | 누락 기능 명시 재호출 |
| V6 | G3 gen_confidence | 0.0~1.0, 소수점 2자리 | 형식 오류 시 자동 보정 또는 reject |
| V7 | G4 review_status | enum 값만 | 형식 오류 reject |

**자동 검증 실행 시점:**
- Stage 2 종료 직후 (V1~V5)
- Stage 4 Gate 종료 직후 (V7)
- Stage 6 종료 직후 (G3 보강 검증)

---

## 6. 적용 시점

| 단계 | 컬럼 채워짐 | 책임 |
|---|---|---|
| TC 생성 직후 | G1 + G2 + G3의 gen_confidence | AI (강화 prompt) |
| Post 검증 후 | G3 source_quote INFERRED 마킹 보강 | AWT |
| Reviewer Gate 통과 후 | G4 | 시험원 |
| 자동실행 후 | G3의 exec_confidence + G5 | AI (실행 + 판정) |
| 최종 산출 시 | 모든 컬럼 동결 | AWT |

---

## 7. 미해결

| ID | 질문 | 결정 시점 |
|---|---|---|
| Q-SCH-1 | `precondition`을 *별도 시트의 공유 가능 항목*으로 정규화할지 (반복 제거) | E5 워크플로 작성 시 |
| Q-SCH-2 | `steps`의 *DSL화* — Playwright 자동 변환을 쉽게 하려면 자연어보다 정형 단계가 유리할 수 있음 | E3 설계 시 |
| Q-SCH-3 | `failure_reason` 4축의 *컬럼 분리* vs *한 컬럼 다섯 줄* | E3 설계 시 |
| Q-SCH-4 | `reviewer_id`를 익명화할지 (다른 시험원에게 공개 시) | 운영 단계 |

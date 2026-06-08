# PoC Quick Start — 2026-05-19

**Phase 1.0 — 시험소가 운영 중인 기존 Claude Code 시험방법 skill의 분리 호출·prompt augmentation 실증.**

> **전체 계획서:** `doc/03-architecture/06-poc-validation-plan.md`
> **본 문서:** *지금 바로 시작*할 수 있는 압축 가이드. 30분~3시간 소요 예상.

---

## 0. 준비 체크리스트 (5분)

- [ ] 대상 제품 1개 선정 — 간단한 웹 (기능 5~10개, 매뉴얼 10~30페이지). 학습용 샘플도 OK (예: 간단한 게시판, TodoMVC 클론)
- [ ] 입력 폴더 준비 — 매뉴얼·기능리스트·URL·결함샘플
- [ ] 기존 시험방법 skill을 평소대로 호출 가능한 환경
- [ ] 본 폴더(`data/poc/2026-05-19/`)에 결과 기록 준비

---

## 1. PoC-1 Option (a) — "TC만 생성하고 stop" (가장 먼저 시도)

**예상 소요:** 20~30분

### 1.1. 평소처럼 기존 skill을 호출하되, 사용자 메시지 *끝에* 다음을 추가

```
[중단 지시]
이번 호출에서는 TC Excel만 산출하고, 어떠한 브라우저 자동화·클릭·입력도 수행하지 마라.
TC 시트 산출 직후 즉시 종료한다.

[강화 출력 요구 — AWT E1·E2 강제 prompt]
모든 TC는 반드시 다음 컬럼을 포함한다:
  - requirement_id : 기능리스트의 "대분류>중분류>소분류" 경로
  - design_technique : happy_path / equivalence / boundary / negative_basic / negative_deep / state_transition / cross_feature 중 하나
  - source_quote : 매뉴얼 또는 기능리스트의 원문 그대로 발췌 + 위치 (예: "manual.pdf p.12 §3.2 '비밀번호는 8자 이상'"). 추론은 "INFERRED: <근거 한 줄>"로 표시.

각 최하위 기능마다:
  - happy_path 최소 1개
  - 입력 도메인 2개 이상이면 equivalence 도메인별 1개
  - 수치/길이 제약 있으면 boundary 양쪽 2개
  - negative_basic 1개 이상
  - 다단계 워크플로면 state_transition 중간 step 누락 1개

TC ID 형식: TC-XXX-YYY (XXX=기능 최하위 분류 일련번호, YYY=같은 기능 내 변형 번호, 둘 다 3자리)

산출 후 self-check:
  - 모든 행에 source_quote 있는가
  - INFERRED 비율 5% 이하인가
  - design_technique 분포에서 happy_path 50% 이하인가
self-check 미통과면 결과를 *제출하지 말고* 수정 후 재산출.
```

### 1.2. 관찰 항목

- [ ] skill이 *Excel만* 산출하고 멈췄는가, 아니면 평소대로 자동실행까지 진행했는가
- [ ] Excel에 위 컬럼들이 모두 포함됐는가
- [ ] design_technique 분포 (스크린샷 또는 카운트)
- [ ] source_quote 채워진 행 수 / INFERRED 행 수 / 비어있는 행 수

### 1.3. PASS / FAIL 판정

| 조건 | 판정 |
|---|---|
| skill이 TC Excel만 산출하고 자동실행 안 함 | (a) PASS |
| skill이 무시하고 자동실행까지 진행 | (a) FAIL → §2로 |
| skill이 일부만 따름 (예: 자동실행 안 했지만 컬럼 누락) | (a) PARTIAL → 메모 후 §2도 시도 |

### 1.4. 결과 기록

`data/poc/2026-05-19/result.md`에 옵션 (a) 결과 기록:
```
option_a: PASS / FAIL / PARTIAL
  - skill이 자동실행을 멈췄나? Y/N
  - 컬럼 추가됐나? Y/N (누락 컬럼: ...)
  - source_quote 채움률: __%
  - INFERRED 비율: __%
  - design_technique 분포: happy=__/equiv=__/bound=__/...
  - 메모: <자유 노트>
```

---

## 2. PoC-1 Option (b) — 재시험 메커니즘 (옵션 a 실패 시)

**예상 소요:** 30~40분

### 2.1. 절차

1. 평소대로 기존 skill 호출 → 1차 시험 완료 (생성 + 자동실행 + 보고서)
2. 결과 Excel을 *수동으로 일부 수정* — 예: 3개 TC의 expected 값을 임의로 변경
3. 수정된 Excel을 첨부해 재시험 요청:
   ```
   [재시험 입력]
   첨부한 TC 시트의 expected가 수정되었다.
   변경된 TC만 다시 실행하고 결과를 채워라.
   새 TC는 만들지 마라. 변경 없는 TC의 기존 결과는 유지하라.
   ```

### 2.2. 관찰

- [ ] skill이 수정된 TC만 재실행했는가
- [ ] 다른 TC의 기존 결과가 보존되었는가
- [ ] 새 TC를 만들지 않았는가

### 2.3. 결과 기록

```
option_b: PASS / FAIL
  - 수정된 TC만 재실행? Y/N
  - 기존 결과 보존? Y/N
  - 새 TC 생성 여부: Y/N
  - 메모: ...
```

---

## 3. PoC-1 Option (c) — Playwright MCP 직접 호출 (a·b 모두 실패 시)

**예상 소요:** 30~60분

### 3.1. 절차

1. AWT가 자체적으로 Playwright MCP로 TC 실행하는 시도:
   ```
   첨부한 TC 시트의 steps를 Claude Code의 Playwright MCP로 직접 실행하고,
   각 TC의 result + actual 컬럼을 채워라.
   ```
2. steps 컬럼의 자연어를 Playwright 액션으로 변환 가능한지 관찰

### 3.2. 결과 기록

```
option_c: PASS / FAIL
  - Playwright MCP로 실행 가능했나? Y/N
  - steps 자연어 → 액션 변환 성공률: __%
  - 메모: ...
```

---

## 4. PoC-2~6 동시 측정 (PoC-1 결과 위에서)

PoC-1에서 산출된 TC Excel을 활용해 다음을 *추가 5~30분*에 측정:

### PoC-2: source_quote grep 정확도

- TC 시트의 source_quote 컬럼 *임의 10개* 추출
- 매뉴얼 PDF에서 텍스트 검색
- 매칭률 측정:
  ```
  M1 (완전일치): __/10 = __%
  M2 (공백정규화): __/10 = __%
  M3 (띄어쓰기무시): __/10 = __%
  ```

### PoC-3: INFERRED 비율

- 자동 카운트 → `__%`

### PoC-5: Prompt 충돌

- AWT 강화 prompt를 *적용한 호출*과 *기존 prompt만으로의 호출* 결과 비교
- TC 수·design_technique 분포·자동실행 진행 여부 비교

### PoC-6: Excel 컬럼 수용성

- AWT 추가 컬럼이 기존 skill 산출에 *어떻게 들어갔는지* 관찰:
  - AS_IS_OK (기존 컬럼 옆에 그대로 추가)
  - NEED_SUFFIX (컬럼명 충돌로 _awt 접미사 필요)
  - NEED_RENAME (기존 컬럼명 변경 필요)
  - NEED_SEPARATE_SHEET (별도 시트 필요)

### PoC-4: 재호출 사이클 (별도 시간)

- §1·§2 결과의 self-check 실패율을 확인하고 재호출 1·2·3회의 통과율 측정

---

## 5. 결과 보고 — 한 페이지 요약

PoC 종료 후 `data/poc/2026-05-19/result.md`를 다음 양식으로 채워서 공유:

```
PoC 일자: 2026-05-19
대상 제품: <간단한 설명>
총 소요: __ 시간

PoC-1:
  option_a: PASS / FAIL / PARTIAL
  option_b: PASS / FAIL / (옵션 a PASS면 skip)
  option_c: PASS / FAIL / (a·b PASS면 skip)
  chosen_path: a / b / c / none

PoC-2:
  M1: __%
  M2: __%
  M3: __%
  채택 매칭 전략: M_

PoC-3: INFERRED __%, 결정: 5%·10%·15% 중 ___

PoC-4: 재호출 1회 __%, 2회 __%, 3회 __%, 상한 _회

PoC-5: 충돌 없음 / 조정 필요 / 심함 — <상세>

PoC-6: 컬럼 전략 채택 — AS_IS_OK / NEED_SUFFIX / NEED_RENAME / NEED_SEPARATE_SHEET

기타 발견: <자유 노트>
```

---

## 6. 막히면

다음 시점에 막힐 가능성:

| 상황 | 도움 요청 |
|---|---|
| 기존 skill이 AWT prompt를 거부 / 깨짐 | skill의 응답 일부 공유 → AWT가 prompt 조정 제안 |
| Excel 컬럼 추가 시 형식 깨짐 | 결과 시트 스크린샷 공유 → AWT가 컬럼 전략 조정 |
| source_quote가 거의 다 INFERRED | 입력 매뉴얼 충실성 의심 → AWT가 매뉴얼 검토 가이드 |
| 자동실행 단계에서 시간 폭증 | 어느 단계에서 늘어났는지 timing 공유 |
| 기타 예상 외 | 노트만이라도 공유 → 같이 풀어감 |

---

## 7. 시작 신호

준비됐으면 §0 체크리스트 → §1 옵션 (a)부터 시작.

PoC 도중·종료 후 결과 공유해주면 다음 턴에서 분석·후속 설계로 진입.

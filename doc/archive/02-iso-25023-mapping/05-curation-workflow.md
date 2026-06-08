# Reviewer Gate Curation 워크플로

**적용 범위:** Phase 1 E5 (Gap analysis), D22(자동실행 *전* Gate), `03-semi-automatable.md` §3 우선순위.
**대상 독자:** 시험원 (사용자 본인 포함, *최초 reviewer 운영*).

> **본 문서의 목적:** 사용자가 *처음으로 reviewer 역할*을 무리 없이 수행할 수 있는 *운영 매뉴얼*. 거창한 도구 없이 Excel + 색상 + 정렬 + 단축키로 충분.

---

## 1. Gate의 위치와 책임

```
[TC 생성 (AI)]
   ↓
[AWT V1~V5 자동 검증]
   ↓
★ Reviewer Gate (현재 문서) ★
   ↓                          ↘
[승인된 TC만 자동실행]    [거절·재생성 요청 → TC 생성으로 복귀]
   ↓
[최종 산출]
```

**시험원 책임 (Gate에서):**
1. AWT 산출 TC의 *적정성* 검토
2. AWT 의견에 동의 / 수정 / 거절 표시
3. 잘못된 TC가 자동실행으로 흘러가지 않게 차단
4. 결재 (reviewer_id 기록)

**시험원 비책임:**
- TC를 *처음부터 만드는 것* (그건 AI 역할)
- 자동실행 직접 수행
- L3 영역 본격 시험 (별도 워크플로)

---

## 2. Excel 시트 구조

### 2.1. 컬럼 배치 (왼쪽부터)

```
[A] tc_id           [B] requirement_id     [C] design_technique
[D] gen_confidence  [E] source_quote       [F] review_status     ← 시험원 입력
[G] precondition    [H] steps              [I] expected
[J] oracle_reason   [K] reviewer_note      ← 시험원 입력
[L] reviewer_id     ← 시험원 입력
```

(자동실행 후 컬럼은 별도 시트 또는 본 시트 오른쪽에 추가)

### 2.2. 자동 색상·정렬 규칙

| 조건 | 행 색상 | 정렬 우선순위 |
|---|---|---|
| `source_quote = INFERRED` | 노란색 배경 | 상위 |
| `source_quote` 매뉴얼 grep 미일치 | 빨간색 배경 | 최상위 |
| `gen_confidence < 0.4` | 빨간색 배경 | 최상위 |
| `gen_confidence < 0.7` | 노란색 배경 | 중상위 |
| `gen_confidence ≥ 0.9` | 회색(연한) 배경 | 최하위 (일괄 승인 후보) |

→ 시트 열면 빨강·노랑·기본·회색 순으로 자연스럽게 시험원의 눈이 위험 항목부터 향함.

### 2.3. 시트 분리 (선택)

대규모 제품(TC 500+)에서는 시트 분리 권장:
- `TC_Risk` — 빨강·노랑만
- `TC_Normal` — 기본
- `TC_AutoApprove` — 회색 (일괄 승인 후보)

→ 시험원이 시트 단위로 처리 시간 통제 가능.

---

## 3. 4가지 결정 액션 (review_status)

각 TC에 대해 시험원은 다음 중 하나:

| 액션 | 의미 | 어떤 경우 | 시간 |
|---|---|---|---|
| **approved** | AWT 산출 그대로 자동실행 진행 | 회색 + 빨리 봐서 이상 없음 | 5~30초 |
| **edited** | 일부 수정 후 진행 (precondition/expected 등 변경) | 노란색 + 비현실적이거나 누락 발견 | 30초~2분 |
| **rejected** | 자동실행에 보내지 않음 (TC 자체 폐기) | 명백히 부적절·중복·환각 | 10~30초 |
| **pending** | 결정 보류 (논의·확인 필요) | 도메인 모호·심층 검토 필요 | 0 (지금 안 함) |

**중요 규칙:**
- 한 시트에 `pending`이 5% 이하로 유지되어야 다음 사이클 진입 (병목 방지)
- `pending`은 다음 sub-session에서 다시 본다
- `rejected` 후 *재생성 요청*하고 싶다면 별도 시트 `TC_Regenerate`에 사유와 함께 옮김

---

## 4. 시험원 처리 순서 가이드 (TC 1개 처리 절차)

### 4.1. 빠른 처리 (회색 행, confidence ≥ 0.9)

```
1. tc_id 확인 (1초)
2. design_technique·requirement_id로 *어떤 시험인지* 파악 (3초)
3. source_quote로 *근거가 매뉴얼에 있는지* 확인 (2초)
4. review_status = approved 입력 (1초)
총: 5~10초
```

일괄 처리 가능: 회색 행 N개 동시 선택 후 `approved` 일괄 입력 매크로.

### 4.2. 중간 처리 (기본 행, confidence 0.7~0.9)

```
1. tc_id·design_technique 확인 (3초)
2. source_quote + steps + expected의 *논리적 일관성* 확인 (10~20초)
3. precondition·expected가 매뉴얼과 정확히 일치하는지 (10~20초)
4. 이상 없으면 approved, 작은 수정이면 edited (해당 셀 직접 수정 후)
총: 30~60초
```

### 4.3. 깊은 처리 (노란/빨강 행, confidence < 0.7 또는 INFERRED)

```
1. design_technique이 적절한가 (5초)
2. source_quote가 매뉴얼 어디에 있는지 직접 PDF 열어 확인 (30초~1분)
3. steps가 *실제 가능한 동작 순서*인가 (15~30초)
4. expected가 *과도하게 일반적*이거나 *근거 없이 추론*된 것은 아닌가 (15~30초)
5. 결정:
   - 매뉴얼 근거 부재 → rejected + 사유 기록 → TC_Regenerate 시트로
   - 일부만 부족 → edited + 직접 수정
   - 명확함 → approved
6. reviewer_note에 *판단 근거* 한 줄 기록 (특히 edited/rejected 시 중요)
총: 1~3분
```

### 4.4. 보류 (pending)

```
1. 본인이 *지금 결정할 수 없는 이유*를 reviewer_note에 기록
2. pending 입력
3. 다음 sub-session에서 다시
주의: pending 비율이 5% 초과되면 *시험 중단* → 도움 요청 or 추가 자료 확보
```

---

## 5. 시간 budget 관리

### 5.1. 예상 시간 (TC 100~200개 기준, AI 산출 분포 가설)

| 분포 가정 (D20 budget 목표) | TC 수 | 평균 시간 | 합계 |
|---|---|---|---|
| 회색 (≥0.9) | 60% (120개) | 8초 | 16분 |
| 기본 (0.7~0.9) | 30% (60개) | 45초 | 45분 |
| 노란 (0.4~0.7 또는 INFERRED) | 8% (16개) | 1.5분 | 24분 |
| 빨강 (<0.4) | 2% (4개) | 3분 | 12분 |
| **합계 (제품 1개)** | **200개** | **평균 30초** | **약 1시간 30분** |

이 시간이 *분포가 깨지면 폭증*:
- 빨강이 10%로 늘면 → 합계 약 2시간 30분 (50% 증가)
- INFERRED가 20%로 늘면 → 합계 약 3시간

→ 분포 자체가 KPI. AWT prompt 조정으로 회색 비율을 최대화하는 게 시험원 시간 절감의 핵심.

### 5.2. 단일 세션 길이 권장

- 연속 검토는 **45분 이내** → 5~10분 휴식 (집중력 저하로 false approve 위험 ↑)
- 빨강·노랑이 많은 시트는 한 번에 *최대 20개*만 처리하고 휴식

### 5.3. 자동 일괄 승인 *경고*

회색 일괄 승인을 *기계적으로* 수행하면 false approve 위험. 권장:
- 일괄 승인 *전*에 시트의 *난수 sample 5개를 무작위 점검*
- sample에서 문제 발견 → 일괄 승인 *취소* + 분포 재검토

---

## 6. 결재 흐름

### 6.1. 단일 reviewer (Phase 1 기본)

- reviewer 1명이 전체 처리 → reviewer_id 기록 → 자동실행 진행

### 6.2. 2단 결재 (옵션)

도입 가능 시 (시험소 정책 따름):
- 1차 reviewer: 모든 TC 처리
- 2차 reviewer (선임): `edited` + `rejected`만 확인
- 2차 reviewer 컬럼 추가: `review2_status` / `review2_id`

본 Phase 1은 *단일 reviewer*로 시작 → 운영 후 필요 시 2단 확장.

---

## 7. Gate 후 단계로의 인계

Gate가 종료되면 다음을 산출:

1. **승인된 TC 시트** (`approved` + `edited`)
   → 기존 skill의 자동실행 단계로 인계 (D23 재시험 메커니즘 활용 — Q-INT-5 결과에 따라 옵션 a/b/c)

2. **거절·재생성 시트** (`rejected` + 재생성 요청)
   → TC 생성 단계로 재호출

3. **보류 시트** (`pending`)
   → 다음 sub-session까지 보관

4. **메타 데이터** (`data/metrics/<product>/<date>.json`)
   ```json
   {
     "gate_status": {"approved": 152, "edited": 31, "rejected": 12, "pending": 5},
     "reviewer_time_minutes": 92,
     "reviewer_time_per_tc_seconds_avg": 27.6
   }
   ```

---

## 8. *자동 승인 습관* 방지 안전망

4인 토론 리스크: reviewer가 *습관적으로 그냥 통과시킬* 가능성. 방지책:

| 안전망 | 작동 방식 |
|---|---|
| 무작위 sample 강제 검토 | 회색 행 중 5% 무작위 sample은 *반드시 빨강 처리 흐름*으로 처리 (도구가 강제) |
| FAIL 비율 모니터링 | 자동실행 후 FAIL이 5% 이상이면 *해당 TC들이 Gate를 통과한 이유*를 시험원이 회고 |
| 결함 탈출 추적 | 시험 종료 후 *실제 운영에서 발견된 결함*이 어느 Layer를 통과했는지 역추적 (Phase 2) |
| Reviewer time 통계 | TC당 평균 시간이 5초 미만이면 *기계적 승인 가능성 경고* |

---

## 9. *처음 reviewer*를 위한 핵심 5가지

사용자가 *처음으로* reviewer 사이클을 돌릴 때 잊지 말 5가지:

1. **빨강·노랑 행부터 본다.** 회색은 마지막.
2. **source_quote는 *반드시* 매뉴얼에서 직접 찾아본다.** AI 인용을 그대로 믿지 말 것.
3. **모르겠으면 `pending`.** 추측으로 `approved` 하지 말 것.
4. **45분마다 휴식.** 집중력 저하 = false approve.
5. **`edited`·`rejected`에는 *반드시 한 줄 사유 기록*.** RAG의 피드백 데이터.

# Prompt 설계 — E1·E2 강제 (구 Prompt Augmentation, D25 재해석)

**작성일:** 2026-05-18 (D25 pivot 후 위상 재해석)
**근거 문서:** `00-existing-method-interview.md`, `00b-gap-analysis.md`
**대상:** Phase 1의 E1·E2 (AWT의 Stage 2 핵심 기능). E3·E4·E5는 후속 문서.

> **D25 후 위상 변경:** 본 문서는 원래 *기존 skill의 prompt에 추가할 augmentation*을 다뤘으나, AWT가 standalone이 된 후 (D25) 본 문서의 내용은 **AWT의 본 prompt 설계**가 된다. 파일명·구조는 유지하되, "augmentation" 표현은 *AWT가 자체적으로 강제하는 출력 사양*으로 해석.
>
> **§5 (Selective Rerun)의 의미 변화:** 기존엔 외부 skill의 재시험 메커니즘을 활용한다고 했으나, D25 후 AWT가 *자체적으로* Gate 통과 TC만 Stage 5(자동 실행)로 보내는 내부 흐름으로 자연 구현.

---

## 1. 목적과 범위

| 강화 | 해결하는 사용자 약점 | 도입 방식 |
|---|---|---|
| **E1: source_quote 강제** | "TC를 믿어야 하는지 모르겠다" — 신뢰 불확실성 | Pre-prompt + Post 검증 (grep loop) |
| **E2: TC 설계 기법 강제** | "CRUD 위주로 한 것 같은데 그 외 기능도 제대로?" — 커버리지 불확실성 | Pre-prompt + Post 분포 검증 |

본 문서는 prompt의 **실제 사용 가능한 템플릿**과 검증 자동화 절차까지 포함한다 (지침 1: 설계 단계에서 모호함 제거).

---

## 2. 적용 시점

```
[사용자가 시험 시작]
    ↓
[AWT: Pre-prompt 조립]           ← §3 (E1+E2 강제 문구 + 기능리스트 + 설계기법 명세)
    ↓
[기존 skill: TC 생성 단계 호출]
    ↓
[기존 skill: Excel TC 산출]
    ↓
[AWT: Post 검증 — source_quote grep + 기법 분포 검증]   ← §4
    ↓
   ┌─ 통과: → Reviewer Gate (E5)
   └─ 미통과: 재생성 요청 prompt 자동 조립 → 재호출 (재시도 N회)
```

---

## 3. Pre-prompt 설계 (조립 규칙)

### 3.1. 기본 시스템 메시지 강화

기존 skill의 system prompt에 *추가*하는 문구. 기존 prompt를 *덮어쓰지 않고* append/prepend로 결합.

```text
[AWT 강화 지시 — 본 지시는 기존 시험 절차에 *추가*된다. 기존 지시와 충돌 시 본 지시를 우선한다.]

1. 모든 TC는 반드시 다음 7개 필드를 *Excel 컬럼*으로 출력한다:
   - tc_id              : TC-XXX-YYY 형식. XXX는 기능리스트 최하위 분류 일련번호. YYY는 동일 기능 내 변형 번호.
   - requirement_id     : 기능리스트의 해당 행 식별자 (대분류>중분류>소분류 경로 그대로)
   - design_technique   : 적용한 설계 기법 — happy_path / equivalence / boundary / negative_basic / negative_deep / state_transition / cross_feature 중 하나
   - precondition       : 사전 조건
   - steps              : 실행 단계
   - expected           : 기대 결과
   - source_quote       : 매뉴얼 또는 기능리스트의 *원문 그대로 발췌*. 발췌 위치 명시(예: "manual.pdf p.12 §3.2 '비밀번호는 8자 이상…'"). 추론 기반이면 "INFERRED: <근거 한 줄>"로 표시.

2. source_quote 규칙:
   - 발췌는 매뉴얼·기능리스트 안에 *문자열 그대로* 존재해야 한다. 글자 한 자라도 다르면 안 된다.
   - 추론 기반(INFERRED)은 5% 이하로 유지. 부득이한 경우만 사용.
   - 동일 source_quote가 여러 TC를 정당화하면 그대로 반복 인용해도 무방.

3. 설계 기법 배분 — 각 최하위 기능마다 다음 비율을 목표로 한다:
   - happy_path: 1개 이상 (필수)
   - equivalence: 입력 도메인이 2개 이상이면 도메인별 1개씩
   - boundary: 수치/문자열 길이 제약이 있으면 경계 양쪽 (포함/미포함)
   - negative_basic: 잘못된 입력에 대한 에러 1개 이상
   - negative_deep: 에러 메시지의 위치·한국어·이해성·보안노출 4중 확인 1개 이상
   - state_transition: 다단계 워크플로면 중간 step 누락 시 1개
   - cross_feature: 기능리스트에서 의미 있게 연관된 다른 기능과의 조합 1개 이상
   - 적용 불가능한 기법은 design_technique 컬럼에 그대로 두지 않고, TC 자체를 만들지 않는다(빈 줄 금지).

4. TC 수 가이드 (참고치, 강제는 아님):
   - 단순 CRUD 기능: 3~8개
   - 입력 검증 포함 기능: 8~20개
   - 다단계 워크플로: 15~40개
   - 결과적으로 1제품당 약 200~500개 (기존의 100~200개에서 확장된다는 점 인지)

5. 출력 형식:
   - 기존 skill이 사용하는 Excel 양식의 컬럼을 *그대로 유지*하되, 위 7개 필드가 누락 없이 모두 채워져야 한다.
   - 컬럼 이름이 충돌하는 경우, AWT 컬럼은 접미사 `_awt`를 붙인다 (예: tc_id_awt).
```

### 3.2. 사용자 메시지 wrapper

기존 skill 호출 시 사용자 메시지 앞에 다음을 자동 prepend:

```text
[입력 자료]
- 매뉴얼: {매뉴얼 파일 목록과 페이지 수}
- 기능리스트: {Excel 경로}, 최하위 분류 N건
- 결함 샘플: {품질특성별 샘플 문서 목록}
- 대상 URL: {URL}

[강제 출력]
위 시스템 지시의 7개 필드를 반드시 모두 채운 Excel을 산출하라.
산출 후 다음 self-check를 *내부적으로* 수행하고, 통과한 결과만 제출:
  C1. 모든 행에 source_quote가 있는가 (INFERRED 포함)
  C2. INFERRED 비율이 5% 이하인가
  C3. 최하위 기능별로 happy_path가 최소 1개 있는가
  C4. design_technique 분포가 happy_path 비율 50% 이하인가 (CRUD 편향 방지)
self-check 미통과 시 결과를 *제출하지 말고* 부족 항목을 수정해서 재산출하라.
```

---

## 4. Post 검증 자동화

기존 skill이 산출한 Excel을 AWT가 후처리해 5단계 검증한다:

| # | 검증 | 자동화 방법 | 실패 시 동작 |
|---|---|---|---|
| V1 | 7개 필수 컬럼 존재 | pandas 컬럼 체크 | 재호출 (기능 부족) |
| V2 | source_quote의 매뉴얼 grep 일치 | PDF/Word 텍스트 추출 후 substring match (공백·줄바꿈 정규화) | 해당 행 `INFERRED — verification failed`로 마킹 + Reviewer Gate 우선 검토 표시 |
| V3 | INFERRED 비율 ≤ 5% | 단순 카운트 | 5~15%는 경고, 15% 초과는 재호출 |
| V4 | design_technique 분포 — happy_path 비율 ≤ 50% | 카운트 | 초과 시 "기법 다양화 요구" prompt 재호출 |
| V5 | 기능리스트 최하위 분류별 TC 누락 | 기능 ID set 비교 | 누락 기능 명시한 prompt 재호출 |

**재호출 prompt 패턴:**

```text
[AWT 자동 보강 — 재호출]
직전 산출에서 다음 항목이 미충족이다:
  - V2 실패: TC-001-003, TC-001-007의 source_quote가 매뉴얼에 존재하지 않음. → 매뉴얼에서 원문 찾아 다시 인용하거나 INFERRED로 명시 마킹.
  - V5 실패: 기능 '회원가입 > 비밀번호 정책 > 변경 주기'에 대한 TC 없음. → 해당 기능에 happy_path + boundary + negative_deep 최소 3개 생성.
직전 산출의 다른 부분은 *유지*하고, 위 항목만 보강한 결과를 산출하라.
```

**재호출 횟수 제한:** 동일 사이클에서 최대 3회. 3회 초과 시 INFERRED 또는 누락 그대로 *Reviewer Gate 강제 검토 대상*으로 전달.

---

## 5. Selective Rerun과의 통합 (D23)

기존 skill에는 *"기존 TC 결과를 첨부해 재시험"* 메커니즘이 있다. AWT는 이를 다음 시점에 활용:

### 5.1. Gate 통과 TC만 실행

Reviewer Gate에서 `review_status=approved` 또는 `edited`인 TC만 추출 → 기존 skill의 재시험 입력으로 전달:

```text
[재시험 입력]
- 첨부: 승인·수정된 TC 시트 (review_status가 approved 또는 edited인 행만)
- 지시: 위 TC들의 steps를 실제 브라우저에서 실행하고, 실행 결과를 expected와 비교해 result + failure_reason 컬럼을 채워라.
- 추가: 새 TC를 *만들지 마라*. 입력된 TC만 실행하라.
```

### 5.2. 검토 결과 반영 후 부분 재실행

자동실행 후 추가 보완할 TC가 생겼을 때:

```text
[부분 재실행 입력]
- 첨부: TC 시트 (rerun_flag=true인 행만)
- 지시: 해당 TC만 다시 실행. 다른 TC의 기존 결과는 유지.
```

> **검증 필요 (Q-INT-5):** 기존 skill이 이 패턴을 그대로 받아들이는지 PoC로 실증. 안 된다면 prompt 표현을 조정하거나 옵션 (b)·(c)로 fallback.

---

## 6. 강화의 토글·관측

### 6.1. 토글

AWT의 모든 augmentation은 *토글 가능*해야 한다. 시험원이 기존 동작과 비교 시험할 수 있어야 함.

- 환경 변수 또는 설정 파일: `AWT_E1=on/off`, `AWT_E2=on/off`, `AWT_GATE=on/off`
- 기본값: 모두 `on`
- 토글 off 시 → AWT는 prompt를 수정하지 않고 그대로 pass-through

### 6.2. 관측 지표 (메타 측정 — Phase 2의 P8 전조)

AWT는 매 시험마다 다음을 기록한다 (`data/metrics/<product>/<date>.json`):

```json
{
  "product_id": "PRD-2026-0518-01",
  "tc_count": 423,
  "design_technique_distribution": {
    "happy_path": 152,
    "equivalence": 78,
    "boundary": 64,
    "negative_basic": 51,
    "negative_deep": 27,
    "state_transition": 33,
    "cross_feature": 18
  },
  "source_quote_inferred_ratio": 0.034,
  "v1_v5_retry_counts": [0, 2, 0, 1, 0],
  "gate_status": {
    "approved": 380,
    "edited": 31,
    "rejected": 12
  },
  "reviewer_time_minutes": 142,
  "reviewer_time_per_tc_seconds_avg": 20.1
}
```

이 데이터가 누적되면:
- AWT prompt 튜닝의 객관 근거 (어느 V가 자주 실패하는가)
- Reviewer 시간 budget 검증 (D20 30s~2min 실현 여부)
- 향후 Phase 2 mutation score 도입 시 baseline

---

## 7. 미해결 결정 (이 문서 작성 후 추가로 결정 필요)

| ID | 질문 | 영향 |
|---|---|---|
| Q-PA-1 | source_quote grep 검증의 fuzzy 허용 범위 — 공백·줄바꿈은 정규화하나, 한자 ↔ 한글, 띄어쓰기 오류는 어디까지? | V2 false reject 비율 |
| Q-PA-2 | INFERRED 5% 상한이 적정한가 — 실제 운영 데이터로 조정해야 | 재호출 빈도 |
| Q-PA-3 | 재호출 3회 상한이 적정한가 | 비용 + 완전성 트레이드오프 |
| Q-PA-4 | AWT 강화 prompt가 기존 skill prompt와 *충돌*할 가능성 — 기존 skill에 들어있는 지시문을 모르면 잠재 충돌 검증 불가 | 사용자가 기존 skill prompt를 부분 공유 가능한가? |
| Q-PA-5 | Excel 컬럼 추가 시 기존 skill이 *추가 컬럼을 무시*하는지, *에러를 내는지* — PoC 필요 | 통합 가능성 |

이 미해결들은 **PoC 시점 (Phase 1.0 — Q-INT-5 검증)에 함께 실증**한다.

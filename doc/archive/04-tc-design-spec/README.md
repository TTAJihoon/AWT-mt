# 04-tc-design-spec/ — TC 산출물 사양 + 품질 메트릭

AI가 생성하는 TC 산출물의 **형식적 사양**과, 그 TC 자체의 품질을 측정하는 **메타 메트릭**.

이 폴더의 사양이 강제되어야 **시험원 reviewer가 신뢰하고 책임질 수 있는 산출물**이 된다 (4인 토론 원칙 P1~P3, D6 신뢰 프레임).

> **TC ID 체계 (D9, D17~D19):**
> - 형식: `TC-XXX-YYY` (총 3자리 + 3자리 고정 자릿수)
> - **XXX**: 기능 분류표의 **최하위(leaf) 분류** 일련번호. 소분류가 있으면 소분류, 없으면 그 기능의 최하위 단계. 1번부터 제품 전체에 걸쳐 일련 부여.
> - **YYY**: 동일 leaf 기능 내 TC 변형 일련번호 (정상/예외/경계/시나리오 등). 999까지 (초과 시 설계 재검토 신호).
> - 최하위가 아닌 상위 분류(대·중)는 ID에 표기하지 않음. 필요 시 metadata 필드에만 기록.
> - Cross-feature 시나리오 TC도 별도 prefix 없이, 시나리오의 *주된 기능*에 귀속해 같은 형식 사용.
>
> **TC 작성 양식 (D10):** 시험소 표준 layout이 사전 제공되며, AI는 해당 양식 외 형식으로 출력하지 않는다.

## 파일

- `01-tc-schema.md` — TC의 정형 스키마: `{requirement_id, preconditions, steps, assertions, source_quote, oracle, confidence}` 등
- `02-traceability.md` — 요구사항 ↔ TC ↔ 실행결과 traceability matrix 규격
- `03-oracle-strategy.md` — PASS/FAIL 판정 근거 체계: 명시적 oracle / 메타모픽 / 차분 / 휴리스틱 등
- `04-confidence-score.md` — AI 결과 신뢰도 산정 공식 — 입력 단서 강도, oracle 명료성, 실행 안정성 등 가중
- `05-coverage-metrics.md` — 3계층 커버리지 측정 방법 (요구사항/입력도메인/시나리오)
- `06-mutation-score.md` — TC 강도 측정 — mutation testing 도입 방법
- `07-feedback-metrics.md` — AI TC acceptance / augmentation / human-added rate, 결함의 layer 귀속 추적

## 핵심 강제

> **모든 TC는 source_quote 없이는 시험원 reviewer의 자동 승인을 받을 수 없다.**

source_quote는 매뉴얼/기능리스트의 원문 그대로의 발췌여야 하며, AI가 *추론한* 거동은 source_quote 자리에 `INFERRED — needs human approval`로 표시되어 Layer 2 검토 대상으로 즉시 분류된다. (D6에 따라 외부 audit 통과를 위한 강제가 아닌, 내부 reviewer의 검증 시간 단축 + 환각 차단 수단)

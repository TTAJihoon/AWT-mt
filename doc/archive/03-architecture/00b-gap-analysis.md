# AWT Design Targets — 8대 원칙 × 구현 매트릭스 (재해석, D25)

**일자:** 2026-05-18 작성, 2026-05-19 D25 pivot 후 재해석
**기반:** `00-existing-method-interview.md` + `doc/01-theory/01-four-person-debate.md` 8대 원칙

> **D25 pivot 후의 재해석:** 본 문서는 원래 *기존 skill의 강화 layer*를 위한 gap analysis였다. AWT가 **standalone**으로 결정된 후 (D25), 본 문서의 매트릭스는 *AWT가 처음부터 충족해야 할 design target*으로 재해석된다.
>
> **변경:** "현행 상태 vs 8대 원칙" → "AWT가 구현해야 할 항목". 매트릭스 내용은 거의 동일하나 *의미는 다름*.

---

## 매트릭스 — AWT의 Design Targets

| # | AWT 원칙 | 구현 책임 (AWT 내부) | 우선순위 | 출처 |
|---|---|---|---|---|
| **P1** | AI TC는 동결 산출물 | Stage별 산출을 `data/runs/<run-id>/`에 불변 보관. seed·prompt·모델 버전 메타데이터 동반 | P2 (보통) | `01-high-level.md` §6 |
| **P2** | requirement_id + source_quote | **Stage 2 E1**의 핵심. prompt에 강제 + Stage 3 V2에서 grep 검증 + 미통과 INFERRED 마킹 | **P1-1 (최우선)** | `05-prompt-augmentation.md` §3.1 |
| **P3** | 3계층 커버리지 | **Stage 2 E2**의 핵심. 7가지 설계 기법 분산 강제 + Stage 3 V4에서 분포 검증 | **P1-2 (최우선)** | `05-prompt-augmentation.md` §3.1 |
| **P4** | 인간 = curation + 심층 + 책임 | **Stage 4 Gate** (`05-curation-workflow.md`). Excel 색상·정렬·결재 컬럼 | **P1-4** | `02-iso-25023-mapping/05-curation-workflow.md` |
| **P5** | Confidence score | **Stage 2·6의 E4**. gen_confidence + exec_confidence 자동 산정. Stage 4 Gate 정렬 기준 | **P1-3 (최우선)** | TC 스키마 G3 |
| **P6** | 결함이력 RAG | Phase 1은 *결함 샘플 prompt 컨텍스트 주입*만. Phase 2에서 vector DB | P1-5 (Phase 1 시드) | `03-data-flow.md` §5 |
| **P7** | Multi-agent 상호 검증 | Phase 2 본격 (생성 agent + oracle agent 분리). Phase 1은 단일 agent | P2 | Phase 2 영역 |
| **P8** | TC 메타 측정 | Phase 1 부분 (acceptance/augmentation rate 자동 기록). 25023 메트릭 %는 Phase 2 | P2 | `04-tc-design-spec/06-mutation-score.md` 후속 |

---

## D25 이전 "보존해야 할 현행 자산" 재해석

| # | 자산 | D25 이전 의미 | D25 이후 의미 |
|---|---|---|---|
| AS1 | Folder-based 입력 파이프라인 | 기존 skill 보존 | **AWT가 동일 방식 채택** (시험원 친숙 형태 유지) |
| AS2 | Excel 기반 산출 양식 | 기존 skill 형식 보존 | **AWT가 시험소 표준 양식 그대로 채택** |
| AS3 | End-to-end 자동 실행 (클릭/입력/판정) | 기존 skill 유지 | **AWT가 Playwright MCP로 자체 구현** (D24) |
| AS4 | 품질특성별 결함 샘플 문서 | 기존 운영 인풋 | **AWT의 Stage 1 입력 + Phase 2 RAG seed** |
| AS5 | 사전/기대/결과 3컬럼 TC 형식 | 기존 컬럼 보존 | **AWT가 시험소 표준 양식 + AWT 추가 컬럼**으로 통합 |

> **원칙: 시험원 친숙성을 깨지 않는다.** AWT는 *입력/출력 형식*에서 시험소 표준을 그대로 따른다. 차별화는 *내부 처리의 신뢰성*에 있다.

---

## Phase 1의 5대 핵심 기능 (재해석 — E1~E5는 AWT의 *자체 기능*)

D30: 기존의 "강화 5종"이 *AWT의 핵심 기능 5종*으로 재해석.

### E1. source_quote 강제 (P2 구현)
- Stage 2 prompt에 `{requirement_id, source_quote}` 필수 출력 강제
- Stage 3 V2에서 grep 검증 → 미통과 INFERRED 마킹 + Reviewer Gate 즉시 우선
- **효과:** 시험원이 "TC를 믿어야 하나" 불안을 source_quote로 5초 검증

### E2. TC 설계 기법 prompt 강제 (P3 구현)
- 단순 "정상/예외" → 7가지 기법 명시:
  - happy_path, equivalence, boundary, negative_basic, negative_deep, state_transition, cross_feature
- 기능별 최소 TC 수 강제
- **효과:** CRUD 편향 해소, 100~200개 → 200~500개 확장

### E3. Oracle 근거 + 실패 원인 자동 기록 (P5 일부)
- Stage 6에서 PASS/FAIL과 함께:
  - `oracle_reason`: 기대값 근거
  - `failure_reason`: 실제출력 / 차이 / 원인후보 / 재시도이력 (4축)
- **효과:** "왜 실패했는지 직접 확인" 부담 제거

### E4. Confidence score (P5 본격)
- `gen_confidence`: source_quote 명료성·기능 명세 강도
- `exec_confidence`: 실행 안정성·재시도·oracle 명료성
- Reviewer는 낮은 confidence부터 본다
- **효과:** D20 (30s~2min budget) 실현

### E5. Reviewer Gate 워크플로 (P4 구현)
- Excel + 색상 + confidence 정렬 + 4상태 (approved/edited/rejected/pending)
- **자동실행 이전에 위치 (D22)** — 잘못된 TC가 실행 전 차단
- **효과:** 시험원이 *처음 reviewer 역할*을 무리 없이 수행

---

## Phase별 정리

### Phase 1 — 단일 제품 정확성 (3~6개월)

AWT가 1제품을 *정확히 처리*하는 게 1차 목표 (D12). 5대 핵심 기능 E1~E5 도입.

### Phase 2 — 신뢰성 심화 (6~18개월)

- Multi-agent 분업 (P7)
- TC 메타 측정 자동 (P8)
- 25023 메트릭 % 자동 계산 (D21 해소)
- RAG 본격화 (P6 완성, D16 익명화 자동/수동 분리)
- 분리 배포 sub-skill 외부 공개

### Phase 3 — 확장 (18개월+)

- 25059 AI 제품 한정 적용 (D15)
- 제품군별 specialized agent (D7)
- 동시 시험 10+ 병렬 (D12 이후)
- 결함 재현 자동화 (4인 토론 R5)

---

## D25 Pivot이 제거한 위험·미지수

| 항목 | D25 이전 | D25 이후 |
|---|---|---|
| Q-INT-5 (skill 분리 호출) | 핵심 미지수 | **N/A — 분리 자체 불필요** |
| Q-PA-4 (prompt 충돌) | 미지수 | **N/A — AWT prompt만 존재** |
| Q-PA-5 (Excel 컬럼 수용성) | 미지수 | **N/A — AWT가 정의** |
| 외부 skill 변경 위험 | 항상 존재 | **N/A — 의존 없음** |
| 다른 엔지니어 협조 필요 | 있음 | **N/A — 사용자 단독 가능** |

→ PoC가 *크게 단순화* (`06-poc-validation-plan.md` 재작성 — PoC-α·β·γ).

---

## 강화의 *물리적 형태* (D25 후)

이전: "기존 skill 호출 전후에 끼어드는 wrapper". **삭제됨.**

현재: AWT는 자체 Stage 1~7을 순차 실행하는 standalone skill. 외부 호출 없음. 호출 흐름은 `01-high-level.md` §1 참조.

---

## 미해결 (재정리)

| ID | 항목 | D25 이후 상태 |
|---|---|---|
| ~~Q-INT-5~~ | ~~skill 분리 호출 가능성~~ | **해소 (D26)** |
| Q-PA-1 | source_quote grep fuzzy 허용 범위 | **유효** — PoC-α에서 검증 |
| Q-PA-2 | INFERRED 5% 상한 적정성 | **유효** — PoC-α에서 검증 |
| Q-PA-3 | 재호출 3회 상한 | **유효** — PoC-α에서 검증 |
| ~~Q-PA-4~~ | ~~prompt 충돌~~ | **해소 (D27)** |
| ~~Q-PA-5~~ | ~~Excel 컬럼 수용성~~ | **해소 (D28)** |
| Q-PROD-1 | PoC 대상 게시판 구체 후보 | **신규** — PoC 진입 전 결정 |

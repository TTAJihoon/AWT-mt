# 04. Stage 0~7 통합 + 점진 도입 로드맵

자산을 *기존 7단계 파이프라인에 어떻게 끼워 넣을 것인가* 와 *Phase별 무엇을 먼저 도입할 것인가*.

## 1. Stage 0~7 통합 매핑

### 1.1 현행 Stage 흐름

```text
Stage 0: DOM scan → spec 초안 (LLM)         [DOM_SPEC]
Stage 1: 파일 파싱·정규화
Stage 2: per-leaf TC 설계 (LLM)             [TC_DESIGN]
Stage 3: V1~V5 검증 + 3회 재생성              [TC_REGEN]
Stage 4: Reviewer Gate (사람)
Stage 5: Playwright 자동 실행
Stage 6: 실패 원인 4축 분석 (LLM)           [FAILURE_ANALYSIS]
Stage 7: Excel 보고서
```

### 1.2 자산 통합 후 Stage 흐름

```text
Stage 0: DOM scan → spec 초안 (LLM)         [DOM_SPEC]
         + lazy 다중 상태 탐색 (자산 #4)
         + ProjectState 초기화 (자산 #1)
         + productType 분류 (자산 #1)

Stage 1: 파일 파싱·정규화 (현행 유지)
         + 적용 가능 패턴·invariants·결함 RAG 검색
         + ProjectState에 적재

Stage 2: per-leaf TC 설계 (LLM)             [TC_DESIGN v2]
         입력 확장: invariants, similar_defects, applicable_patterns, equivalence_templates
                                              (자산 #2, #5, #5b)

Stage 2.5: cross-screen TC 설계 (LLM, 신규)  [CROSS_SCREEN_DESIGN]
           입력: 전체 leaf 요약 + cross-screen-invariants  (자산 #3)

Stage 3: V1~V5 + V6~V10 검증                 [TC_REGEN]
         V6: selector 안정성  (자산 #6)
         V7: TC 중복도 Jaccard  (자산 #7)
         V8: spec hallucination 검증  (자산 #2 의존)
         V9: TestPattern 적용 완전성  (자산 #5b)
         V10: negativeRequiredCount 충족  (자산 #5b)

Stage 4: Reviewer Gate
         + CoverageMatrix 빨간 칸 (미생성 패턴 + 사유)
         + spec hallucination 의심 플래그 (V8)
         + cosmetic 중복 플래그 (V7)

Stage 5: Playwright 자동 실행 (현행 유지)

Stage 6: 실패 원인 분석 (LLM)               [FAILURE_ANALYSIS v2]
         + 결함 분류 enum (selector_break / scenario_error / 
                          expected_error / true_defect / fictional_positive)
         + 진짜 결함 시 카탈로그 적재 트리거  (자산 #5)

Stage 7: 보고서
         + CoverageMatrix 포함
         + 자동화 영역 / 보조 영역 / 영역 밖 3구분 명시
```

## 2. 신규 Contract / 모듈

### 2.1 신규 Contract

| Contract | 시점 | 용도 |
|---|---|---|
| `CROSS_SCREEN_DESIGN` | Stage 2.5 | cross-screen TC 생성 |
| `PATTERN_EXTRACT` | Stage 7 후 | 완성 TC에서 invariant 추출 (사후) |
| `DEFECT_ANONYMIZE` | 카탈로그 적재 시 | D4/D13/D16 정책 자동화 |

### 2.2 신규 모듈 (app/ 디렉터리 권고)

```text
app/
├── state/
│   └── project_state.py          # 자산 #1
├── assets/
│   ├── invariants_loader.py      # 자산 #2, #3
│   ├── pattern_library.py        # 자산 #5b
│   └── equivalence_templates.py  # 자산 #5b
├── rag/
│   ├── defect_retrieval.py       # 자산 #5 검색
│   ├── defect_indexer.py         # 자산 #5 임베딩
│   └── defect_anonymizer.py      # D4/D13/D16
├── validation/
│   ├── v6_selector_stability.py
│   ├── v7_jaccard_duplicate.py
│   ├── v8_hallucination.py
│   ├── v9_pattern_coverage.py
│   └── v10_negative_count.py
└── orchestrator/
    └── (현행 + 신규 Stage 2.5 추가)
```

### 2.3 신규 데이터 디렉터리

```text
data/
├── assets/                       # 영속 자산 (자산 #1 절충안)
│   ├── test-patterns/
│   ├── equivalence-templates/
│   ├── domain-invariants/
│   ├── cross-screen-invariants/
│   └── defect-catalog/
├── projects/
│   └── PRJ-2025-XXX/
│       ├── project-state.json
│       ├── page-states.json
│       ├── coverage-matrix.json
│       └── (기존 immutable run artifact)
└── poc/                          # 현행 유지
    └── 2026-05-19/output/
```

## 3. Phase 0~4 로드맵 (Stage와의 매핑)

### Phase 0 (Month 1-2): 스키마 동결

**구현**:
- `data/assets/` 디렉터리 구조 생성
- 6개 자산 스키마 *형식만* 정의 (내용 비어있음)
- ProjectState 영속 모듈 (자산 #1) 골격
- Stage 0~7 파이프라인에 *자산 주입 인터페이스* 만 추가

**완료 조건**:
- 자산 비어있어도 기존 PoC 재현 가능
- 자산 채워지면 자동으로 LLM 입력에 주입됨

**가치**: 0 (가시적 효과 없음, 인프라 단계)

### Phase 1 (Month 3-6): 1순위 3개 자산 활성화

**구현 (우선순위 순)**:

1. **자산 #6 selector 안정성 점수 (V6)** — 1주 작업, 즉각적 가치
   - PoC-γ 9 fail 중 selector 깨짐 분석
   - `app/validation/v6_selector_stability.py` 구현
   - `tc_design.md` 출력 검증에 V6 추가

2. **자산 #5 결함 카탈로그 적재 UI** — 2주 작업
   - 스키마 확정
   - 적재 UI (PySide6 폼)
   - `learning.patternProposal` 필드 작성 의무화
   - **RAG는 아직 안 함** (데이터 부족)

3. **자산 #2 domain-invariants.yaml 채널** — 1개월 작업
   - yaml 형식 확정
   - `tc_design.md` 입력 확장
   - V8 (spec hallucination 검증) 추가
   - 첫 invariants 작성 (PoC-α 데이터에서 추출)

**완료 조건**:
- 신규 시험 1건 진행 시 INFERRED 비율 30% 미만
- source_quote 인용률 75% 이상
- selector 안정성 검증 V6 작동
- 결함 카탈로그 30~50건 적재

**가치**: 결함 매핑률 12~15% 도달 추정

### Phase 2 (Month 7-12): 2순위 자산 활성화

**구현**:

4. **자산 #1 ProjectState 영속 (절충안)** — Phase 1 종료 후
   - 패턴·invariants·결함 카탈로그를 *조직 자산* 으로 영속화 시작
   - schemaVersion 정책 (D38 stateless 유지)

5. **자산 #3 cross-screen-invariants** — 1개월 작업
   - Stage 2.5 `CROSS_SCREEN_DESIGN` Contract 추가
   - 첫 cross-screen invariants 작성

6. **자산 #5b TestPattern 라이브러리** — Phase 2 진행 중 누적
   - 결함 카탈로그의 patternProposal 환류
   - candidate → preliminary → active 생애주기
   - V9, V10 활성화

7. **자산 #4 PageState 그래프** — 동적 UI 제품 도입 시
   - lazy 다중 상태 탐색
   - elementRegistry 다중 selector 보존

**완료 조건**:
- 1개 제품유형의 TestPattern 30~50개 (active 상태)
- domain-invariants 20~40개
- 결함 카탈로그 300~500건
- 자동화 TC 결함 매핑률 15~18%

### Phase 3 (Year 2): RAG 활성화

**구현**:

8. **자산 #5 RAG 활성화** — 결함 카탈로그 ≥ 500건 시점
   - 벡터 임베딩 인덱스 구축
   - `tc_design.md` 입력에 `similar_past_defects` RAG 결과 주입
   - 유사도 임계 튜닝

9. **자산 #7 TC 중복도 검사 (V7)** — TC 수 증가 후
   - LLM 보조 invariant 추출
   - Jaccard 알고리즘 적용

**완료 조건**:
- RAG 검색 적합도 60% 이상
- 자동화 TC 결함 매핑률 18~21%

### Phase 4 (Year 2.5+): 지속 확장

- 신규 제품유형 도입 = 2~3 프로젝트 Shadow Mode 후 자동화 편입
- 이미지(비전) 휴리스틱 첨부 — 동적 UI 제품
- 패턴 archive 정책 작동 시작

## 4. 우선순위 결정의 ROI 근거

```text
자산 #6 (selector 안정성)
  구축: 1주
  효과: 9 fail 중 절반 이상 사전 차단 추정
  ROI: 최고

자산 #5 (결함 카탈로그 적재만)
  구축: 2주
  효과: Phase 1엔 직접 효과 작지만, Phase 2~3의 모든 효과의 *전제*
  ROI: 장기 최고

자산 #2 (domain-invariants)
  구축: 1개월
  효과: INFERRED 41.5% → 30% 미만, source_quote 58.5% → 75%
  ROI: PoC 신호의 본질적 해법
```

본 분석 권고 = **#6 → #5(적재) → #2 → 나머지** 순.

## 5. 기존 PoC-α/β/γ 결과의 재활용

### 5.1 PoC-α의 41 TC를 *패턴 추출 입력* 으로

```text
41 TC를 LLM에 전체 입력 (사후 분석)
→ 추출:
  - 등가류 후보 5~8개
  - cross-screen invariant 후보 2~3개
  - 일반화 가능한 invariant 5~10개

→ Phase 1의 *첫 자산 시드* 로 사용
```

### 5.2 PoC-γ의 5개 결함을 *카탈로그 시드* 로

```text
기존 3 + 신규 2 = 5개 결함
→ 결함 카탈로그 스키마 첫 5건 적재
→ 각각 patternProposal 작성
→ Phase 1 시작 시 *비어있지 않은 카탈로그* 보유
```

### 5.3 PoC-α의 INFERRED 17개를 *invariants 추출 입력* 으로

```text
17개 INFERRED expected_output → LLM 분석
→ "이 추론들이 실제 정책이라면 어떤 invariant?" 질문
→ 시험설계 리드 검토 후 yaml 진입
→ domain-invariants.yaml 첫 5~8개 항목 확보
```

## 6. AWT-claude의 미해결 Q와의 연결

본 권고와 AWT-claude `doc/06-decisions.md` 의 미해결 Q를 연결:

| AWT-claude Q | 본 분석 권고 | 답 방향 |
|---|---|---|
| Q-PA-1: source_quote fuzzy tolerance | 자산 #2 invariants | tolerance 조정 대신 *quote 소스 확장* |
| Q-PA-2: INFERRED threshold tuning | 자산 #2 invariants | threshold 완화 대신 *INFERRED 자체 감소* |
| Q-PA-3: Retry limits | 자산 #4 (PageState) + #6 (selector) | 재시도 원인 사전 차단 |
| Q-PA-4: API backoff policy | (본 분석 범위 외) | — |
| Q-MX-1~4: 25023/25051/25059 매핑 | 자산 #5 patternProposal | 결함→매핑 자동 후보 추출 |
| Q-SCH-1: precondition 정규화 | 자산 #5b TestPattern | preconditionTemplate 표준화 |
| Q-SCH-2: steps DSL | (본 분석 범위 외) | — |
| Q-SCH-3: failure_reason 분해 | Stage 6 enum 분류 | 본 제안 §1.2 Stage 6 확장 |
| Q-SCH-4: 검수자 익명화 | 자산 #5 anonymize 정책 | DEFECT_ANONYMIZE Contract |
| Q14: Reviewer 권한·sign-off | (조직 정책 영역) | — |

본 권고를 채택하면 **Q-PA-1, Q-PA-2, Q-PA-3, Q-MX-1~4, Q-SCH-1, Q-SCH-3, Q-SCH-4** 의 답 방향이 자연스럽게 정해진다.

## 7. Phase 1 진입 전 *최소 추가 작업* (1주 시뮬레이션)

가장 빠르게 시작할 수 있는 *최소 변경* 시퀀스. 다른 자산 도입을 미루더라도 *이 1주만* 투자하면 본 권고의 *씨앗* 이 심어진다.

```text
Day 1: 자산 #5 결함 카탈로그 스키마 JSON 확정 + 디렉터리 생성
Day 2: PoC-γ의 5개 결함을 카탈로그에 적재 (patternProposal 채움)
Day 3: 자산 #6 selector 안정성 점수 알고리즘 초안 구현
Day 4: PoC-α의 41 TC 분석 → invariants 후보 5~8개 추출 → yaml 작성
Day 5: `tc_design.md` 입력에 invariants_yaml 필드 추가, 시험 호출
Day 6: V6 (selector), V8 (hallucination) 검증 로직 초안
Day 7: PoC 재실행 → INFERRED 비율·source_quote 인용률 변화 측정
```

1주 후 *측정 가능한 변화* 가 나오면 Phase 1 자원 투입 정당화 가능.

## 8. 다음 문서

자산화의 *이론적 근거* 와 *토큰 절감 계산*: → `05-foundational-frameworks.md`

본 권고가 *답하지 못하는* 결정사항: → `06-questions-to-resolve.md`

# 01. 현재 코드 직접 분석

분석 대상: `AWT-claude` 브랜치
분석 시점: 2026-05-19
분석 범위: `prompts/`(4 파일), `doc/`(6 파일), PoC 산출물 메타데이터
분석 방법: WebFetch + 문서 대조

## 1. 좋은 결정 (먼저)

비판으로 들어가기 전에, 현재 설계에서 *이미 옳은 방향* 으로 가고 있는 부분들. 본 제안은 이 위에 *덧붙이는* 권고지 *대체하는* 권고가 아니다.

### 1.1 ISO 표준의 정합 사용 (doc/04-iso-mapping.md)

- 25010을 *분류 어휘*, 25023을 *측정 메트릭* 으로 분리
- L1(전자동) / L2(보조+검토) / L3(인간 전용) 3계층
- L1의 4가지 자격 조건이 명시: 측정 객관성·oracle 도출 가능성·신뢰도 정량화·재현·추적

→ 본 분석의 *test oracle L0~L3 분류* 와 거의 동일. 본 제안 §5의 *프레임워크* 는 이미 부분 구현됨.

### 1.2 V1~V5 사후 검증 파이프라인 (doc/03-tc-schema.md)

```text
V1: 필수 필드 채움
V2: source_quote 명세 대조
V3: INFERRED 비율 제어
V4: 기법 다양성 (happy_path ≤ 50%)
V5: leaf 커버리지
→ 실패 시 tc_regen 3회
```

→ *LLM 출력 자유 통과* 가 아닌 *코드 검증 깔때기* 의 사상이 잘 구현됨. 본 제안의 *4-gate 검증* 사상과 부합.

### 1.3 4 LLM Contract 분리 (doc/02-llm-contracts.md)

- DOM_SPEC / TC_DESIGN / TC_REGEN / FAILURE_ANALYSIS
- 각각 token budget + JSON Schema + 캐싱(SHA-256)
- per-leaf 처리

→ *책임 분할된 호출 경계* 의 좋은 예. 본 제안 §5.1 Layer A 부분 구현.

### 1.4 source_quote + INFERRED 명시

`tc_design.md` 의 *직접 인용 vs INFERRED 접두사* 강제는 *spec hallucination 차단* 의 옳은 사상. 100% 작동은 못 했지만(58.5%) *시도 자체가 옳음*.

### 1.5 익명화 결함 데이터 정책 (D4/D13/D16)

L1~L2 자동 익명화, L3~L4 수동, L5 보류. *결함 카탈로그 RAG의 전제 조건* 이 정리됨.

→ 단, 정책만 있고 *적재·검색·환류 시스템* 은 없음 (§3.5 참조).

---

## 2. 분석 프레임

본 분석은 다음 9개 항목으로 AWT-claude 코드를 점검했다.

```text
A. 호출 구조 분할         (Decomposition)
B. 상태 보존 / 자산화      (State / Asset accumulation)
C. 사후 검증 깔때기        (Post-validation)
D. 실측 피드백 루프         (Probe loop)
E. 정책·invariant 채널     (Policy channel)
F. 등가류 깊이             (Equivalence-class depth)
G. cross-screen 깊이       (Cross-screen depth)
H. 결함 학습 환류           (Defect feedback loop)
I. selector 안정성         (Selector stability)
```

각 항목에서 *AWT-claude 현황 → 갭 → 영향* 을 정리.

---

## 3. 결정적 누락 (10가지)

### 3.1 자산 누적 / ProjectState 시스템

**AWT-claude 현황**:
- D38: stateless Anthropic API 명시
- 산출물은 *per-run immutable artifact* (감사용)
- 프로젝트 간 자산 누적 메커니즘 없음

**갭**:
- 41 TC PoC 산출물이 *다음 프로젝트에 어떻게 자산화되는지* 절차 없음
- D4/D13/D16의 *익명화 정책* 은 *RAG의 전제* 만 정한 것

**영향**: 100건의 시험을 해도 *100건 1회씩* 의 효과. 누적 곡선이 평평하게 유지.

**권고**: §4.1 *stateless API + stateful 자산 저장소* 절충안 채택. API 자체는 stateless 유지하되 *프로젝트 간 자산(패턴·결함 카탈로그·invariants)* 을 별도 저장소에 영속.

### 3.2 TestPattern 라이브러리 / 등가류 템플릿

**AWT-claude 현황**:
- `tc_design.md` 가 LLM에 *manual_excerpt + defect_patterns(500자)* 만 전달
- 등가류 분류는 *매 호출 LLM 자유 추론*

**갭**:
- 이메일·비밀번호·날짜·파일 등 표준 입력 유형마다 *매번 LLM이 등가류를 다시 enumerate*
- 결과적으로 INFERRED 비율 41.5% (PoC-α)
- equivalence-class inflation 가능성 높음

**영향**: 정밀한 음성 케이스 깊이 확보 불가. 7기법(equivalence/boundary/negative_*)이 *분류만 있고 내용은 LLM 추론*.

**권고**: `03-seven-design-assets.md` §2.1 등가류 템플릿 라이브러리. 입력 유형별 *결정론적* 등가류 + skip 조건.

### 3.3 domain-invariants 채널

**AWT-claude 현황**:
- 매뉴얼 발췌(1500자)만 LLM 입력
- *회사 정책·법적 요구사항·보안 정책* 의 별도 명시 채널 없음

**갭**:
- spec hallucination 차단이 *source_quote 강제* 한 가지 (58.5% 달성)
- 매뉴얼에 명시 안 된 정책이 *LLM 추론* 으로 채워지면 fictional positive 생성

**영향**: PoC-α의 *나머지 41.5% INFERRED 영역* 이 fictional이 될 수 있음. 시험성적서에 가짜 결함 보고 위험.

**권고**: `03-seven-design-assets.md` §2.2 domain-invariants.yaml 채널. `tc_design.md` 입력에 추가.

### 3.4 cross-screen invariants

**AWT-claude 현황**:
- 7기법 중 `cross_feature` 가 있지만 *한 호출 안에서* 처리
- per-leaf 처리(D39)가 *효율* 을 주는 대신 *cross-leaf invariant* 를 구조적으로 차단

**갭**:
- "등록 후 목록 반영", "변경 후 audit log 완전성", "권한 변경 후 즉시 적용" 같은 *화면 간 일관성* 검증 누락
- LLM이 한 leaf만 보면 화면 간 관계 추론 불가

**영향**: 시스템적으로 *모든 cross-screen 결함* 을 누락. 사람도 자주 빠뜨리는 영역이지만 자동화에서 *영원히* 빠뜨림.

**권고**: `03-seven-design-assets.md` §2.3. *별도 검증 단계* (Stage 2.5)로 cross-screen invariant TC 생성. per-leaf 처리는 유지.

### 3.5 결함 카탈로그 RAG 검색

**AWT-claude 현황**:
- `defect_patterns` 입력 필드가 *500자* 로 존재
- 어디서 어떻게 채워지는지 절차 없음
- 임베딩·검색 인프라 없음

**갭**:
- 500자 제한은 *카탈로그 RAG 결과 N건 주입* 운용에 부적합 (1건 요약도 안 됨)
- D4/D13/D16의 익명화 정책은 *RAG의 전제 조건* 만 정한 것

**영향**: LLM이 *교과서 결함* 만 만드는 한계 영원히 못 벗어남. 회사 누적 결함의 학습 효과 0.

**권고**: `03-seven-design-assets.md` §2.5 결함 카탈로그 + RAG. `tc_design.md` 의 `defect_patterns` 를 `similar_past_defects` (max 1500자) 로 확장.

### 3.6 selector 안정성 점수 / Probe Loop

**AWT-claude 현황**:
- Playwright는 Stage 0 (DOM scan) + Stage 5 (execution) 에만 사용
- TC 설계 단계의 *실측 검증* 없음

**갭**:
- 깨진 selector가 *실행 단계에서야* 발견됨
- tc_regen이 호출되어야 수정 → 재실행 사이클 비효율

**영향**: PoC-γ의 9/41 실패 중 selector 깨짐이 절반 이상으로 추정. 토큰·시간 낭비.

**권고**: `03-seven-design-assets.md` §2.6. V1~V5에 *V6 selector 안정성 점수* 추가. Low-stability selector 자동 거부.

### 3.7 PageState 그래프 / DOM 다중 상태

**AWT-claude 현황**:
- Stage 0의 DOM scan은 *한 시점의 DOM*
- 로그인 후·검색 후·모달 열림 등 *상태별 DOM* 누적 없음

**갭**:
- 동적 UI(모달, 다단계 form, 검색 결과)가 많은 제품일수록 leaf 누락 증가
- selector가 *"존재 안 함"* 으로 나와도 사실은 *"아직 안 렌더링됨"* 인 경우 구분 불가

**영향**: SPA·동적 UI 제품에서 TC 누락률 증가.

**권고**: `03-seven-design-assets.md` §2.4. Stage 0를 *다중 상태 탐색* 으로 확장. lazy 구축으로 비용 통제.

### 3.8 이미지(비전) 활용

**AWT-claude 현황**: 4개 contract 어디에도 이미지 입력 없음. DOM 텍스트만 사용.

**갭**:
- icon-only 버튼, canvas/svg, 시각적 그루핑이 다른 경우 → leaf 분류 누락
- ARIA label 없는 아이콘 영역 *영원히* 인지 불가

**영향**: 대시보드·시각화 중심 제품에서 큰 누락. 단, 일반 CRUD 제품엔 영향 작음.

**권고**: 의도적 단순화로 보임. Phase 1 이후 *선택적 첨부 휴리스틱* 으로 도입 (token 비용 통제).

### 3.9 TC 의존성 그래프

**AWT-claude 현황**:
- TC ID `TC-XXX-YYY` 형식만 있고 *전제 TC / 후속 TC* 의 명시적 의존 관계 없음
- `cross_feature` 기법은 *한 TC 안에서* 여러 기능을 묶음

**갭**:
- 회귀시험에서 의존 실패 시 후속 자동 skip 불가
- 실패 보고서가 *cascade noise* 로 가득

**영향**: PoC-γ의 9 fail이 *서로 독립적* 인지 *cascade* 인지 구분 불가.

**권고**: `03-seven-design-assets.md` §2.7. TC 스키마에 `preconditions.requires` / `postconditions.enables` 추가.

### 3.10 TC 중복도 자동 검사

**AWT-claude 현황**: V4(기법 분포)는 있지만 *TC 쌍의 invariant 집합 비교* 없음.

**갭**:
- *기법은 다른데 검증 invariant는 같은* cosmetic TC가 통과됨
- 검수자가 41개 모두 검토해야 함 (검수 피로 임계 도달)

**영향**: Phase 1 진입 후 *TC 수* 가 늘면 검수 피로 폭증.

**권고**: `03-seven-design-assets.md` §2.7. V7: TC 간 invariant Jaccard 중복도 > 0.7 시 cosmetic 의심 플래그.

---

## 4. 설계 철학의 분기점

본 분석과 AWT-claude가 *다른 방향* 으로 간 곳들. 어느 쪽이 맞는지는 회사 맥락이 결정.

### 4.1 stateless vs stateful

**AWT-claude**: D38 *완전 stateless*. 산출물은 immutable per-run.

**본 분석 권고**: *ProjectState 영속* 이 ★ 차별점.

**분기 이유 추정**: AWT-claude는 *재현성·감사 가능성* 을 우선. 본 분석은 *자산 누적* 을 우선.

**절충안**:

```text
LLM API 호출 자체     : stateless 유지 (D38 보존)
프로젝트 간 자산      : stateful 저장소
호출 시점에         : 자산을 *입력으로* 주입

→ API 측면에서는 stateless 원칙 깨지지 않음
→ 자산은 별도 영속 저장소 (file or DB)
→ 호출 입력에 *주입* 되어 LLM이 활용
```

→ 두 목표(재현성·자산화) 모두 달성 가능. *stateless 원칙* 의 정확한 정의가 *API 호출* 인지 *시스템 전체* 인지가 분기의 핵심.

### 4.2 per-leaf 호출 vs 책임 단위 호출

**AWT-claude**: leaf 1개 = LLM 1회 호출 (D39).

**본 분석**: 호출 분할은 *책임 단위* (제품분류 / 기능매핑 / 패턴적용 / assertion).

**분기**: AWT-claude는 *기능 단위*, 본 분석은 *추론 책임 단위*.

**평가**: per-leaf가 단순하고 좋은 선택. 단 leaf 안에서 *책임을 더 쪼갤* 여지가 있음 — *제품 유형 분류* 와 *기능 매핑* 은 leaf 호출 *밖* 으로 빼는 게 토큰 효율적. 부분 적용 권장.

### 4.3 INFERRED 임계 *완화* 결정

**AWT-claude**: PoC-α에서 INFERRED 41.5% 발생 → 임계를 30%로 *완화* 조정.

**본 분석**: *임계 완화는 spec hallucination을 정상으로 인정하는* 방향.

**위험**: 임계를 완화하는 방향은 *문제를 해결한 게 아니라 문제를 정상으로 인정한* 것.

**대안 방향**:

```text
현재 방향: INFERRED 41.5% 발생 → 임계 30%로 완화

권고 방향: INFERRED 41.5% 발생
  → invariants 채널 도입으로 *추론* 영역을 *참조* 영역으로 전환
  → INFERRED 비율이 자연스럽게 낮아짐
  → 임계는 *낮아짐* (예: 15%) 또는 *유지*
```

본 분석에서 *가장 위험한 신호* 로 식별. 다른 모든 권고에 우선하여 재검토 권장.

연관 미해결 질문: Q-PA-1 (source_quote fuzzy tolerance), Q-PA-2 (INFERRED threshold).

---

## 5. PoC 결과 신호 해석

### 5.1 신규 결함 매핑률 4.9%의 의미

```text
PoC-γ: 41 TC 실행, 5개 결함 발견 (기존 3 + 신규 2)
신규 결함 매핑률 ≈ 2/41 = 4.9%
(베이스라인 LLM 추정 11% 미달)

해석 후보:
1. 목업이 *과도하게 단순* (PoC-α에서 명시한 사전 주의사항)
2. 자산(패턴/카탈로그/invariants) 부재로 LLM 단독 성능 그대로
3. source_quote 58.5%는 *나머지 41.5%가 추론* → 추론 영역에서 spec hallucination 가능성
```

해석 1·2가 동시에 작동. 진짜 제품 시험 시 *결함 매핑률이 8~14%로 회복* 될 가능성 있음. **단 자산 도입 없이는 그 이상으로 안 오름.**

### 5.2 source_quote 58.5%의 의미

옳은 사상(*직접 인용 강제*)을 도입했음에도 58.5%에 그친 건 두 가지 가능성:

- LLM이 *quote 형식만 흉내내는* 출력을 함 (V2 fuzzy match 허용 시)
- 매뉴얼에 명시 안 된 부분을 *추론* 하는 게 진짜 많아서 quote 못 함

후자가 사실이면 → invariants 채널 필요. 매뉴얼 외 *회사 정책* 을 LLM이 quote할 수 있게.

### 5.3 9/41 실패의 분류 부재

PoC-γ 보고에 9 fail의 *분류* 가 없음.

다음 분류가 자동으로 되어야 *AWT 개선의 우선순위* 결정 가능:

- selector 깨짐 (V6로 사전 차단 가능)
- 시나리오 오류 (tc_regen 대상)
- 기대결과 오류 (invariants 채널로 차단 가능)
- 진짜 결함 발견 (성공 사례, 카탈로그 적재)
- fictional positive (spec hallucination 의심)

`failure_analysis.md` 의 `root_cause_candidates` 가 *enum화* 되면 자동 분류 가능. `03-seven-design-assets.md` §2.8 참조.

---

## 6. 한 줄 진단

> AWT-claude는 *베이스라인 + 구조 강제* 단계, 본 분석은 *베이스라인 + 자산화* 단계. 두 단계 사이의 약 6개월 분량 작업이 갭이다.

다음 문서:
- *왜 자산화가 핵심인가* → `02-density-problem.md`
- *어떤 자산을 어떻게 추가하나* → `03-seven-design-assets.md`
- *Stage 0~7에 어떻게 엮나* → `04-incremental-implementation.md`

# 05. 이론적 근거 — 4계층 / L0~L3 / 토큰 절감

본 권고들이 *왜 그런 형태인가* 의 이론적 근거. 채택 여부 결정 시 *근거의 타당성* 을 평가하는 데 사용.

## 1. 차별점의 4계층 프레임

LLM 자동화 도구의 효율은 *프롬프트 내용* 이 아니라 *호출 구조* 에서 나온다.

```text
Layer A. 호출 분할 (decomposition)
  - LLM 호출을 몇 번, 어떤 책임 경계로 자르는가
  - AWT-claude: 4 Contract 분리 ✓
  - 추가 권고: leaf 안에서 productType/featureType 분리

Layer B. 상태 보존 (state)
  - 호출 간 무엇을 코드가 들고 있는가
  - AWT-claude: stateless (D38), per-run artifact
  - 추가 권고: stateless API + stateful 자산 저장소 절충

Layer C. 사후 검증 (post-validation)
  - LLM 출력을 무엇으로 어떻게 거르는가
  - AWT-claude: V1~V5 ✓
  - 추가 권고: V6~V10

Layer D. 실측 피드백 (probe loop)
  - 출력의 일부를 실제 환경에 부딪쳐 검증·재요청
  - AWT-claude: Stage 5 실행 후 tc_regen
  - 추가 권고: V6 (selector 안정성)을 설계 단계로 당김
```

### 1.1 AWT-claude의 4계층 상태

| Layer | AWT-claude 상태 | 본 권고 |
|---|---|---|
| A. 분할 | 70% | leaf 호출 내 책임 분리 추가 |
| B. 상태 | 30% (run artifact만) | 자산 저장소 분리 |
| C. 검증 | 60% (V1~V5) | V6~V10 추가 |
| D. 피드백 | 40% (실행 후) | 설계 단계로 당김 |

**가장 큰 갭은 Layer B와 D.** A와 C는 부분 구현되어 있음.

## 2. Oracle 분류 — AWT-claude의 L1/L2/L3 vs 본 분석의 L0~L3

### 2.1 두 분류의 비교

**AWT-claude `doc/04-iso-mapping.md`**:
```text
L1 (Full AWT Automation)        : 객관 측정, oracle 도출 가능, 신뢰도 정량화 가능
L2 (AWT Assistance + Review)    : 도메인 지식·판단 필요, 시험원 검토
L3 (Human-Owned Testing)        : 자동화 부적합, 보조 정보만
```

**본 분석 `agenda/05`**:
```text
L0. Mechanical    : DOM 상태, HTTP 코드, 콘솔 에러
L1. Rule-based    : 텍스트·패턴·수치 비교
L2. Model-based   : LLM 판단 (분산 큼)
L3. Human-only    : 주관, 도메인 전문성
```

### 2.2 매핑

```text
본 분석 L0 + L1   ≈ AWT-claude L1 (전자동)
본 분석 L2         ≈ AWT-claude L2 (보조+검토)
본 분석 L3         ≈ AWT-claude L3 (수동)
```

분류 체계는 거의 동일. AWT-claude의 *L1 4가지 자격 조건* 이 본 분석의 *결정론 영역 정의* 와 일치.

### 2.3 두 분석의 공통 결론

```text
원칙 1. L0·L1만 신뢰 자동화로 부른다.
원칙 2. L2는 결과 출력 + 사람 검수 큐.
원칙 3. L3은 자동화 시도 안 함 + 보고서에 영역 표시.
```

이게 *시험성적서 윤리* — *자동화한 척* 의 결함을 차단.

### 2.4 본 분석이 추가로 권고하는 부분

AWT-claude의 L1/L2/L3 분류는 *카테고리 분류* 까진 좋다. 추가 권고:

```text
ProductTypeProfile.expectedAutomationCoverage:
  L1_ceiling   : 0.70    ← 제품유형별로 다름
  L2_assisted  : 0.15
  L3_human     : 0.15

→ 제품유형별 *자동화 가능 면적* 의 사전 명시
→ 시험성적서에 *자동화 범위의 한계* 가 자동 기록됨
```

CRUD 제품(예: gnuboard5)은 L1 70%까지 가능, 협업·미디어 제품은 L1 30% 이하. *유형별 차등* 이 산출물에 보이게.

## 3. 토큰 절감 견적

### 3.1 100 페이지 / 500 TC 규모 시뮬레이션

```text
AWT-claude 현행 (per-leaf, defect_patterns 500자만 활용):
  입력 토큰  ≈ 2.5M   (per-leaf manual_excerpt 반복 + DOM_SPEC)
  출력 토큰  ≈ 0.8M   (TC + 재생성 평균 1.2회)
  비전 토큰  ≈ 0      (이미지 미사용)
  환산 합계  ≈ 3.3M

AWT-claude + 7 자산 적용 후:
  입력 토큰  ≈ 0.9M   (ProjectState 선택 주입 + 캐시 효율 증가)
  출력 토큰  ≈ 0.3M   (V6 사전 차단으로 tc_regen 횟수 감소)
  비전 토큰  ≈ 0      (현행 유지)
  환산 합계  ≈ 1.2M

절감률: 약 64%
```

### 3.2 절감의 출처

| 자산 | 절감 기여도 | 메커니즘 |
|---|---|---|
| ProjectState 선택 주입 (자산 #1) | 입력 4배 감소 | productType·featureMap 재추론 회피 |
| V6 selector 사전 차단 (자산 #6) | 출력 30~50% 감소 | tc_regen 사이클 감소 |
| 패턴 적용 (자산 #5b) | 출력 10~20% 감소 | LLM 자유 enumerate → 패턴 lookup |
| 캐시 효율 증가 | 부수 효과 | 입력 안정화로 SHA-256 캐시 적중률 ↑ |

### 3.3 절감의 *비용* 영역

자산 자체 구축에 LLM 호출이 동반:
- 패턴 추출 (Stage 7 후 `PATTERN_EXTRACT` Contract)
- 결함 익명화 (`DEFECT_ANONYMIZE`)
- invariant 사후 추출 (프로젝트 종료 시)

이 비용은 *연간 절감의 약 1/10*. 손익분기 명확.

## 4. 자산화 곡선의 본질

### 4.1 곡선

```text
       자동화 TC 결함 매핑률
       │
   22% │ ────────  사람 시니어 (도달 불가)
       │   ╱────  사람 평균 (Phase 3+ 도달 가능)
   18% │ ╱
       │╱        ← Phase 3 (RAG 활성화)
   15% │
       │         ← Phase 2 (자산 누적 중)
   12% │
       │         ← Phase 1 (3개 자산 도입)
    8% │
       │         ← PoC 현재 (자산 없음)
    4% │
       └──────────────────── 시간
       0   3mo   6mo   1yr   2yr   2.5yr
```

### 4.2 곡선의 두 가지 본질

1. **천장은 22%.** 사람 시니어의 암묵지 한계로 자동화는 *완전 도달 불가*. 영원한 천장.

2. **출발점은 거의 0이지만 누적 효과로 *사람 평균* 까지 도달 가능.** 단 자산 채집 워크플로가 작동해야 함.

### 4.3 곡선이 평평해지는 조건

자산 채집이 *추가 작업* 으로 인식되면 6개월 후 채집 0:

| 채집 마찰 | 6개월 후 작동률 |
|---|---|
| 별도 폼에 invariant 작성 | 0~10% |
| TC 작성 중 입력 필드 추가 | 20~30% |
| 검수 시 1클릭 라벨 | 70~80% |
| 프로젝트 종료 시 LLM 추출 + 30분 검토 | 90%+ |
| 결함 해결 시 patternProposal (기존 흐름 연장) | 80~90% |

**90% 이상 작동하는 채집 방식만 살아남는다.** 다른 방식은 *시도해도 사라진다* 고 가정해야 함.

AWT-claude의 결함관리 흐름이 *어떻게 구성될지* 가 *자산화 성공의 절반*. PySide6 UI 설계 단계에서 *결함 입력 폼에 `patternProposal` 필드가 1순위* 로 배치되어야 함.

## 5. 깊이의 3정의 — 본 권고의 사고 프레임

| 정의 | LLM 강약 | 사유 | 자산 |
|---|---|---|---|
| A. Cardinality (TC 개수) | 압도적 강함 | 인지부담 0 | — (이미 강함) |
| B. Equivalence-class | 사람보다 강함 | 체크리스트 사고 | 자산 #5b 등가류 템플릿 |
| C. Information (invariant 수) | 사람보다 약함 | 도메인 지식 부재 | 자산 #2, #3, #5 |

**A·B 강점이 C 약점을 가려서 외관상 깊어 보임.** 실효 깊이는 C에 의존. C는 *외부 자산 주입* 없이는 메울 수 없음.

AWT-claude의 7기법(happy_path / equivalence / boundary / negative_*)은 *B의 카테고리 분류* 까지만 구현. *B 안의 깊이* 는 LLM 자유 추론 → equivalence-class inflation 위험.

## 6. *깊이의 환상* 문제

LLM은 *깊어 보이는 TC* 를 만드는 데 능숙. 진짜 깊이와 *외관상 깊이* 의 구분이 본 권고의 핵심 동기.

### 6.1 진짜 깊이의 정의

```text
unique_value(tc) = (이 TC가 잡는 결함 집합) - (다른 TC들이 잡는 결함 집합 합집합)

unique_value > 0 → 진짜 깊은 TC
unique_value = 0 → cosmetic depth (대체 가능)
```

### 6.2 측정의 어려움

위 정의는 *실제 결함 집합* 을 알아야 측정 가능. *예방적 측정* 으로는:

```text
대체 측정: TC 간 invariant 집합 Jaccard
  Jaccard(inv_A, inv_B) > 0.7 → cosmetic 의심

(완벽하진 않지만 운영 가능한 근사)
```

이게 자산 #7의 알고리즘적 근거.

## 7. *모든 커버리지를 자동화* 의 윤리적 한계

본 권고 전반에 깔린 원칙 하나:

> **"모든 커버리지를 다 자동화하려는 야망 자체가 결함을 만든다."**

- L2를 *신뢰 자동화* 로 격상시키면 자동화 편향으로 결함을 놓침
- L3까지 자동화 *시도* 하면 fictional 검증이 만들어짐
- **경계의 명시가 경계의 확장보다 우선**

이게 AWT-claude의 L3 *"Human-owned"* 명시 결정이 *옳은 방향* 인 이유. 본 권고는 이 결정을 *유지하면서 더 명시화* 하라는 것 — *어느 영역이 자동화 시도 안 함인지* 시험성적서에 표시.

## 8. 세 가지 산출물 구분의 원칙

시험성적서에는 반드시:

```text
1. 자동화로 검증한 것              (L0, L1)
2. 자동화 영역 밖이라 수동 검증한 것 (L3)
3. 검증 시도 안 한 것              (시간·범위 제약, 명시)
```

이 세 구분이 모두 명시되어야 *진짜 자동화 도구의 산출물* 이지, *자동화한 척* 의 산출물이 아니다.

AWT-claude의 *G5 (Execution Results)* 컬럼은 `actual_output, pass/fail/blocked/not_executed` 만 있음. *not_executed* 가 *"실행 시도했으나 막힘"* 인지 *"애초에 자동화 시도 안 함"* 인지 구분 안 됨. 권고:

```diff
  G5. Execution Results:
- status: pass/fail/blocked/not_executed
+ status: pass/fail/blocked/excluded/not_executed
+   - excluded: 자동화 영역 밖 (사람 검증 영역, automation_mode=MANUAL_REQUIRED)
+   - not_executed: 실행 시도했으나 막힘 (재시도 가능)
```

## 9. 본 권고의 적용 결과 예측

자산 7개 모두 활성화 시점(Year 2.5)의 AWT-claude:

| 지표 | 현재 PoC | 자산 적용 후 |
|---|---|---|
| INFERRED 비율 | 41.5% | 15% 미만 |
| source_quote 인용률 | 58.5% | 80% 이상 |
| 신규 결함 매핑률 (보정) | 8~14% | 18~21% |
| TC당 평균 검수 시간 | 51초 | 25~30초 |
| 토큰 비용 (per 시험) | 기준 | 약 36% (64% 절감) |
| 패턴 라이브러리 | 0 | 100~150개 |
| 결함 카탈로그 | 0 | 800~1500건 |
| domain-invariants | 0 | 200~400개 |

**천장에 *근접* 하지만 사람 시니어 수준엔 도달 못 함.** 이게 정직한 기대치.

## 10. 마지막 원칙 — 한 줄로

> **capability 차별점은 LLM 발전 속도에 깎인다. 살아남는 차별점은 결정의 결정론성과 상태의 영속성이다.**

본 권고 7가지 자산은 모두 *결정론(코드로 결정) + 영속성(자산 누적)* 의 두 축에서 설계되었다. AWT-claude가 이 두 축에 자원을 투입할 가치가 있다고 판단하면 본 권고가 유효하고, *LLM 발전에 의존* 하는 전략이라면 본 권고의 우선순위는 낮다.

## 11. 다음 문서

본 권고가 *답하지 못하고* AWT-claude 팀이 답해야 할 결정사항: → `06-questions-to-resolve.md`

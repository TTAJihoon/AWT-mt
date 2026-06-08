# 00. 핵심 요약 (5분)

## 본 제안이 다루는 한 가지 문제

**LLM 자동생성 TC의 *생산밀도*** — 외관상 풍부한 출력에 비해 *최종 결함에 매핑되는 TC 비율* 이 낮은 현상.

PoC-α 결과 신호:
- INFERRED 비율 41.5%
- source_quote 직접 인용률 58.5%
- 신규 결함 매핑률 ≈ 2/41 = 4.9% (목업 단순화 보정 후 추정 11~14%)

이 셋은 모두 *밀도가 낮다는 직접 지표* 다.

## 핵심 진단

밀도 저하의 원인은 LLM 성능이 아니라 **자산화 시스템의 부재**.

AWT-claude는 *구조 강제(V1~V5, JSON Schema)* 까지 잘 됐지만, 다음이 빠져 있다:

1. **결함 카탈로그** — 누적·검색·환류 메커니즘 (D4/D13/D16의 *정책* 만 있고 *시스템* 없음)
2. **domain-invariants 채널** — 매뉴얼 외 *회사·법적·보안 정책* 의 명시 주입 채널 (현재 매뉴얼 1500자 발췌만)
3. **TestPattern 라이브러리** — 등가류·기법별 사전 정의 (현재는 매 호출 LLM 자유 추론)

이 셋이 없어서 LLM은 *교과서적 TC* 만 만들 수 있고, *회사 특수성·과거 결함 학습* 영역에 도달 못 한다.

## 5가지 우선 권고

| # | 권고 | 적용 위치 | 효과 |
|---|---|---|---|
| 1 | 결함 카탈로그 스키마 + 적재 UI 도입 | 신규 `data/defect-catalog/` | 자산 누적의 출발점 |
| 2 | domain-invariants.yaml 채널 + LLM 입력 추가 | `prompts/tc_design.md` 입력 확장 | source_quote 58.5% 본질 해법 |
| 3 | selector 안정성 점수 (V6) 추가 | `doc/03-tc-schema.md` 검증 V 추가 | 깨진 selector 사전 차단 |
| 4 | negative 카테고리별 minimum count 강제 | `prompts/tc_design.md` 강화 | V4 분포 강제를 카테고리 강제로 확장 |
| 5 | 실패 TC 자동 분류 (selector/scenario/expected/fictional) | `prompts/failure_analysis.md` 출력 확장 | 9 fail 분석의 자산화 |

이 5개를 1개월 내 추가하면 Phase 1 진입 시 *결함 매핑률 12~15%* 도달 가능 (현재 추정 4.9% → 11~14% → 12~15%).

## 3가지 구체적 코드 변경 (예시)

### A. `prompts/tc_design.md` 입력 확장

```diff
  ## 입력 파라미터
  - category_major, category_mid, category_leaf
  - requirement_id
  - tc_id_start
  - manual_excerpt (max 1500자)
- - defect_patterns (max 500자)
+ - domain_invariants_yaml (max 2000자, 회사/법적/보안 정책)
+ - similar_past_defects (max 1500자, 결함 카탈로그 RAG N건 요약)
+ - applicable_test_patterns (max 1000자, 적용 가능 패턴 ID + 등가류)
```

### B. `doc/03-tc-schema.md` 검증 V 추가

```diff
  ## 검증 파이프라인 (V1–V5)
  V1: 필수 필드 채움
  V2: source_quote 명세 대조
  V3: INFERRED 비율 제어
  V4: 기법 다양성 (happy_path ≤ 50%)
  V5: leaf 커버리지
+ V6: selector 안정성 점수 (Low-stability 자동 거부)
+ V7: TC 간 invariant 집합 Jaccard 중복도 (> 0.7 cosmetic 의심)
+ V8: 참조된 정책이 domain_invariants_yaml에 실재 (없으면 spec hallucination 경고)
```

### C. 신규 결함 카탈로그 스키마 (예시)

```jsonc
// data/defect-catalog/DEF-2025-NNN.json
{
  "defectId": "DEF-2025-USR-0142",
  "projectId": "...",
  "product": { "productTypeIds": [...], "techStack": [...] },
  "feature": { "featureType": "CREATE", "screenLocation": "/..." },
  "title": "...",
  "description": "...",
  "observedBehavior": "...",
  "expectedBehavior": "...",
  "iso25023Mapping": { "characteristic": "기능 적합성", ... },
  "detection": { "method": "MANUAL_EXPLORATORY", "detectingTcId": null },
  "learning": {
    "patternProposal": {  // ← 핵심 필드
      "name": "STATE_FILTERED_REFERENCE_INTEGRITY",
      "description": "...",
      "appliesTo": ["CREATE", "UPDATE"],
      "checks": [...],
      "status": "candidate"  // candidate → preliminary → active → archived
    }
  },
  "tags": [...],
  "vectorEmbedding": "..."
}
```

세부 스키마와 운용은 `03-seven-design-assets.md` §2.5 참조.

## 1가지 가장 중요한 결정 사항 (AWT-claude 팀이 답해야 함)

**`patternProposal` 작성을 프로젝트 종료 게이트에 강제할 것인가?**

이 결정이 *Yes* 면 결함 카탈로그는 *학습 자산* 이 되고, *No* 면 *결함 목록* 에 그친다. D4/D13/D16의 *익명화 정책* 은 *No* 와 *Yes* 어느 쪽으로 가도 작동하지만, *자산화* 효과는 *Yes* 일 때만 발생.

본 분석 전체에서 *가장 자주 빠뜨리는 결정* 으로 식별된 항목.

## 5가지 가장 위험한 신호 (즉시 점검 권장)

1. **PoC-α의 INFERRED 임계 *완화* 결정** — *조정* 이 아니라 *invariants 채널 도입* 방향이 옳음. `01-gap-analysis.md` §3.3, §4.3 참조.

2. **PoC-γ의 9 fail 결함 분류 부재** — 다음 개선 우선순위 결정이 *불가능*. `01-gap-analysis.md` §5.3.

3. **D38 stateless API + 자산 누적 메커니즘 부재** — *stateless API + stateful 자산 저장소* 절충 가능. `01-gap-analysis.md` §4.1.

4. **per-leaf 처리의 *cross-leaf invariant* 구조적 차단** — 화면 간 일관성 결함이 시스템적으로 누락됨. `03-seven-design-assets.md` §2.3.

5. **defect_patterns 500자 입력은 RAG 결과 N건 주입에 부적합** — 2000자 이상으로 확장 필요. `03-seven-design-assets.md` §2.5.

## 깊이 읽기

각 항목의 근거·예시·trade-off:

- 왜 밀도가 본질 문제인가 → `02-density-problem.md`
- 7가지 자산의 스키마·통합 위치 → `03-seven-design-assets.md`
- Stage 0~7과 자산을 어떻게 엮을 것인가 → `04-incremental-implementation.md`
- 4계층 차별점·L0~L3 oracle 분류·토큰 절감 → `05-foundational-frameworks.md`
- AWT-claude 팀이 답해야 할 미해결 결정 → `06-questions-to-resolve.md`

## 한 줄 결론

> 결함 카탈로그 + invariants 채널 + selector 점수 — 이 셋이 *AWT-claude를 베이스라인 자동화에서 자산화 자동화로 옮기는* 최소 변경이다.

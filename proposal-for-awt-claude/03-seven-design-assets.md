# 03. 갭을 메우는 7가지 자산

각 자산은 *없을 때 어떤 결함을 놓치는가* 가 명확해야 한다. 본 장은 각 자산의 *스키마 + AWT-claude 코드 통합 위치* 를 함께 제시한다.

## 자산 깊이 영향 매트릭스 (재정렬)

| 자산 | B 깊이 | C 깊이 | 토큰 절감 | 우선순위 |
|---|---|---|---|---|
| #1 ProjectState + 자산 저장소 | — | — | 큼 (간접) | 2순위 |
| #2 domain-invariants.yaml | — | 매우 큼 | — | **1순위** |
| #3 cross-screen-invariants.yaml | — | 큼 | — | 2순위 |
| #4 PageState 그래프 (다중 DOM) | 작음 | 중간 | — | 2순위 |
| #5 결함 카탈로그 + RAG | — | 매우 큼 (RAG 후) | — | **1순위** |
| #6 selector 안정성 점수 (V6) | — | — | 간접 (재실행 차단) | **1순위** |
| #7 TC 중복도 검사 (V7) | 작음 | 작음 | — | 3순위 |

**Phase 1 진입 전 1순위 3개(#2·#5·#6)** 만 우선 도입 권장.

---

## 자산 #1. ProjectState + 자산 저장소

### 1.1 본질

D38의 *stateless API* 를 깨지 않고 *조직 자산 누적* 을 가능하게 하는 절충 구조.

```text
LLM API 호출 자체     : stateless 유지 (D38 보존)
프로젝트 간 자산      : 별도 영속 저장소
호출 시점에         : 자산을 입력으로 주입

→ "stateless" 원칙의 정의: API 호출에는 대화 이력 없음
→ 자산은 별도 시스템에서 관리하고 *입력 데이터로* 들어감
```

### 1.2 저장소 구조 (예시)

```
data/
├── assets/
│   ├── test-patterns/          # 자산 #5b
│   │   ├── PATTERN_001.json
│   │   └── ...
│   ├── domain-invariants/      # 자산 #2
│   │   └── default.yaml
│   ├── cross-screen-invariants/ # 자산 #3
│   │   └── default.yaml
│   ├── defect-catalog/         # 자산 #5
│   │   ├── DEF-2025-NNN.json
│   │   └── ...
│   └── equivalence-templates/  # 자산 #5b
│       └── *.json
└── poc/
    └── 2026-05-19/output/      # 기존 immutable run artifact (보존)
```

### 1.3 ProjectState (per-project 상태)

```jsonc
// data/projects/PRJ-2025-XXX/project-state.json
{
  "projectId": "PRJ-2025-XXX",
  "productTypeClassification": [
    { "productTypeId": "USER_MANAGEMENT", "confidence": 0.86 }
  ],
  "appliedPatternIds": ["PATTERN_001", "PATTERN_005", ...],
  "appliedInvariantNames": ["marketing_email_opt_in", ...],
  "ragSearchResults": [
    { "defectId": "DEF-2024-USR-0098", "similarity": 0.78 }
  ],
  "coverageMatrix": [
    { "patternId": "...", "detected": true, "generated": true, "tcIds": ["TC-001-001"] },
    { "patternId": "...", "detected": false, "generated": false, "reason": "..." }
  ]
}
```

### 1.4 AWT-claude 코드 통합

- 신규 디렉터리 `data/assets/` 생성
- 신규 모듈 `app/state/project_state.py` (또는 `orchestrator/` 하위)
- Stage 0 시작 시 ProjectState 초기화, productType 분류
- Stage 2 호출 전 적용 가능 패턴·invariants 검색하여 입력에 주입
- Stage 7 보고서에 CoverageMatrix 포함

---

## 자산 #2 (1순위). domain-invariants.yaml 채널

### 2.1 본질

매뉴얼에 *없는* 회사·법적·보안 정책을 명시 주입. spec hallucination 차단의 본질적 해법.

### 2.2 스키마

```yaml
# data/assets/domain-invariants/default.yaml
- name: marketing_email_opt_in
  statement: "마케팅 이메일은 GDPR 옵트인 동의 시에만 발송"
  appliesTo: [CREATE, UPDATE_PROFILE]
  verification: "audit_log.email_sent WHERE type='marketing' → consent_record 존재"
  severity_on_violation: BLOCKER
  source: "GDPR Article 7"

- name: deleted_account_reuse
  statement: "soft-deleted 계정의 이메일은 30일 후 재등록 가능"
  appliesTo: [CREATE]
  verification: "deleted_at + 30 days < now() 에서만 등록 허용"
  severity_on_violation: MAJOR
  source: "사내 운영 정책 v2.3"

- name: state_filtered_reference_integrity
  statement: "참조 select는 참조 대상의 활성 상태로 필터되어야 함"
  appliesTo: [CREATE, UPDATE]
  verification: "select 옵션 = 참조 테이블 WHERE status=ACTIVE"
  severity_on_violation: MAJOR
  source: "결함 학습 (DEF-2024-USR-0098)"
```

### 2.3 AWT-claude 코드 통합

#### `prompts/tc_design.md` 입력 확장

```diff
  ## 입력 파라미터
  - category_major, category_mid, category_leaf
  - requirement_id
  - tc_id_start
  - manual_excerpt (max 1500자)
- - defect_patterns (max 500자)
+ - domain_invariants_yaml (max 2000자)
+ - similar_past_defects (max 1500자)
+ - applicable_test_patterns (max 1000자)
```

#### LLM 지침 추가

```diff
  ## 시스템 지침
  ... ISO/IEC 25023 기반 SW 시험 전문가 ...
  
+ 추가 강제 사항:
+ - domain_invariants_yaml에 명시된 각 invariant에 대해, 
+   해당 leaf에 appliesTo가 매칭되면 *반드시* 검증 TC를 1개 이상 생성하라.
+ - 매뉴얼이나 invariant에 *없는 정책* 을 시나리오로 만들지 마라.
+ - 정책 위반 검증 TC는 source_quote에 invariant.name을 적어라.
```

#### V 추가

```diff
  ## 검증 V1~V5
  ...
+ V8: spec hallucination 검증
+   - 각 TC의 expected_output에 등장하는 *정책 진술* 이
+   - manual_excerpt 또는 domain_invariants_yaml에 실재하는지
+   - 둘 다에 없으면 hallucination 의심으로 검수자 큐
```

### 2.4 채집 방식

본 자산이 *누구에 의해 작성되는가* 가 운영의 핵심:

- **전략 A (권장)**: 결함 발생 시 `learning.patternProposal.checks` 의 일반화 형태로 자동 후보 생성. 시험설계 리드가 검토 후 yaml 진입.
- **전략 B (보조)**: 프로젝트 종료 시 LLM이 완성 TC 전체에서 *공통 invariant* 추출. 시험설계 리드가 yes/no 라벨링.

### 2.5 PoC-α 데이터로 적용 시뮬레이션

PoC-α의 41 TC에서 *INFERRED 17개(41.5%)* 의 expected_output을 분석하면, 일반화 가능한 invariant가 약 5~8개 추출 가능 (추정). 이 5~8개가 yaml에 들어가면 다음 PoC에서 *INFERRED 비율이 25~30%* 로 자연 감소.

---

## 자산 #3. cross-screen-invariants.yaml

### 3.1 본질

per-leaf 처리(D39)의 *구조적 한계* 를 보완. *서로 다른 leaf 간 관계* 를 별도 검증 단계로.

### 3.2 스키마

```yaml
# data/assets/cross-screen-invariants/default.yaml
- name: list_reflects_create
  statement: "신규 등록 후 목록 페이지 1초 내 반영"
  source: CREATE
  target: READ_LIST
  verification: "POST 성공 응답 후 GET /list count == 이전 +1"

- name: audit_log_completeness
  statement: "변경 액션은 6필드 audit log 남김"
  source: [CREATE, UPDATE, DELETE]
  target: AUDIT_LOG
  verification: "actorId/targetId/action/timestamp/sourceIp/userAgent 모두 채워짐"

- name: permission_change_propagation
  statement: "권한 변경 후 사용자의 모든 활성 세션에 즉시 적용"
  source: UPDATE_PERMISSION
  target: SESSION_VALIDATION
  verification: "권한 변경 후 5초 내 해당 사용자 권한 체크 시 새 값 반환"
```

### 3.3 AWT-claude 코드 통합

#### Stage 2.5 신규 추가

```text
기존:
  Stage 2: per-leaf TC 설계 (LLM 호출 N회)
  Stage 3: V1~V5 검증

권고:
  Stage 2: per-leaf TC 설계 (현행 유지)
  Stage 2.5: cross-screen TC 설계 (별도 LLM 호출 1회)
    - 입력: 전체 leaf 목록 + cross-screen-invariants.yaml
    - 출력: cross-screen TC들 (TC-XSC-NNN 형식)
  Stage 3: V1~V5 + 추가 V (V9 cross-screen coverage)
```

#### 새 prompt `prompts/cross_screen_design.md`

```text
## Contract: CROSS_SCREEN_DESIGN v1.0
모델: claude-sonnet-4-6
토큰: 4000 in / 3000 out

## 입력
- all_leafs_summary: 전체 leaf 분류 요약 (max 2000자)
- cross_screen_invariants_yaml (max 2000자)

## 출력
{
  "tcs": [
    {
      "tc_id": "TC-XSC-001",
      "scenario": "...",
      "source_leaves": ["leaf1", "leaf2"],
      "invariant_name": "list_reflects_create",
      ...
    }
  ]
}
```

---

## 자산 #4. PageState 그래프 (다중 DOM 상태)

### 4.1 본질

Stage 0 DOM scan을 *한 시점 스냅샷* 이 아닌 *상태별 누적 그래프* 로.

### 4.2 데이터 구조

```jsonc
// data/projects/PRJ-XXX/page-states.json
{
  "pageStates": [
    {
      "stateId": "STATE_INITIAL",
      "url": "/admin/users",
      "triggerAction": null,
      "domSummary": { ... },
      "elementRegistry": [ ... ]
    },
    {
      "stateId": "STATE_SEARCH_RESULT",
      "url": "/admin/users",
      "triggerAction": "searchButton.click(query='홍길동')",
      "domSummary": { ... },
      "elementRegistry": [ ... ]
    },
    {
      "stateId": "STATE_CREATE_MODAL_OPEN",
      "url": "/admin/users",
      "triggerAction": "createButton.click",
      "domSummary": { ... },
      "elementRegistry": [ ... ]
    }
  ]
}
```

### 4.3 AWT-claude 코드 통합

#### Stage 0 확장 (lazy 구축)

```text
현행 Stage 0: 한 시점 DOM scan → spec 초안

권고 Stage 0:
  1. 초기 DOM scan → STATE_INITIAL 등록
  2. spec 초안 생성 (LLM)
  3. 발견된 *상호작용 요소* 별로 lazy 트리거
     - 검색 버튼 클릭 → STATE_SEARCH_RESULT 추가
     - 생성 버튼 클릭 → STATE_CREATE_MODAL_OPEN 추가
     - ... (최대 N개 상태까지)
  4. 각 상태에서 spec 보강
```

### 4.4 비용 통제

- 모든 상태를 *선구축(eager)* 하면 Stage 0 시간·비용 폭증
- *lazy*: TC 설계 중 selector 매칭 실패 시 그때 새 상태 탐색
- 한 번 탐색한 상태는 PageState 그래프에 영속

---

## 자산 #5 (1순위). 결함 카탈로그 + RAG

### 5.1 본질

D4/D13/D16의 *익명화 정책* 을 *시스템화*. 누적·검색·환류의 3단계 메커니즘.

### 5.2 스키마 (전체)

```jsonc
// data/assets/defect-catalog/DEF-2025-USR-0142.json
{
  // === 식별 ===
  "defectId": "DEF-2025-USR-0142",
  "projectId": "PRJ-2025-A012",
  "discoveredAt": "2025-08-14T09:23:00+09:00",

  // === 제품 컨텍스트 (유사 검색 키) ===
  "product": {
    "name": "...",                          // 익명화 후 hash
    "productTypeIds": ["USER_MANAGEMENT"],
    "techStack": ["React", "Spring Boot"],
    "scale": "MEDIUM"
  },

  // === 기능 컨텍스트 ===
  "feature": {
    "featureType": "CREATE",
    "screenLocation": "/admin/users/new",
    "triggeringAction": "submitButton.click",
    "preconditions": ["관리자 로그인", "부서 1개 이상 존재"]
  },

  // === 결함 본문 (임베딩 대상) ===
  "title": "비활성 부서 선택 후 사용자 등록 가능",
  "description": "사용자 등록 폼의 부서 select는 모든 부서를 노출. 비활성 부서 선택해도 등록 차단 없음.",
  "observedBehavior": "비활성 부서 선택 후 등록 시 성공 처리",
  "expectedBehavior": "비활성 부서는 select에서 제외되거나 등록 단계에서 거부",

  // === 분류 ===
  "iso25023Mapping": {
    "characteristic": "기능 적합성",
    "subcharacteristic": "기능 정확성"
  },
  "severity": "MAJOR",
  "defectCategory": "BUSINESS_RULE_VIOLATION",

  // === 발견 경로 (TC 효과 측정) ===
  "detection": {
    "method": "MANUAL_EXPLORATORY",     // AUTO_TC / MANUAL_TC / EXPLORATORY / CUSTOMER_REPORT
    "detectingTcId": null,
    "timeToDetectMin": 35
  },

  // === 근본원인 ===
  "rootCause": {
    "category": "SPEC_AMBIGUITY",        // FRONTEND/BACKEND/SPEC/INTEGRATION/DATA/CONFIG
    "whatWasMissed": "기획서에 비활성 부서 처리 규칙 없음"
  },

  // === 학습 피드백 (가장 중요한 부분) ===
  "learning": {
    "preventingPatternId": null,
    "patternProposal": {
      "name": "STATE_FILTERED_REFERENCE_INTEGRITY",
      "description": "참조 select는 참조 대상의 활성 상태로 필터되어야 함",
      "appliesTo": ["CREATE", "UPDATE"],
      "checks": [
        "select 옵션 = 참조 테이블 WHERE status=ACTIVE",
        "POST 요청 시 서버측에서도 status 재검증"
      ],
      "proposalAuthor": "QA-LEE",
      "status": "candidate"   // candidate → preliminary(3건) → active(5건) → archived(6개월 무사용)
    }
  },

  // === 검색용 ===
  "tags": ["참조무결성", "상태필터", "select 검증"],
  "vectorEmbedding": "...",              // description + observed + expected 임베딩

  // === 관리 ===
  "status": "RESOLVED",
  "resolution": "프론트엔드: status 필터 추가. 백엔드: POST 검증 추가"
}
```

### 5.3 가장 중요한 필드

**`learning.patternProposal`** — 이 필드가 비어 있으면 카탈로그는 *결함 목록* 일 뿐 *학습 자산* 이 아님.

작성 책임: 결함 발견자가 아니라 **해결 후 검토자(시험설계 리드)**.

작성 시점: 결함 해결 후 회고. 약 15분/건.

**작성 강제 정책이 없으면 1년 후 패턴 0개가 됨.** 가장 자주 빠뜨리는 정책.

### 5.4 RAG 통합

#### Phase 1: 적재만 (검색 없이)

- 결함 발생 시 카탈로그에 본문만 적재
- patternProposal은 *candidate* 상태로 누적
- RAG는 아직 활성화 안 함

#### Phase 2: 카탈로그 ≥ 100건 시점

- 벡터 임베딩 인덱스 구축
- TC 생성 시 RAG 검색 활성화

#### Phase 3: 카탈로그 ≥ 500건 시점

- 유사도 임계 정밀 튜닝
- 신규 프로젝트 cold start 비용 감소 확인

### 5.5 AWT-claude 코드 통합

#### `prompts/tc_design.md` 입력 변경

```diff
- defect_patterns (max 500자)
+ similar_past_defects (max 1500자)
+   - RAG 검색으로 productType + featureType 매칭 상위 3건
+   - 각 결함의 title + description + patternProposal.checks 요약
```

#### `prompts/tc_design.md` 지침 추가

```diff
+ 추가 강제 사항:
+ - similar_past_defects의 각 결함에 대해
+   동일/유사 결함을 검증할 TC를 1개 이상 생성하라.
+ - 해당 TC의 source_quote에 결함 ID를 명시하라.
```

#### 신규 모듈

```python
# app/rag/defect_retrieval.py
def retrieve_similar_defects(
    product_type_ids: list[str],
    feature_type: str,
    leaf_summary: str,
    top_k: int = 3
) -> list[Defect]:
    """결함 카탈로그에서 유사 결함 검색"""
    ...
```

---

## 자산 #5b. TestPattern 라이브러리 + 등가류 템플릿

### 5b.1 본질

LLM 자유 추론으로 매번 enumerate되는 등가류를 *결정론적 자산* 으로.

### 5b.2 TestPattern 스키마

```jsonc
// data/assets/test-patterns/PATTERN_CREATE_VALID.json
{
  "patternId": "PATTERN_CREATE_VALID",
  "featureType": "CREATE",
  "name": "정상 등록",
  "requiredEvidence": ["createButton", "inputForm", "saveButton"],
  "scenarioTemplate": "{entityName} 필수값을 입력하여 신규 등록한다",
  "expectedResultTemplate": "등록 후 {resultLocation}에서 {primaryDisplayField}가 확인된다",
  "recommendedAssertions": ["assertRowContains", "assertTextVisible"],
  "negativeRequiredCount": 3,
  "negativeCategoryRequired": [
    "validation_failure",
    "duplicate_or_conflict",
    "permission_denied"
  ],
  "automationDefault": true,
  "defaultRiskLevel": "MEDIUM",
  "isoQualityMapping": {
    "characteristic": "기능 적합성",
    "subcharacteristic": "기능 정확성"
  },
  "status": "active",
  "validatedProjectsCount": 8
}
```

### 5b.3 등가류 템플릿 스키마

```jsonc
// data/assets/equivalence-templates/EMAIL_INPUT.json
{
  "templateId": "EMAIL_INPUT_DEPTH",
  "applicableWhen": "feature.inputs has email",
  "classes": [
    { "id": "format.missing-at",       "priority": "required" },
    { "id": "format.missing-domain",   "priority": "required" },
    { "id": "boundary.min-length",     "priority": "recommended" },
    { "id": "boundary.max-length",     "priority": "required" },
    { "id": "normalization.case",      "priority": "recommended" },
    { "id": "normalization.whitespace","priority": "optional" },
    { "id": "injection.sql",           "priority": "skipIf product.backend.prepared==true" },
    { "id": "unicode.emoji",           "priority": "skipIf product.spec.unicodeAllowed==true" }
  ]
}
```

### 5b.4 AWT-claude 코드 통합

#### `prompts/tc_design.md` 입력 추가

```diff
+ applicable_test_patterns (max 1000자):
+   - leaf featureType에 매칭되는 TestPattern 목록
+   - 각 패턴의 ID + scenarioTemplate + negativeRequiredCount
+   - LLM은 이 패턴들을 *반드시* 적용
```

#### 새 V 추가

```diff
+ V9: TestPattern 적용 완전성
+   - 적용 가능 패턴 N개 중 K개 생성 (K/N ≥ threshold)
+   - 미생성 패턴은 *근거 명시* 필수 (CoverageMatrix에 기록)

+ V10: negativeRequiredCount 충족
+   - 각 적용 패턴의 negativeRequiredCount 이상 음성 TC 생성
+   - negativeCategoryRequired 카테고리 모두 커버
```

---

## 자산 #6 (1순위). selector 안정성 점수 (V6)

### 6.1 본질

깨질 selector를 *실행 단계가 아닌 설계 단계* 에서 차단.

### 6.2 점수 산식 (예시)

```python
def selector_stability_score(selector: str, dom_element: dict) -> float:
    score = 0.0
    
    # 긍정 가중치
    if has_stable_id(selector):            score += 0.40
    if has_role_and_aria_label(selector):  score += 0.20
    if has_unique_text(selector):          score += 0.20
    
    # 부정 가중치
    if has_positional_selector(selector):  score -= 0.30  # nth-child, position
    if has_dynamic_class(selector):        score -= 0.20  # hash-suffixed class
    if has_complex_css_chain(selector, depth=3): score -= 0.10
    
    return max(0.0, min(1.0, score))


def selector_decision(score: float) -> str:
    if score >= 0.7:  return "ACCEPT"
    if score >= 0.5:  return "ACCEPT_WITH_WARNING"
    return "REJECT"
```

### 6.3 AWT-claude 코드 통합

#### V6 추가

```diff
  ## 검증 V1~V5
  V1~V5: (현행 유지)
+ V6: selector 안정성 점수
+   - 각 TC의 검증 selector를 추출
+   - selector_stability_score >= 0.5 미만이면 거부
+   - tc_regen에 *대안 selector 제안* 요청
```

#### tc_regen.md 입력 확장

```diff
  ## 입력
  - failed_tcs_json
  - v_failures
+ - low_stability_selectors: list[{
+     selector: str,
+     score: float,
+     suggested_alternatives: list[str]  // ElementRegistry에서
+   }]
  - fix_instructions
```

### 6.4 ElementRegistry 보강

selector 안정성 점수가 작동하려면 ElementRegistry가 *selector 후보를 다중 보존* 해야 한다.

```jsonc
// PageState.elementRegistry 각 항목
{
  "elementId": "el_create_button_001",
  "anchor": "main > div.users > button.create",  // 시각적 위치
  "selectorCandidates": [
    { "selector": "[data-testid='create-user']",    "score": 0.95 },
    { "selector": "button:has-text('사용자 등록')",   "score": 0.75 },
    { "selector": ".user-create-btn",               "score": 0.45 },
    { "selector": "main > div:nth-child(2) > button","score": 0.20 }
  ],
  "role": "button",
  "text": "사용자 등록"
}
```

V6는 *selectorCandidates의 최고 점수* 를 사용. 모든 후보가 0.5 미만이면 거부.

---

## 자산 #7. TC 중복도 자동 검사 (V7)

### 7.1 본질

cosmetic depth를 자동 검출.

### 7.2 알고리즘 (의사코드)

```python
def detect_cosmetic_duplicates(tcs: list[TC]) -> list[Pair]:
    flagged = []
    for tc_a, tc_b in combinations(tcs, 2):
        inv_a = extract_invariants(tc_a.assertions)
        inv_b = extract_invariants(tc_b.assertions)
        if not inv_a or not inv_b:
            continue
        jaccard = len(inv_a & inv_b) / len(inv_a | inv_b)
        if jaccard > 0.7:
            flagged.append((tc_a.tc_id, tc_b.tc_id, jaccard))
    return flagged
```

### 7.3 invariant 추출 (LLM 보조)

각 TC의 *assertions + expected_output* 에서 *논리적 검증 명제* 를 LLM으로 추출:

```text
TC-001 의 expected_output:
  "등록 후 목록에서 입력한 이름이 표시되어야 함"

→ 추출된 invariants:
  - list_reflects_create
  - text_match_input

TC-007 의 expected_output:
  "신규 등록 사용자가 사용자 목록에 보이는지 확인"

→ 추출된 invariants:
  - list_reflects_create
  - text_match_input

→ Jaccard = 2/2 = 1.0 → cosmetic 의심 플래그
```

### 7.4 우선순위

이 자산은 *TC 수가 늘기 시작한 후* 가 효과적. Phase 1엔 *후순위*, Phase 2~3에 도입 권장.

---

## 자산 통합 — `prompts/tc_design.md` 의 최종 형태 (권고)

```text
## Contract: TC_DESIGN v2.0
모델: claude-sonnet-4-6
토큰: 6000 in / 3000 out  (증가, +자산 주입 분량)

## 입력
- category_major, category_mid, category_leaf
- requirement_id
- tc_id_start
- manual_excerpt (max 1500자)
- domain_invariants_yaml (max 2000자)         ← 신규 (자산 #2)
- similar_past_defects (max 1500자)            ← 확장 (자산 #5)
- applicable_test_patterns (max 1000자)        ← 신규 (자산 #5b)
- applicable_equivalence_templates (max 800자) ← 신규 (자산 #5b)

## 시스템 지침
... ISO/IEC 25023 ...

추가 강제:
1. applicable_test_patterns의 각 패턴에 대해 TC 생성
   - 미생성 시 사유 명시
   - negativeRequiredCount 이상 음성 TC 생성
2. domain_invariants_yaml의 매칭 invariant 검증 TC 생성
3. similar_past_defects의 각 결함에 대해 유사 결함 검증 TC 생성
4. equivalence_templates의 등가류 분류기 사용 (자유 enumerate 금지)
5. source_quote 출처:
   - manual_excerpt (직접 인용)
   - invariant.name (정책 출처)
   - defectId (결함 학습 출처)
   - patternId (패턴 출처)
   - INFERRED (위 어느 것도 아닌 경우)

## 출력 (현행 유지 + 확장)
{
  "tcs": [
    {
      "tc_id", "scenario", "precondition", "expected_output",
      "technique", "source_quote", "gen_confidence",
      "applied_pattern_id",        ← 신규
      "applied_invariant_names",   ← 신규 (배열)
      "related_defect_ids",        ← 신규 (배열)
      "covered_equivalence_classes" ← 신규 (배열)
    }
  ],
  "coverage_summary": {            ← 신규
    "applied_patterns": [...],
    "missed_patterns": [           // 적용 가능했으나 미생성
      { "patternId": "...", "reason": "..." }
    ]
  }
}
```

## 다음 문서

각 자산을 *언제 도입하는가* (Stage 0~7 통합 + Phase 0~4 로드맵): → `04-incremental-implementation.md`

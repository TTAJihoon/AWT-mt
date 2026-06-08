# LLM Call Contract 설계 — 토큰 최적화

**목적:** AWT에서 Anthropic API를 호출하는 모든 지점을 정형화. 각 Call은 입력 범위·출력 스키마·토큰 예산을 사전 고정해 낭비 없는 추론 호출을 보장.
**결정 근거:** D38 (stateless 호출), D41 (토큰 최적화 원칙)

---

## 1. Call 목록

| Call ID | 호출 단계 | 목적 | 호출 단위 |
|---|---|---|---|
| `DOM_SPEC` | Stage 0 | DOM 요소 → 기능 명세 초안 | 페이지당 1회 |
| `TC_DESIGN` | Stage 2 | leaf 기능 → TC 목록 | leaf당 1회 |
| `TC_REGEN` | Stage 3 | V 실패 TC 재생성 | 실패 배치당 1회 |
| `FAILURE_ANALYSIS` | Stage 6 | 실패 TC 원인 분석 | 실패 TC당 1회 |

---

## 2. Contract 공통 규칙

1. **대화 히스토리 없음** — 매 호출은 독립된 단일 메시지. 이전 컨텍스트 미전달.
2. **JSON Schema 강제** — 모든 출력은 사전 정의 JSON 스키마로만 응답. 자유 텍스트 금지.
3. **입력 상한 강제** — 각 필드에 문자 수 상한 명시. 초과 시 로컬에서 잘라낸 후 전송.
4. **불필요 정보 제외** — 해당 Call과 무관한 정보 일절 미포함 (다른 leaf, 전체 매뉴얼 등).
5. **캐시 키** — `SHA-256(call_id + 주요 입력 필드)`. 동일 키 존재 시 API 미호출.

---

## 3. DOM_SPEC — DOM → 기능 명세 초안

### 3.1. 입력 스키마

```
[System]
너는 웹 제품의 DOM 구조를 분석해 기능 명세 초안을 작성하는 전문가야.
ISO/IEC 25010의 기능 적합성(Functional Suitability) 기준으로 leaf 기능 단위까지 분류해.
출력은 반드시 아래 JSON 스키마만 사용해. 자유 텍스트 금지.

[User]
페이지 URL: {url}

DOM 요소 (style·class 제거 후 필터됨):
{dom_elements_json}
```

**입력 필드 제한:**

| 필드 | 포함 내용 | 상한 |
|---|---|---|
| `url` | 페이지 URL | - |
| `dom_elements_json` | `{type, tag, name, id, placeholder, aria-label, text, href}` 배열 | 3,000 토큰 |

**제외 목록 (API 전송 금지):**
- DOM의 style, class, data-* 속성
- 이미지 src, script 내용
- 다른 페이지의 DOM 정보

### 3.2. 출력 스키마

```json
{
  "features": [
    {
      "category_major": "string",
      "category_mid": "string",
      "category_leaf": "string",
      "implicit_spec": "string (1~3문장, 명세 근거 포함)",
      "source_element": "string (근거 DOM 요소명)",
      "confidence": "HIGH | MID | INFERRED"
    }
  ],
  "ambiguous_elements": [
    {
      "element": "string",
      "reason": "string"
    }
  ]
}
```

### 3.3. 토큰 예산

| 항목 | 예상 |
|---|---|
| System + User (고정) | ~200 tok |
| dom_elements_json | ≤ 3,000 tok |
| 출력 | ≤ 2,000 tok |
| **호출당 합계** | **≤ 5,200 tok** |

---

## 4. TC_DESIGN — leaf 기능 → TC 설계

### 4.1. 입력 스키마

```
[System]
너는 ISO/IEC 25023 기반 SW 시험 전문가야.
주어진 leaf 기능 1개에 대해 TC를 설계해.
출력은 반드시 아래 JSON 스키마만 사용해.

설계 원칙:
- source_quote: 매뉴얼 발췌에서 직접 인용. 근거 없으면 "INFERRED: " 접두어 필수.
- 7가지 기법을 가능한 분산: happy_path / equivalence / boundary / negative_basic / negative_deep / state_transition / cross_feature
- TC 수: 최소 3개, 최대 6개
- 사전입력조건 / 기대 출력 값 은 구체적으로 (추상 표현 금지)

[User]
## 대상 기능
대분류: {category_major}
중분류: {category_mid}
소분류(leaf): {category_leaf}
TC ID 시작 번호: {tc_id_start}  (예: TC-003-001부터)

## 관련 매뉴얼 발췌 (최대 1,500자)
{manual_excerpt}

## 관련 결함 패턴 (최대 500자)
{defect_patterns}
```

**입력 필드 제한:**

| 필드 | 포함 내용 | 상한 |
|---|---|---|
| `category_*` | 대/중/소 분류명 | - |
| `tc_id_start` | 이 leaf의 첫 TC ID | - |
| `manual_excerpt` | 이 leaf와 직접 관련된 매뉴얼 섹션만 | **1,500자** |
| `defect_patterns` | 이 기능 유형과 관련된 결함 패턴 요약 | **500자** |

**제외 목록:**
- 다른 leaf의 매뉴얼 내용
- 전체 매뉴얼 (다른 섹션 불필요)
- 이미 생성된 다른 TC 목록
- DOM 구조 전체

### 4.2. 출력 스키마

```json
{
  "tcs": [
    {
      "tc_id": "TC-XXX-YYY",
      "scenario": "string (테스트 시나리오)",
      "precondition": "string (사전입력조건 — 구체적 값 포함)",
      "expected_output": "string (기대 출력 값 — 구체적)",
      "technique": "happy_path | equivalence | boundary | negative_basic | negative_deep | state_transition | cross_feature",
      "source_quote": "string (매뉴얼 직접 인용 or 'INFERRED: 이유')",
      "gen_confidence": 0.0
    }
  ]
}
```

### 4.3. 토큰 예산

| 항목 | 예상 |
|---|---|
| System (고정) | ~400 tok |
| 기능명·TC ID | ~50 tok |
| manual_excerpt | ≤ 750 tok (1,500자 ÷ 2) |
| defect_patterns | ≤ 250 tok |
| 출력 (4TC 기준) | ≤ 2,500 tok |
| **호출당 합계** | **≤ 4,000 tok** |
| **10 leaf 합계** | **≤ 40,000 tok** |

---

## 5. TC_REGEN — V 실패 TC 재생성

### 5.1. 활성 조건

- V1~V5 중 하나 이상 실패
- 최대 재호출 3회 (초과 시 해당 TC에 `INFERRED` 마킹 후 통과)

### 5.2. 입력 스키마

```
[System]
너는 ISO/IEC 25023 기반 SW 시험 전문가야.
아래 TC들이 검증에 실패했어. 지적된 문제점을 고쳐서 재생성해.
출력은 반드시 TC_DESIGN과 동일한 JSON 스키마만 사용해.

[User]
## 실패한 TC 목록
{failed_tcs_json}

## 검증 실패 내용
{v_failures}

## 수정 지침
{fix_instructions}
```

**입력 필드 제한:**

| 필드 | 포함 내용 | 상한 |
|---|---|---|
| `failed_tcs_json` | 실패한 TC만 (통과한 TC 제외) | 1,500 tok |
| `v_failures` | 어떤 V가 왜 실패했는지 | 300 tok |
| `fix_instructions` | 구체적 수정 방향 | 200 tok |

**출력 스키마:** TC_DESIGN과 동일

### 5.3. 토큰 예산

| 항목 | 예상 |
|---|---|
| 합계 | **≤ 4,000 tok/회** |
| 최대 3회 시 | **≤ 12,000 tok** |

---

## 6. FAILURE_ANALYSIS — 실패 TC 원인 분석

### 6.1. 활성 조건

- Stage 5 자동 실행 결과 FAIL인 TC

### 6.2. 입력 스키마

```
[System]
너는 SW 시험 결과 분석 전문가야.
아래 TC가 자동 실행에서 실패했어. 원인을 4축으로 분석해.
출력은 반드시 아래 JSON 스키마만 사용해.

[User]
TC ID: {tc_id}
테스트 시나리오: {scenario}
사전입력조건: {precondition}
기대 출력 값: {expected_output}
실제 출력: {actual_output}
```

**입력 필드 제한:**

| 필드 | 상한 |
|---|---|
| `scenario` | 200자 |
| `precondition` | 300자 |
| `expected_output` | 300자 |
| `actual_output` | 500자 (스크린샷 OCR 포함 시 상한) |

**제외 목록:**
- 다른 TC의 실행 결과
- 전체 TC 목록
- 매뉴얼 전문

### 6.3. 출력 스키마

```json
{
  "actual_output_summary": "string",
  "difference": "string (기대 vs 실제 차이점)",
  "root_cause_candidates": [
    "string"
  ],
  "retry_history": "string (재시도 여부·결과)",
  "exec_confidence": 0.0
}
```

### 6.4. 토큰 예산

| 항목 | 예상 |
|---|---|
| 합계 | **≤ 2,300 tok/TC** |
| 실패 5TC 기준 | **≤ 11,500 tok** |

---

## 7. 전체 토큰 예산 요약 (10 leaf, 페이지 10개, 실패 5TC 기준)

| 단계 | 호출 수 | 토큰 소비 |
|---|---|---|
| DOM_SPEC (10 페이지) | 10 | 52,000 |
| TC_DESIGN (10 leaf) | 10 | 40,000 |
| TC_REGEN (낙관적, 2회) | 2 | 8,000 |
| FAILURE_ANALYSIS (5 TC) | 5 | 11,500 |
| **합계** | **27** | **~111,500 tok** |

**모델별 예상 비용:**

| 모델 | 입력 단가 | 출력 단가 | 예상 비용 |
|---|---|---|---|
| claude-3-haiku | $0.25/M | $1.25/M | ~$0.05 |
| claude-3-5-sonnet | $3/M | $15/M | ~$0.60 |
| claude-3-7-sonnet | $3/M | $15/M | ~$0.60 |

→ **품질 우선: claude-3-5-sonnet 권장** (TC 설계 품질이 핵심)
→ **TC_DESIGN·DOM_SPEC만 sonnet, 나머지는 haiku**로 혼합 사용 가능

---

## 8. 캐시 전략

```python
# tools/cache.py 의사코드
import hashlib, json, os

CACHE_DIR = "data/llm_cache"

def get_cached(call_id: str, inputs: dict) -> dict | None:
    key = hashlib.sha256(
        (call_id + json.dumps(inputs, sort_keys=True)).encode()
    ).hexdigest()
    path = f"{CACHE_DIR}/{key}.json"
    if os.path.exists(path):
        return json.load(open(path))
    return None

def save_cache(call_id: str, inputs: dict, result: dict):
    key = hashlib.sha256(
        (call_id + json.dumps(inputs, sort_keys=True)).encode()
    ).hexdigest()
    json.dump(result, open(f"{CACHE_DIR}/{key}.json", 'w'))
```

**캐시 무효화 조건:**
- manual_excerpt 변경 시
- 모델 변경 시
- Contract 프롬프트 버전 변경 시 (버전 번호를 캐시 키에 포함)

---

## 9. Contract 버전 관리

각 `prompts/*.md` 파일 상단에 버전 헤더:
```
---
contract_id: TC_DESIGN
version: v1.0
model: claude-3-5-sonnet-20241022
max_input_tokens: 4000
max_output_tokens: 3000
---
```

버전 변경 시 기존 캐시 자동 무효화 (버전 번호가 캐시 키에 포함됨).

# LLM Provider 추상화 설계

> AWT는 Anthropic Claude를 기본으로 하되, OpenAI GPT·Google Gemini도 동일 인터페이스로 호출 가능하도록 추상화한다.
>
> **결정 근거:** D48 (LLM provider 정책), D38 (stateless 호출 유지), D41 (토큰 최적화 유지)
> **추가 일자:** 2026-05-20

---

## 1. 목적과 비목적

### 1.1 목적
- **모델 자유 선택** — Contract 단위로 `claude-*`/`gpt-*`/`gemini-*` 중 선택 가능
- **벤더 종속 회피** — 한 vendor의 API 정책·가격 변경에 종속되지 않음
- **품질·비용 비교** — 동일 입력을 여러 모델로 실험해 정량 비교 가능
- **인터페이스 일관성** — Stage 코드는 provider를 모름. `llm_client.call(contract_id, inputs)`만 사용

### 1.2 비목적 (이번 작업 범위 밖)
- LLM 호출 *동시에 여러 provider* 실행해 합의 도출 (ensemble) — Phase 2 이후
- provider별 특수 기능 노출 (예: Anthropic의 prompt caching, Gemini의 long context) — 공통 API만 사용
- 사용자별 model 라우팅 정책 (역할 기반) — 운영 단계 결정

---

## 2. 식별 방식 — 모델명 prefix 자동 라우팅 (D48-A)

```
claude-*     → AnthropicProvider
gpt-*        → OpenAIProvider
gemini-*     → GeminiProvider
o1-*, o3-*   → OpenAIProvider  (reasoning 모델군)
```

**근거:**
1. 기존 `prompts/*.md` 5개 모두 `model: claude-sonnet-4-6` 같이 모델명을 이미 frontmatter에 가짐 → 추가 필드 불필요
2. 업계 표준 명명 규칙과 충돌 없음 (claude/gpt/gemini는 vendor-exclusive prefix)
3. 운영 단계에서 vendor 추가 시 매핑 테이블 1줄 추가로 확장

**예외 처리:**
- 매핑 안 되는 모델명 → `ValueError("Unknown model prefix: <name>")`
- 같은 prefix 내 모델 버전 차이는 provider가 내부에서 처리 (예: `claude-haiku-4-5-20251001` vs `claude-sonnet-4-6`)

---

## 3. 추상 인터페이스

```python
# app/api/providers/base.py
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Provider 공통 인터페이스. 모든 구현체가 이 메서드를 만족해야 한다."""

    name: str  # "anthropic" | "openai" | "google"

    @abstractmethod
    def chat(
        self,
        system: str,           # System prompt
        user: str,             # User message
        model: str,            # 모델명 (예: claude-sonnet-4-6)
        max_tokens: int,       # 출력 토큰 상한
        json_mode: bool = True # JSON 강제 여부 (기본 True)
    ) -> ChatResult:
        """단일 stateless chat 호출. 대화 히스토리 없음 (D38)."""
        ...

@dataclass
class ChatResult:
    text: str              # 응답 본문 (JSON 문자열 또는 plain text)
    input_tokens: int
    output_tokens: int
    model: str             # 실제 응답한 모델명
    raw: dict | None       # provider 원본 응답 (디버그용)
```

**핵심 설계 결정:**
- **stateless 호출만 노출** — `messages: list[dict]` 같은 다중 턴 인터페이스 의도적 배제 (D38 강제)
- **JSON 강제는 provider 책임** — 호출자(`LLMClient`)는 `json_mode=True`만 넘김. provider별 강제 방식 차이를 내부에서 처리

---

## 4. Provider별 JSON 강제 방식 (중요 차이)

| Provider | JSON 강제 메커니즘 | 비고 |
|---|---|---|
| **Anthropic** | system prompt에 "JSON 스키마만 사용" 명시 + 응답 후 ```json 블록 추출 | API에 native JSON mode 없음 (2026-05 기준). prompt 강제 + 파싱 후처리 |
| **OpenAI** | `response_format={"type": "json_object"}` API 파라미터 | 모델이 JSON 외 출력 시 API에서 오류. 강제력 가장 강함 |
| **Google Gemini** | `generation_config={"response_mime_type": "application/json"}` | response_schema도 지원하나 본 추상화에선 mime_type만 사용 |

**합의:**
- `json_mode=True` 시 provider가 알아서 위 방식 적용
- 응답 텍스트는 모두 *공통 JSON 문자열 형태*로 정규화 — 호출자는 차이를 모름

---

## 5. System 메시지 처리 차이

| Provider | system 전달 위치 |
|---|---|
| Anthropic | `messages.create(system="...", messages=[{role:"user", ...}])` |
| OpenAI | `messages=[{role:"system", ...}, {role:"user", ...}]` |
| Gemini | `model.generate_content(contents=[...], system_instruction="...")` |

내부에서 처리. 호출자는 항상 `chat(system=..., user=...)`만 호출.

---

## 6. 토큰 계산 + 비용 표 (호출당 평균 4,000 tok 기준)

| Provider | 모델 | 입력 단가 (per M tok) | 출력 단가 | 4K tok 호출당 |
|---|---|---:|---:|---:|
| Anthropic | claude-haiku-4-5 | $0.80 | $4.00 | ~$0.012 |
| Anthropic | claude-sonnet-4-6 | $3.00 | $15.00 | ~$0.045 |
| Anthropic | claude-opus-4-5 | $15.00 | $75.00 | ~$0.225 |
| OpenAI | gpt-4o-mini | $0.15 | $0.60 | ~$0.002 |
| OpenAI | gpt-4o | $2.50 | $10.00 | ~$0.035 |
| OpenAI | o1-mini | $3.00 | $12.00 | ~$0.045 |
| Google | gemini-1.5-flash | $0.075 | $0.30 | ~$0.001 |
| Google | gemini-1.5-pro | $1.25 | $5.00 | ~$0.018 |
| Google | gemini-2.0-flash | $0.10 | $0.40 | ~$0.0015 |

*가격은 2026-05 기준 공시가. 실 운영 시 vendor 공식 페이지 재확인 필요.*

**기본값 (Contract별):**
| Contract | 권장 model | 사유 |
|---|---|---|
| TC_DESIGN | claude-sonnet-4-6 | TC 품질 핵심. 가성비 최선 |
| TC_REGEN | claude-sonnet-4-6 | 재생성도 동일 품질 필요 |
| DOM_SPEC | claude-sonnet-4-6 | DOM 구조화는 추론 능력 필요 |
| FAILURE_ANALYSIS | claude-haiku-4-5 | 짧은 인과 분석. 저비용 모델로 충분 |
| PATTERN_EXTRACT | claude-sonnet-4-6 | 결함→패턴 추출은 추론 깊이 필요 |

**비용 실험 시나리오:** 모든 Contract를 `gemini-1.5-flash`로 바꾸면 ~30배 절감 가능. 단 품질은 별도 검증 필요 → Phase 2 실험 항목.

---

## 7. 캐시 정책

기존 `app/tools/cache.py`는 그대로 사용. 캐시 키만 확장:

```python
# 기존
key = SHA256(call_id + version + inputs)

# 변경 후
key = SHA256(call_id + version + model + inputs)
```

**근거:** 같은 입력을 다른 모델에 보내면 다른 결과가 나오므로 model이 캐시 키에 포함되어야 한다.

기존 캐시는 model 정보가 없어 자동 무효화 — Phase B 첫 실행 시 LLM 캐시 전체 재구축.

---

## 8. 환경변수

```env
# .env
# Provider 선택 (필수)
LLM_PROVIDER=anthropic   # anthropic | openai | google

# Provider별 API 키 (선택한 provider의 키만 필수)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

**UI 처리 (D48-B):**
- Dashboard에 Provider 드롭다운 (3개 옵션)
- 선택한 provider의 API key 입력란 1개만 노출
- 입력값은 기존 `app/config/settings.py`의 Fernet 암호화 저장소에 그대로 저장 (provider 이름과 함께)

---

## 9. 의존성

```txt
# requirements.txt 추가
openai>=1.50.0
google-genai>=0.3.0   # 신 SDK (구 google-generativeai는 deprecated)
```

**선택 설치 정책:**
- `requirements.txt`에는 셋 다 명시 (모든 환경에서 설치)
- 단, **import는 lazy** — provider 클래스 인스턴스화 시점에만 import. 의존성 없으면 명확한 오류 메시지

```python
# app/api/providers/openai_provider.py
def __init__(self, ...):
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "OpenAI provider requires 'openai' package. "
            "Install: pip install openai>=1.50.0"
        )
    self._client = OpenAI(api_key=...)
```

---

## 10. 회귀 보장

본 작업의 **유일한 PASS 기준**:

1. 기존 5개 Contract (`prompts/*.md`)의 `model: claude-*` 그대로 동작
2. **Mock 파이프라인 회귀**: TC 79개, INFERRED 0%, MANUAL 92.4%/INVARIANT 7.6% 분포 100% 동일
3. `tests/test_v6_selector_stability.py` 36개 전부 PASS
4. 신규 `tests/test_provider_routing.py` PASS — provider 라우팅·system 메시지 변환·JSON 모드 분기

기존 동작이 깨지면 D48 자체를 재검토.

---

## 11. 미해결 — 운영 시 결정

| ID | 질문 | 결정 시점 |
|---|---|---|
| Q-LLM-1 | provider별 token 계산법 차이 (Anthropic·OpenAI는 자체 계산, Gemini는 별도) — V3 INFERRED 임계 적용 시 통일 필요? | Phase 2 운영 |
| Q-LLM-2 | 다중 provider 합의(ensemble) 도입 — TC 품질·결함 검출률 vs 토큰 비용 trade-off | Phase 2 R&D |
| Q-LLM-3 | provider별 캐시 분리 vs 통합 — 같은 입력·다른 모델 결과 비교 시 캐시 정책 | Phase 2 운영 |
| Q-LLM-4 | UI Provider 토글 시 진행 중인 실행 처리 — 중단 vs 완료까지 기존 provider 유지 | Phase 1 UI 다듬기 |

# Stage 0: DOM 스캔 + 기능 명세 초안 합성

**결정 근거:** D32 (DOM 기반 명세 초안 필수), D33 (인증 필요 페이지 스캔 필수)
**활성 조건:** 매뉴얼 또는 기능리스트가 없거나 빈약할 때 (선택 단계)
**산출:** `feature-spec-draft.md` → Stage 1 Ingest의 입력으로 투입

---

## 1. 입력 / 출력

| 항목 | 내용 |
|---|---|
| **입력** | URL (대상 제품 진입점) + 인증 정보 (아이디/비번, 있는 경우) |
| **출력** | `feature-spec-draft.md` (기능 목록 + 암묵적 명세) |
| **보관** | `data/runs/<run-id>/dom-scan/` (동결, 불변) |

---

## 2. 처리 흐름

```
[URL 투입]
    │
    ├─ 인증 필요?
    │      YES → Playwright: 로그인 페이지 접속 → 아이디/비번 입력 → 세션 확보
    │      NO  → 그대로 진행
    │
    ▼
[페이지 스캔 루프]
    • 진입 URL → DOM 수집
    • nav·sidebar·메뉴에서 하위 URL 링크 추출
    • 각 URL 방문: form·input·button·modal·table·alert 수집
    • 방문 depth 상한: 2 (설정 가능)
    │
    ▼
[요소 분류]
    • input[type=text/password/email/file] → 입력 필드 명세
    • button / a[role=button] → 액션 명세
    • form → 제출 흐름 명세
    • table / list → 데이터 노출 명세
    • alert / toast / modal → 피드백 명세
    │
    ▼
[LLM 합성 prompt]
    • 수집된 DOM 요소 목록 + 페이지 구조를
      "기능 명세 초안"으로 변환
    • 출력: 대분류 / 중분류 / 소분류(leaf) + 암묵적 명세 문장
    │
    ▼
[feature-spec-draft.md 저장]
    → Stage 1 Ingest에 "매뉴얼 대체 입력"으로 투입
```

---

## 3. 인증 시퀀스 (D33)

```python
# 의사코드 — Playwright MCP 호출
page.goto(login_url)
page.fill('input[name=username]', user_id)    # 실행 시 사용자 입력
page.fill('input[name=password]', password)   # 실행 시 사용자 입력
page.click('button[type=submit]')
page.wait_for_load_state('networkidle')
# 세션 쿠키 유지 → 이후 모든 스캔에 적용
```

**보안 원칙:**
- 인증 정보는 실행 시점에 사용자가 직접 입력 (하드코딩 금지)
- 세션 정보는 `data/runs/<run-id>/dom-scan/` 외부 저장 금지
- PoC 단계에서는 `file://` 로컬 파일로 대체 가능 (인증 불필요)

---

## 4. LLM 합성 prompt 구조 (초안)

```
[System]
너는 웹 제품의 DOM 구조를 분석하고 기능 명세 초안을 작성하는 전문가야.
ISO/IEC 25010 품질 특성 중 기능 적합성(Functional Suitability)을 기준으로
leaf 기능 단위까지 분류해.

[User]
다음은 URL별 DOM 요소 수집 결과야:
---
{dom_elements_json}
---

다음 형식의 기능 명세 초안을 작성해:
1. 대분류 / 중분류 / 소분류(leaf) 계층 표 (CSV 형식)
2. 각 leaf 기능의 암묵적 명세 문장 (1~3줄) — 근거는 DOM 요소 이름·위치
3. 불명확한 기능은 "INFERRED:" 접두어 표시

출력 형식: Markdown (## 헤더로 섹션 구분)
```

---

## 5. 스캔 범위 설정 파라미터

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `max_depth` | 2 | 링크 탐색 깊이 (1: 진입 페이지만, 2: 1단 이하까지) |
| `max_pages` | 30 | 최대 스캔 페이지 수 |
| `auth_required` | false | 인증 시퀀스 활성 여부 |
| `scan_forms` | true | form 요소 수집 |
| `scan_nav` | true | nav/sidebar 링크 수집 |
| `screenshot` | true | 페이지별 스크린샷 저장 (`dom-scan/screenshots/`) |

---

## 6. Stage 0 → Stage 1 연결

Stage 0 산출 `feature-spec-draft.md`는 Stage 1에서 다음과 같이 소비됨:

| Stage 1 입력 | Stage 0 대응 |
|---|---|
| `input/manual.md` | `dom-scan/feature-spec-draft.md` (섹션 §2 이후) |
| `input/feature-list.csv` | `dom-scan/feature-list-draft.csv` (대/중/소 3컬럼 자동 추출) |

→ 사용자가 `feature-spec-draft.md`를 검토·수정 후 Stage 1에 투입하는 것을 권장 (게이트 없이 자동 통과도 옵션).

---

## 7. 미해결 (PoC 후 결정)

| 항목 | 현재 가정 | 결정 시점 |
|---|---|---|
| SPA(React/Vue) 동적 렌더 처리 | `waitForSelector` 로 lazy load 대기 | Stage 0 구현 시 |
| iframe 내 DOM 접근 | 현재 스코프 외 — 별도 처리 필요 | Stage 0 구현 시 |
| 무한 스크롤 목록 | 2~3회 scroll 후 중단 | Stage 0 구현 시 |
| LLM 합성 prompt INFERRED 임계 | Stage 3 V3 기준 동일 적용 여부 | Stage 0 구현 시 |

---

## 8. PoC-δ (Stage 0 검증)

> PoC-α/β/γ 완료 후 별도 PoC-δ에서 Stage 0 단독 검증 예정.

**PASS 기준:**
- DOM 수집된 기능 중 ≥ 80% 가 Stage 2 TC에 반영됨
- 인증 필요 페이지에서 세션 유지 성공
- INFERRED 마킹 된 명세가 reviewer에게 명확히 식별됨

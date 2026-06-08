# doc/ — AWT 설계 문서

AWT 프로젝트의 **모든 설계 결정의 단일 출처**. 구현은 이 문서들이 합의된 이후에만 시작한다 (개발 지침 1).

---

## 핵심 문서

| # | 파일 | 내용 | 읽는 순서 |
|---|---|---|---|
| 1 | [01-architecture.md](01-architecture.md) | 전체 흐름 (Stage 0~7) + 데스크탑 앱 구조 + 인증 + Playwright | **시작점** |
| 2 | [02-llm-contracts.md](02-llm-contracts.md) | LLM 호출 5종 Contract + 토큰 예산 + 캐시 | 01 이후 |
| 3 | [03-tc-schema.md](03-tc-schema.md) | TC 컬럼·타입·7기법·V1~V5 검증 | 01 이후 |
| 4 | [04-iso-mapping.md](04-iso-mapping.md) | ISO/IEC 25010/25023/25051/25059 × Layer 분류 | 참조용 |
| 5 | [05-poc-plan.md](05-poc-plan.md) | PoC-α/β/γ 계획 + 진행 상황 | 진행 중 |
| 6 | [06-decisions.md](06-decisions.md) | D1~D48 확정 + 미해결 질문 (주제별) | 참조용 |
| 7 | [07-llm-providers.md](07-llm-providers.md) | LLM provider 추상화 (Anthropic/OpenAI/Gemini) | 02 보완 |
| 8 | [08-feature-list-refinement.md](08-feature-list-refinement.md) | 기능 리스트 정제 & 확정 게이트 (로그인 편중 해소, D51~D53) | 03 보완 |
| 9 | [09-tc-grouping-and-performance.md](09-tc-grouping-and-performance.md) | TC 그룹핑 & 파이프라인 성능 (생성 6.9h→<1h, D54~D56) | 03 보완 |
| 10 | [10-reviewer-gate-v2.md](10-reviewer-gate-v2.md) | Reviewer Gate v2 (검토 부담↓·가독성↑, D57~D58) | 03 보완 |
| — | [AWT_장점분석.md](AWT_장점분석.md) | 기본 접근법(LLM 직접 요청) 대비 AWT 장점 — 항목별 상세 분석 | 소개·발표용 |

---

## 현재 상태 (2026-05-19)

- **PoC-α 완료** — `data/poc/2026-05-19/output/tc_review.xlsx` 산출
- **PoC-β 대기** — 사용자 검토 중
- **PoC-γ 예정** — β 통과 후
- **Phase 1 (Desktop App 개발) 진입 대기** — PoC γ 통과 후

---

## archive/

D25 이전 가정에 기반한 문서 + 통합 전 세부 자료. 보존하되 *직접 참조 금지* (D37 이후 무효한 부분 다수).

| 폴더 | 보존 사유 |
|---|---|
| `01-theory/` | 4인 토론 (초기 의사결정 근거) |
| `02-iso-25023-mapping/` | Layer 매트릭스 상세 (요약은 04-iso-mapping.md) |
| `03-architecture/` | 단계별 설계 변천 (D25→D37 pivot 기록) |
| `04-tc-design-spec/` | 통합 전 TC 스키마 (현재는 03-tc-schema.md) |
| `05-deployable-skills/` | 빈 골격만 |
| `00-overview/`, `06-risks…`, `07-roadmap.md` | 미작성 또는 통합됨 |
| `08-open-questions.md` | 시간순 결정 누적 원본 (주제별은 06-decisions.md) |

---

## 작성 원칙

- **설계 우선 동결** — 합의된 결정은 변경 시 ID 추가 (예: D25 → D37) + 원 결정 ~~취소선~~
- **추적 가능** — 모든 결정은 근거 문서로 trace 가능
- **단일 진입점** — 본 README가 모든 문서로 향하는 유일한 index

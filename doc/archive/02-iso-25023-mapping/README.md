# 02-iso-25023-mapping/ — ISO/IEC 25023 매핑 + 자동화 가능성 분류

ISO/IEC 25023(품질측정)·25051(COTS 품질)·(검토 중인) 25059(AI 시스템 품질) 표준이 정의하는 품질 메트릭을 AWT의 자동화 가능성으로 분류하고, 각 메트릭의 *operational definition*과 인간 검증이 필요한 영역의 워크플로를 정의한다.

**가장 핵심적인 산출물.** 표준의 어떤 부분을 AI가 다룰 수 있고 어떤 부분을 인간이 다뤄야 하는지에 대한 시험소 내부의 공식 입장 (D6: 외부 audit 강제 아님, 내부 신뢰 기준).

## 파일

- `01-characteristics-matrix.md` — ISO/IEC 25010 8특성 × 25023 메트릭 × Layer1/2/3 매트릭스 (마스터 표)
- `02-automatable.md` — Layer 1 (AI 풀 자동) 영역 상세 — 기능적 적합성 일부, 신뢰성 일부, 성능 등
- `03-semi-automatable.md` — Layer 2 (AI 보조 + 인간 검토) 영역 상세 — 콘텐츠 정합성, 일부 접근성
- `04-human-only.md` — Layer 3 (인간 전담) 영역 상세 — 사용성, 미적, 도메인 비즈니스 룰, 보안 심층, 탐색적
- `05-curation-workflow.md` — Layer 2 검토자 워크플로 (AI TC를 어떻게 읽고 승인/거절/수정)
- `06-deep-areas.md` — Layer 3 심층 시험 절차 (heuristic evaluation, 스크린리더, 콘텐츠 검수 등)
- `07-exploratory-charter.md` — 탐색적 시험 charter 양식과 운영 방식
- `08-metric-definitions.md` — 각 25023 메트릭의 측정식과 산출 절차 (operational definition)

## 분류 원칙

"자동화 가능"의 기준 — **모두 충족 시**:
1. 메트릭이 객관적 기준으로 측정 가능 (인간 인지 불요)
2. Oracle을 명세(매뉴얼/기능리스트)에서 도출 가능
3. False PASS/FAIL 위험이 confidence score로 정량화 가능
4. 재현성·추적성 강제 가능

위 4조건 중 하나라도 미충족 → Layer 2 또는 Layer 3.

# 03-architecture/ — 시스템 아키텍처

AWT의 *어떻게* 동작하는지. 멀티에이전트 분업, 데이터 흐름, RAG 구조.

## 파일

### As-Is (현행 파악)
- `00-existing-method-interview.md` — 사용자 인터뷰 기반 기존 시험방법 정리 + 9개 핵심 사실(F1~F9)
- `00b-gap-analysis.md` — 8대 원칙 × 현행 매트릭스, Phase 1 강화 5종 (E1~E5), Gate 모델 (D22)

### To-Be (강화 설계)
- `01-high-level.md` — 입력 → 처리 → 산출 전체 흐름도 (Stage 0~7, D32·D33 반영)
- `02-multi-agent-design.md` *(Phase 2)* — TC 생성 agent / 실행 agent / oracle 검증 agent / 보고서 agent 분업
- `03-data-flow.md` — 데이터 흐름 상세
- `04-rag-design.md` *(Phase 2)* — 익명화 파이프라인, vector DB 구조, 결함 패턴 추출
- `05-prompt-augmentation.md` — **E1·E2 강제 prompt 템플릿 + 5단계 검증 + selective rerun 통합** (Phase 1.1·1.2)
- `06-poc-validation-plan.md` — **PoC 검증 계획서 (Phase 1.0)**
- `07-prompt-augmentation-e3e4.md` *(PoC 후 작성)* — E3·E4 강제 (oracle 근거 + confidence score)
- `08-stage0-dom-scan.md` — Stage 0 DOM 스캔 + 기능 명세 초안 합성 설계 (D32·D33)
- **`09-desktop-app-design.md`** — **프로덕션 Desktop App 전체 아키텍처 (D37~D43)** ← 신규
- **`10-llm-call-contracts.md`** — **LLM 호출 정형화 + 토큰 최적화 설계 (D38·D41)** ← 신규

## 설계 제약

- **모든 agent는 stateless하게 호출 가능** — 재현성 보장
- **상호 검증** — oracle 검증 agent는 TC 생성 agent의 산출을 *모르고* 매뉴얼만 보고 판정 근거를 별도 도출 → 일치하지 않으면 인간 review
- **RAG은 read-only** — 신제품 시험 중 RAG에 쓰지 않음 (사후 별도 익명화·정제 단계에서만 추가)

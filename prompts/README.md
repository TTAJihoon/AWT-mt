# prompts/ — Multi-agent Prompt 템플릿

> **상태:** 비어 있음 — 구현 단계에서 채움

각 agent의 prompt 템플릿을 버전 관리한다. Prompt는 AWT의 *실질적 비즈니스 로직*이므로 코드와 동등하게 git 추적된다.

## 예정 구조 (설계 확정 후)

- `tc-generator/` — TC 생성 agent
- `executor/` — 자동 실행 agent
- `oracle-verifier/` — 판정 검증 agent (TC 생성과 분리된 독립 oracle)
- `reporter/` — 보고서 작성 agent
- `curator-helper/` — Layer 2 검토자 보조 agent

각 prompt에는 모델 버전·temperature·seed 등 재현성 메타데이터를 frontmatter로 명시.

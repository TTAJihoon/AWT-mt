---
name: awt-poc
description: AWT 프로젝트의 PoC 단계 — Claude Code 환경에서 prompt 품질 검증용. ISO/IEC 25023/25051/25059 기준 웹 SW 시험인증 자동화의 TC 설계·검증 흐름을 시뮬레이션. 사용자가 "AWT PoC 진행", "TC 생성 시뮬레이션", "샘플 게시판으로 시험" 등을 요청할 때 사용.
status: poc-dev-only
---

# AWT Skill (PoC 환경 전용)

> **주의 (D37):** 본 SKILL.md는 **PoC 환경 전용**이다. 프로덕션 = Python 데스크탑 앱 (.exe). 자세한 내용은 [doc/01-architecture.md](doc/01-architecture.md) 참조.
>
> 이 skill은 *프로덕션 배포 대상이 아니다*. Phase 1 본 개발 진입 시 본 skill의 prompt 본문이 `prompts/` 디렉터리에 그대로 이식된다.

---

## 정체성

- **PoC 단계 (현재):** Claude Code 환경에서 prompt 품질 검증
- **프로덕션 (Phase 1+):** Python 데스크탑 앱이 동일 prompt를 Anthropic API로 직접 호출

본 skill은 PoC 산출물(`data/poc/<date>/`)을 생성하는 데 사용. 사용자 reviewer가 결과를 검토해 prompt 품질을 판단.

---

## Trigger 시나리오

- "AWT PoC 진행해줘"
- "샘플 게시판으로 TC 생성 시뮬레이션"
- "PoC-α 다시 실행"

---

## 입력 요구

PoC 단계에서는 합성 mockup 사용:
- 매뉴얼: `data/poc/<date>/sample-board/input/manual.md`
- 기능리스트: `data/poc/<date>/sample-board/input/feature-list.csv`
- URL: `data/poc/<date>/sample-board/input/url.txt`
- 결함 샘플: `data/poc/<date>/sample-board/input/defect-samples.md`

---

## 동작 단계 (PoC 시뮬레이션)

1. **Stage 1 Ingest** — 합성 입력 파일 파싱
2. **Stage 2 TC Design** — 매뉴얼 + 기능리스트 → TC 41개 생성
3. **Stage 3 Verify** — V1~V5 자동 검증
4. **Stage 4 Gate (β)** — `tc_review.xlsx` 산출 후 사용자 검토 대기
5. **Stage 5 Execute (γ)** — Playwright MCP로 자동 실행 시뮬레이션
6. **Stage 6 Enhance** — 실패 TC에 failure_reason 보강
7. **Stage 7 Output** — 최종 Excel 산출

> Stage 0 (DOM 스캔)은 PoC mockup이 너무 단순해 활성화 불요. 실제 OSS 시험 시 활성.

---

## 산출물 위치

- `data/poc/<date>/output/tc_raw.csv` — Stage 2 산출
- `data/poc/<date>/output/tc_review.xlsx` — Stage 4 게이트용
- `data/poc/<date>/output/analysis.md` — AWT 자체 평가
- `data/poc/<date>/output/v_meta.json` — 메타 통계
- `data/poc/<date>/result.md` — 사용자 검토 종료 후 직접 작성

---

## 프로덕션 (Phase 1) 진입 가이드

PoC γ 통과 후 본 skill을 *해체*하고 데스크탑 앱으로 이식:

1. 본 skill의 prompt 본문 → `prompts/*.md` 로 이동
2. 본 skill의 동작 흐름 → `app/core/orchestrator.py` 로 이식
3. Claude Code MCP 호출 → 로컬 Python (anthropic SDK + playwright)으로 교체

설계 근거: [doc/01-architecture.md §10](doc/01-architecture.md), [doc/02-llm-contracts.md](doc/02-llm-contracts.md)

---

## 전체 설계 진입점

- [doc/README.md](doc/README.md) — 설계 문서 진입점
- [CONTINUE.md](CONTINUE.md) — 다른 PC에서 이어 작업 시

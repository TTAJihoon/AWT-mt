# 로드맵

> **갱신:** 2026-05-18 — Gap analysis(`doc/03-architecture/00b-gap-analysis.md`)에 따라 단기 단계를 구체화.

## 원칙

- D12: **1개 동시 시험을 정확히 동작**시키는 게 1차 목표 (Phase 1)
- D11: 기존 Claude Code 시험방법 skill을 *교체하지 않고 강화*
- D6: 외부 audit 통과가 아닌 **시험원 reviewer 신뢰** 확보가 진짜 목적

## Phase 1 — 단일 제품 정확성 (3~6개월)

Gap analysis의 E1~E5를 순차 도입. 각각이 *독립적으로 가치 발생* 가능 — 한 번에 다 안 해도 됨.

| 단계 | 강화 | 종료 조건 | 측정 |
|---|---|---|---|
| 1.1 | **E1: source_quote 강제** — TC 생성 prompt에 requirement_id + source_quote 출력 강제, grep 검증 reject loop | TC 100%가 grep 검증 통과 또는 명시적 INFERRED 표시 | grep 통과율, INFERRED 비율 |
| 1.2 | **E2: TC 설계 기법 prompt 강제** — 등가분할/경계값/negative depth/상태전이/cross-feature 명시 요구 | 1개 제품 TC 수 100~200 → 200~500, CRUD 외 분류 비율 ≥ 40% | 기법별 TC 수 분포 |
| 1.3 | **E3: Oracle 근거 + 실패 원인 자동 기록** | FAIL TC 100%에 failure_reason 4축(실제출력/차이/원인후보/재시도이력) 기록 | FAIL TC 중 reviewer가 *추가 조사 필요*로 판정한 비율 |
| 1.4 | **E4: Confidence score** — gen/exec confidence 2종 산정 | 모든 TC가 두 가지 confidence 값 보유, 분포가 목표(≥0.9 60%↑, <0.4 ≤3%) 충족 | confidence 분포 |
| 1.5 | **E5: Reviewer Gate (자동실행 *이전*)** — Excel review 컬럼 + confidence 정렬 + 색상 하이라이트 + 승인된 TC만 실행 단계 진입 (D22) | 사용자 본인이 *제품 1개에 대해 Gate 사이클 완주*, 잘못된 TC가 실행 전 차단되는 사례 확인 | reviewer 시간/TC 평균 (target: D20 30s~2min), Gate 차단율 |
| 1.0 | **선행: Q-INT-5 검증** — 기존 skill이 TC 생성과 자동실행을 분리 호출 가능한지 실증 | (a)(b)(c) 중 작동 옵션 확정 | 옵션별 PoC 결과 |

**Phase 1 완료 기준:** 사용자가 직접 reviewer로 *제품 1개를 처음부터 끝까지 검토 + 결재*하고, 그 결과를 *믿을 수 있다*고 진술.

## Phase 2 — 신뢰성 심화 (6~18개월)

| 단계 | 강화 | 효과 |
|---|---|---|
| 2.1 | **Multi-agent 분업** — TC 생성 agent와 oracle 검증 agent 분리, 불일치 시 reviewer 우선 |  Hallucinated assertion 차단 |
| 2.2 | **TC 메타 측정 자동** — acceptance rate, augmentation rate, mutation score 누적 | AWT 자체의 품질 추이 가시화 |
| 2.3 | **25023 메트릭 % 자동 계산** — 내부 품질관리용 (외부 산출 여부는 별도 결정) | 시험소 내부 KPI 정립 |
| 2.4 | **RAG 본격화** — 누적 결함 익명화 (L1+L2 자동, L3+L4 수동) + vector 검색 | 신제품 TC 품질 ↑ |
| 2.5 | **분리 배포 sub-skill 1~2개 외부 공개** | 시험소 R&D 가치 외부 전달 |

## Phase 3 — 확장 (18개월+)

- **25059 도입** — AI 포함 제품 한정 sub-mapping (D15)
- **제품군별 specialized agent** — 웹 외 SW로 확장 (D7)
- **병렬 10+ 동시 시험** (D12 이후)
- **결함 재현 자동화** — 사람이 발견한 결함을 최소 재현 TC로 변환 (4인 토론 R5)

## 비-단계 작업 (지속)

- `doc/`의 결정 누적 (08-open-questions.md)
- 인터뷰 결과를 반영한 prompt template 진화 (`prompts/` 폴더 시작)
- 결함 샘플 문서 → 익명화 누적 데이터로 단계적 이관 (`data/` 폴더 시작)

# AWT-claude 브랜치 개선 제안

본 폴더는 `github.com/TTAJihoon/AutoWebTesting` 의 `AWT-claude` 브랜치 코드를 분석한 후, 별도 검토 그룹에서 도출한 *TC 생성 품질 향상* 관련 권고사항을 정리한 자료다.

## 누가, 왜

`AutoWebTesting` 의 다른 검토 그룹에서 *LLM 기반 자동 TC 생성의 생산밀도 문제* 를 다회 연구토론으로 분석했다. 그 과정에서 AWT-claude 브랜치의 prompts/, doc/, PoC 산출물을 자세히 검토했고, *Phase 1 진입 결정 전에* 공유할 가치가 있는 관찰과 권고가 정리되었다.

본 자료는 *명령이 아니라 관점 제공*. 각 권고는 근거와 함께 제시되며, 채택·각색·기각은 AWT-claude 팀의 판단에 맡긴다.

## 읽는 순서

**긴급도 우선 (30분 이내)**

1. `00-summary.md` — 핵심 5분 요약
2. `01-gap-analysis.md` — 현재 코드의 직접 분석 (prompts/, doc/, PoC 결과)
3. `06-questions-to-resolve.md` — 본 분석이 답하지 못하고 AWT-claude 팀이 답해야 할 결정

**배경·근거 필요 시**

4. `02-density-problem.md` — 왜 *생산밀도* 가 본질 문제인가
5. `03-seven-design-assets.md` — 갭을 메우는 7가지 자산 (스키마 포함)
6. `04-incremental-implementation.md` — 자산을 Stage 0~7에 어떻게 추가할 것인가
7. `05-foundational-frameworks.md` — 4계층 차별점 / L0~L3 oracle 분류 / 토큰 절감 견적

## 핵심 메시지 (한 줄)

> **AWT-claude는 *4 LLM contract + V1~V5 검증* 으로 구조 강제는 잘 됐다. 그러나 *자산화 시스템* 자체가 설계에 없다.** Phase 1 진입 전 *결함 카탈로그 + invariants 채널 + selector 점수* 셋만 추가하면 본질적으로 다른 도구가 된다.

## 톤과 한계

- 본 분석은 *외부 시점* 이라 AWT-claude의 *암묵적 제약*(인력 배치, 일정, 정책)을 다 모름
- 일부 권고는 D38(stateless) 같은 합의된 결정과 *부분 충돌* 할 수 있음 → 절충안 제시
- "이게 옳고 저게 틀렸다" 가 아니라 "이런 trade-off가 있다" 의 형식

## 본 제안의 출처

본 폴더의 모든 문서는 *AutoWebTesting* 다른 검토 그룹의 9회차 연구토론 결과를 *AWT-claude 브랜치에 적용 가능한 형태로 재구성* 한 것이다. 원본 토론 산출물은 검토 그룹 내부의 `agenda/01-08.md` 에 보관되어 있다.

본 제안에 대한 회신·반박·각색안은 환영. 채택 여부와 무관하게 *왜 채택 안 했는지* 정도의 회신은 본 분석의 *다음 라운드* 에 유용한 입력이 된다.

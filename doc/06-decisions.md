# 결정 누적 + 미해결 질문

> 시간순이 아닌 *주제별*로 재정렬. 폐기·대체된 결정은 ~~취소선~~ + 대체 ID 표시.
> 시간순 원본은 [archive/08-open-questions.md](archive/08-open-questions.md) 참조.

---

## 1. 적용 범위 + 표준

| ID | 결정 | 일자 |
|---|---|---|
| D1 | AI agent 역할 = TC 설계 + 자동 실행 + 결과 판정 (end-to-end) | 2026-05-18 |
| D2 | 자동화 가능한 ISO/IEC 25023 특성부터 모두 적용, 나머지는 Layer 분류 | 2026-05-18 |
| D7 | 대상 제품군 (Phase 1) = 웹 제품 | 2026-05-18 |
| D8 | 적용 표준 = 25023:2016 + 25051:2014 즉시 적용 | 2026-05-18 |
| D15 | 25059:2023 = AI 제품에만 조건부 적용 | 2026-05-18 |
| D12 | 병렬도 = Phase 1은 1개 동시 시험 정확 동작 우선 | 2026-05-18 |
| D21 | 25023 메트릭 % 산출 = Phase 2에서 결정 (내부 KPI용) | 2026-05-18 |

---

## 2. 구현 형태 (가장 핵심 — 여러 차례 pivot)

| ID | 결정 | 일자 |
|---|---|---|
| ~~D5~~ | ~~Skill 패키징 = `SKILL.md` 1개 + sub-skill~~ → D11로 변경 후 D25 → 최종 D37 | 2026-05-18 |
| ~~D11~~ | ~~AWT = 기존 skill의 강화 layer~~ → D25로 대체 | 2026-05-18 |
| ~~D25~~ | ~~AWT = standalone Claude Code skill~~ → D37로 보완 (PoC용으로만 유지) | 2026-05-19 |
| **D37** | **프로덕션 = Python 데스크탑 앱. Claude Code = PoC·개발 환경 전용** | 2026-05-19 |
| D34 | 배포 대상 = Windows 사용자 전체, 단독 .exe | 2026-05-19 |
| D35 | 구현 = Python GUI (PyQt5/PySide6) + Anthropic SDK. Electron 기각 | 2026-05-19 |
| D43 | Stage 0~7 오케스트레이션 = 로컬 Python orchestrator.py | 2026-05-19 |

---

## 3. 인프라 스택

| ID | 결정 | 일자 |
|---|---|---|
| D44 | 중앙 인증 DB = **PostgreSQL** (향후 로그·통계 확장 고려) | 2026-05-19 |
| D45 | UI 프레임워크 = **PySide6** (LGPL — 상용 배포 무료, Qt6 공식 바인딩) | 2026-05-19 |
| D46 | Windows 설치 패키지 = **Inno Setup** (Python/PyInstaller 레퍼런스 풍부, 무료) | 2026-05-19 |
| **D48** | **LLM provider = Anthropic 기본 + OpenAI/Gemini 선택 가능. 모델명 prefix(`claude-*`/`gpt-*`/`gemini-*`)로 자동 라우팅. provider별 API 키는 `.env`에 분리 저장. UI는 단일 provider 선택. D38(stateless)·D41(토큰 최적화) 유지. 상세: [doc/07-llm-providers.md](07-llm-providers.md)** | 2026-05-20 |
| **D49** | **negative_category 5enum 정의 + V10 강제** — `validation_failure`/`duplicate_or_conflict`/`permission_denied`/`boundary_violation`/`injection_or_security`. 외부 제안 #4 채택. leaf 적용 가능 카테고리 중 ≥ 60% 충족, 각 카테고리당 ≥ 1 TC. 상세: [doc/03-tc-schema.md](03-tc-schema.md) §7 | 2026-05-20 |
| **D50** | **failure_category 5enum 정의** — `selector_broken`/`scenario_error`/`expected_mismatch`/`real_defect`/`fictional_positive`. 외부 제안 #5 채택. V6 정적 분석 + LLM 동적 분석 통합 (V6 우선, 충돌 시 merged). 상세: [doc/03-tc-schema.md](03-tc-schema.md) §6 | 2026-05-20 |

---

## 5. 인증·보안

| ID | 결정 | 일자 |
|---|---|---|
| D40 | 로그인 = 중앙 DB 서버 인증. 처리(API·Playwright)는 로컬 | 2026-05-19 |
| D42 | API 키 = 사용자별 개인, 머신 고유 키 기반 Fernet 암호화 로컬 저장 | 2026-05-19 |
| D33 | Stage 0 인증 = 실행 시점에 사용자가 아이디/비번 입력. 하드코딩 금지 | 2026-05-19 |

---

## 6. LLM 호출 + 토큰 최적화

| ID | 결정 | 일자 |
|---|---|---|
| D38 | LLM = stateless Anthropic API 호출. 대화 히스토리 없음 | 2026-05-19 |
| D41 | 토큰 절약 = ① per-leaf 처리 ② 발췌 투입 ③ JSON Schema 강제 ④ 캐시 | 2026-05-19 |
| D39 | Playwright = 로컬 Python 라이브러리. 설치 패키지에 chromium 포함 | 2026-05-19 |
| D24 | 실행 도구 = Claude Code Playwright MCP (PoC 한정) → D39로 프로덕션 변경 | 2026-05-18 |

---

## 7. TC 설계 + 워크플로

| ID | 결정 | 일자 |
|---|---|---|
| D9 | TC ID 형식 = `TC-XXX-YYY` (D17·D18·D19로 세부 확정) | 2026-05-18 |
| D17 | XXX = 최하위 분류(leaf)의 일련번호 | 2026-05-18 |
| D18 | YYY = 3자리 고정 (999까지) | 2026-05-18 |
| D19 | Cross-feature TC = 주된 기능에 귀속, 별도 prefix 없음 | 2026-05-18 |
| D10 | TC 작성 양식 = 시험소 표준 layout 사전 제공, AI는 그 양식으로만 출력 | 2026-05-18 |
| D6 | 신뢰 프레임 = 외부 audit 아님. source_quote는 *내부 reviewer 신뢰* 확보 수단 | 2026-05-18 |
| D22 | Reviewer Gate = 자동실행 *이전* 위치 (사전 게이트 모델) | 2026-05-18 |
| D20 | Reviewer 시간 budget = TC 1개당 평균 30초~2분 | 2026-05-18 |
| D23 | 재시험 = 기존 TC 결과 첨부하여 부분 재실행 | 2026-05-18 |
| D30 | E1~E5 (5종 강화) = AWT 핵심 기능 (외부 강화가 아닌 자체 기능) | 2026-05-19 |
| D32 | Stage 0 (DOM → 명세 초안) = 필수 기능 | 2026-05-19 |
| **D51** | **전역 컴포넌트 dedup** — 헤더·푸터·네비 등 ≥`GLOBAL_RATIO`(**0.4**, 실측 로그인 49.4%라 0.5면 놓쳐 보정) 페이지에 동일 셀렉터 지문으로 반복되는 요소를 `__global__`로 1회만 명세. 규칙 기반(LLM 불필요), 손실 0(이동), `dedup_global_components` 옵트아웃. 로그인 편중(인증 도메인 ~30%)의 1순위 원인 직격. **구현·검증 완료**(단위+통합 테스트). 상세: [doc/08-feature-list-refinement.md](08-feature-list-refinement.md) §3 | 2026-06-02 |
| **D52** | **카테고리 통제 어휘(taxonomy)** — `category_major`를 고정 **12종**(회원·인증/게시판·콘텐츠/검색·필터/네비게이션·메뉴/UI·접근성/결제·쇼핑/폼·입력검증/알림·고객지원/관리자/정보표시·정책/설정·환경/기타) 중 선택 강제. `app/core/taxonomy.py` 단일 정의 + dom_spec·feature_consolidate 프롬프트 주입 + `coerce_major` 후보정(unknown은 원본 유지·기록, 손실 0). **구현·검증 완료**: 실측 436종→97.7% 통제 흡수, 인증 분열(User Management/Authentication/Account Management)이 단일 "회원·인증"으로 통합. major만 통일되므로 깊은 병합은 D85와 상보. 상세: [doc/08-feature-list-refinement.md](08-feature-list-refinement.md) §3 | 2026-06-02 |
| **D53** | **기능 확정 게이트** — Stage 1b 후 Stage 2 진입 전, 대분류(D52)별 집계 + 선택적 leaf 제외(`app/ui/feature_gate.py`). opt-in(`RunConfig.feature_gate`, 기본 OFF)·무조작 통과(회귀 없음). **구현 완료**(트리 제외 검증). 도메인 TC 예산은 D53b로 분리(D54와 함께). 상세: [doc/08-feature-list-refinement.md](08-feature-list-refinement.md) §3 | 2026-06-02 |
| **D54** | **Leaf 그룹핑 최적화** — (A) **구현 완료**: 신규 TC_DESIGN_GROUP으로 source_url(페이지) 그룹+cap12 단위 설계, leaf_index 매핑. 기존 TC_DESIGN 유지(V10·재생성 무손상). 검증: 5leaf/2페이지→2호출. (B) **교차 페이지 플로우(TC_FLOW)** — **구현 완료**: 도메인별 사이트 요약 1회 입력→여정 최대 15개(TC-FLOW-NNN, cross_feature). 도메인 넘나드는 흐름(로그인→글쓰기) 포함. cap=12·동시성=6·Qt signal 확정. 상세: [doc/09-tc-grouping-and-performance.md](09-tc-grouping-and-performance.md) §2 | 2026-06-02 |
| **D55** | **LLM 호출 병렬화** — **구현 완료**: stage2 그룹·V10 보완 배치를 `ThreadPoolExecutor(RunConfig.concurrency 기본6)` 동시 실행. llm_client Lock으로 스레드 안전(provider/RPM/캐시/로그), 결과 입력순 병합→결정성 유지. `concurrency=1`이면 순차(회귀 없음). 검증: 8그룹 2.7x↑·결과 동일. (stage0/stage6 병렬화는 후속) 상세: [doc/09-tc-grouping-and-performance.md](09-tc-grouping-and-performance.md) §2 | 2026-06-02 |
| **D56** | **V10 보완 재설계** — **구현 완료**: 신규 TC_V10_GROUP으로 gap leaf를 페이지 배치 그룹 호출(777→수십), 증식 상한 6/leaf, screenshot_file 전파(D58 누락 동시 해결). 선제 충족은 D54-A가 담당. 병렬화는 D55. D49 기준 유지. 검증: 5gap/2페이지→2호출. 상세: [doc/09-tc-grouping-and-performance.md](09-tc-grouping-and-performance.md) §2 | 2026-06-02 |
| **D57** | **Reviewer Gate 리스크 triage** — TC를 **위험점수**(gen_confidence 주축 + source/기법/민감도 보정)로 🔴집중(<0.45)/🟢안전(≥0.75)/🟡확인 3버킷 자동 분류. **source 의존 배제** — 참고문서 없는 DOM-only도 신뢰도·기법으로 동작(실측 🔴 34%, 100% 아님). 🟢 일괄승인+🔴 집중+위험군 진행률로 "꼭 정독" 100%→~1/3. 필터·정렬·"왜 검토하나" 배지·임계값 노출. 상세: [doc/10-reviewer-gate-v2.md](10-reviewer-gate-v2.md) §3 | 2026-06-02 |
| **D58** | **Reviewer Gate 상세 패널 강화** — **구현 완료**: 더블클릭 팝업을 failure_detail(D88)로 교체(스크린샷 교차검색·전후이동·←→), 키보드 A/E/R 결정+자동 다음행·↑↓ 이동, run_dir 전달. screenshot_file 전파는 D56에서 완료. 상세: [doc/10-reviewer-gate-v2.md](10-reviewer-gate-v2.md) §3 | 2026-06-02 |

---

## 8. RAG·결함이력

| ID | 결정 | 일자 |
|---|---|---|
| D4 | RAG 데이터 = 익명화 전제로 활용 가능 | 2026-05-18 |
| D13 | 기존 RAG = 제품명·업체명 없음, 기능명 + 결함내용만 | 2026-05-18 |
| D16 | 익명화 = L1+L2 자동, L3+L4 수동 검토. L5 보류 | 2026-05-18 |

---

## 9. PoC

| ID | 결정 | 일자 |
|---|---|---|
| D3 | 산출물 1차 = 설계 문서 (`doc/`) 우선 | 2026-05-18 |
| D29 | PoC 재정의 = α / β / γ로 단순화 (이전 PoC-1~6 폐기) | 2026-05-19 |
| D31 | PoC 대상 = 간단한 한국어 OSS 게시판 (현재는 자체 합성 mockup) | 2026-05-19 |
| D36 | Stage 0 개발 우선순위 = PoC (α→β→γ) 완료 후 1순위 | 2026-05-19 |
| D14 | 기존 skill = 사용자가 만든 것 아님 → 공유 불가. 인터뷰로만 학습 | 2026-05-18 |
| **D47** | **Phase 2 OSS 시험 대상 = 그누보드5 (gnuboard/gnuboard5)** — 한국 최다 사용 PHP 게시판, Docker 지원, 마크다운 가이드(g5guide.github.io) Stage 1 입력 | 2026-05-19 |

---

## 10. PoC 후 자동 해소된 항목 (이전 결정이 D25 pivot으로 N/A)

| ID | 원 질문 | 해소 사유 |
|---|---|---|
| D26 (Q-INT-5) | 기존 skill TC 생성만 단독 호출 가능한가 | D25 standalone → 분리 자체 불필요 |
| D27 (Q-PA-4) | AWT prompt와 기존 skill 충돌 가능성 | D25 → AWT prompt만 존재 |
| D28 (Q-PA-5) | Excel 컬럼 추가 시 기존 skill 호환성 | D25 → AWT가 컬럼 직접 정의 |

---

## 11. 미해결 — Phase 1 개발 진입 전 결정 필요

| ID | 질문 | 결정 시점 |
|---|---|---|
| ~~Q-PROD-1~~ | ~~PoC 후 실제 OSS 시험 대상 후보 결정~~ → **D47** | 2026-05-19 확정 |
| ~~Q-INFRA-1~~ | ~~DB 서버 스택~~ → **D44** | 2026-05-19 확정 |
| ~~Q-INFRA-2~~ | ~~UI 프레임워크~~ → **D45** | 2026-05-19 확정 |
| ~~Q-INFRA-3~~ | ~~설치 패키지 도구~~ → **D46** | 2026-05-19 확정 |
| Q-MX-1~4 | 25023·25051·25059 매트릭스의 시험소 실무 정합성 | Phase 1 진입 후 검수 |
| ~~Q-LLM-0~~ | ~~LLM 호출이 Anthropic SDK에 직접 결합~~ → **D48** | 2026-05-20 확정 |

## 12. 미해결 — 운영 시 결정

| ID | 질문 | 결정 시점 |
|---|---|---|
| Q-SCH-1 | `precondition` 별도 시트 정규화 여부 | 운영 |
| Q-SCH-2 | `steps`의 DSL화 (Playwright 자동 변환 위해) | 운영 |
| Q-SCH-3 | `failure_reason` 4축 컬럼 분리 vs 한 컬럼 | 운영 |
| Q-SCH-4 | `reviewer_id` 익명화 여부 | 운영 |
| Q-PA-1 | source_quote grep의 fuzzy 허용 범위 | PoC-α 후속 |
| Q-PA-2 | V3 INFERRED 임계 정량 (현재 30%, PoC-β 후 조정) | PoC-β 후 |
| Q-PA-3 | 재호출 3회 상한 적정성 | 운영 |
| Q-PA-4 | API 호출 재시도 횟수·간격 정책 | Phase 1 개발 중 |
| Q14 | Reviewer 결정권 범위 (책임·결재 라인) | 시험소 정책 결정 시 |
| Q-LLM-1~4 | provider별 토큰 계산, ensemble, 캐시 분리, UI 토글 정책 | Phase 2 운영 (상세: doc/07-llm-providers.md §11) |

---

## 결정 누적 규칙

- 새 결정 → 위 표에 *주제별 위치*에 추가
- 기존 결정 변경 → 원 결정에 ~~취소선~~ + 대체 ID 표시
- 미해결이 길어지면 *조건부 가정*으로 명시 + 영향 분석

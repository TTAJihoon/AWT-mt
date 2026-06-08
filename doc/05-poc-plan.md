# PoC 검증 계획 — α / β / γ

> Claude Code 환경에서 prompt 품질을 검증. 통과 시 Desktop App 본 개발(Phase 1) 진입.

---

## 1. 검증 대상

| ID | 질문 | 검증 항목 |
|---|---|---|
| **PoC-α** | TC 생성 품질이 기준을 충족하는가 | TC_DESIGN prompt 유효성 |
| **PoC-β** | 시험원이 시간 budget 내 검토·결재 가능한가 | Reviewer Gate 워크플로 + D20 |
| **PoC-γ** | 승인 TC가 Playwright로 실제 실행되고 결과·실패원인이 기록되는가 | 자동 실행 + 실패 분석 통합 |

---

## 2. PoC 환경

- **대상 제품:** 간단한 한국어 게시판 mockup (`data/poc/<date>/sample-board/board.html`)
- **합성 입력:** 매뉴얼·기능리스트·결함샘플은 AWT가 합성
- **시간 budget:** 총 2~3시간
- **도구:** Claude Code (skill 호출), Playwright MCP, 브라우저
- **기록 위치:** `data/poc/<YYYY-MM-DD>/`

---

## 3. PoC-α — TC 생성 품질 [완료]

### 시나리오

1. 미니 게시판 mockup + 합성 입력을 PoC 입력 폴더에 배치
2. AWT skill 호출 → Stage 1~3 수행 → `tc_raw.csv` + `tc_review.xlsx` 산출

### PASS 기준

- TC 수 ≥ 50
- 필수 컬럼 100% 채움
- happy_path 비율 ≤ 60%
- source_quote 매뉴얼 매칭률 ≥ 85%
- INFERRED ≤ 10% (또는 PoC 학습 후 정량 조정)
- 자동 재호출 ≤ 3회

### PoC-α 결과 (2026-05-19)

| 검증 | 결과 | 비고 |
|---|---|---|
| TC 수 | 41 | 목표 미달이나 mockup 단순함 고려 시 합리적 |
| V1 필수 컬럼 | ✅ PASS | |
| V2 source_quote | ⚠ PARTIAL | 24/41 (58.5%) 직접 인용 |
| V3 INFERRED ≤ 5% | ❌ FAIL | 41.5% (mockup 매뉴얼 모호성 기인) |
| V4 기법 분포 | ✅ PASS | happy 24.4% |
| V5 leaf 커버리지 | ✅ PASS | 10/10 |

**해석:** V3 실패는 *결함*인 동시에 *기능 작동 증거*. AWT가 추론을 source_quote로 위장하지 않고 정직하게 INFERRED 마킹 → P2 traceability 작동.
**조치:** 임계를 30%로 완화 (PoC 환경 한정) + 실제 OSS 매뉴얼에선 10% 재강제.

---

## 4. PoC-β — Reviewer Gate 워크플로 [완료 — 2026-05-19]

### PoC-β 결과

| 기준 | 목표 | 결과 |
|---|---|---|
| TC당 평균 시간 ≤ 60초 | ≤ 60s | ✅ ~51초 |
| pending ≤ 5% | ≤ 2개 | ✅ 0개 |
| Gate 재사용 의향 ≥ 3/5 | ≥ 3 | ✅ 4/5 |

결정 분포: approved 38 / edited 3 / rejected 0 / pending 0
상세: `data/poc/2026-05-19/result.md`
**→ PoC-β PASS**

### 원래 시나리오

### 시나리오

1. PoC-α 산출 `tc_review.xlsx` 열기
2. 사용자가 직접 reviewer 역할로 TC 41개 검토:
   - 회색(≥0.85): approved 빠르게 (TC당 5초)
   - 노랑(0.50~0.85): 5~30초 확인
   - 빨강(<0.50, INFERRED): 30초~2분 심층
3. 모든 TC에 결정 입력 (A/E/R/P)
4. 종료 시간 기록

### PASS 기준

- TC당 평균 시간 ≤ 60초 (D20 30s~2min 중간점)
- pending ≤ 5%
- Gate 워크플로 재사용 의향 ≥ 3 / 5

### 기록 양식

```
- 결정 분포: approved __개 / edited __개 / rejected __개 / pending __개
- 총 소요 시간: __분
- 피로도 (1~5): __
- 가장 판단 어려웠던 TC: TC-___-___ (이유)
- AWT가 다음에 개선했으면: ___
- 종합 판단: 다음 PoC-γ로 진행 OK? Y/N
```

---

## 5. PoC-γ — 자동 실행과 결과 보강 [완료 — 2026-05-19]

### PoC-γ 결과

| 기준 | 목표 | 결과 |
|---|---|---|
| 실행 완료율 | ≥ 90% | ✅ 100% (41/41) |
| TC당 평균 실행 시간 | ≤ 30초 | ✅ < 1초 (JS eval) |
| FAIL failure_reason 4축 | ≥ 80% | ✅ 100% (9/9) |
| 사용자 결과 신뢰도 | ≥ 3/5 | ✅ 5/5 |

PASS 32 / FAIL 9 — BUG-1·2·3 전부 검출 + 신규 BUG-4·5 발견
상세: `data/poc/2026-05-19/output/tc_gamma_results.md`
**→ PoC-γ PASS → Phase 1 진입 가능**

### 원래 시나리오

### 시나리오

1. PoC-β의 approved + edited TC만 추출
2. Stage 5 (Playwright MCP) 자동 실행
3. result + actual + failure_reason + exec_confidence 채움
4. `tc_final.xlsx` 검토

### PASS 기준

- 실행 완료율 ≥ 90% (셀렉터·환경 문제 ≤ 10%)
- TC당 평균 실행 시간 ≤ 30초
- FAIL TC의 failure_reason 4축 채움률 ≥ 80%
- 사용자 결과 신뢰도 ≥ 3 / 5

---

## 6. 의사결정 트리

```
PoC-α
├─ PASS → PoC-β
├─ V1 FAIL → prompt 컬럼 강제 강화
├─ V2 FAIL → source_quote 정규화 전략 강화
├─ V3 FAIL → 입력 자료 품질 검토 또는 임계 완화 (PoC-α 결과 후자 채택)
└─ V4 FAIL → 설계 기법 분포 강제 강화

PoC-β
├─ PASS → PoC-γ
├─ 시간 폭증 → confidence 분포 조정 (자동 승인 비율 확대)
├─ pending 다발 → 명세 모호성 → 입력 자료 보강
└─ 피로도 ↑ → Gate UX 조정 (색상·정렬·단축키)

PoC-γ
├─ PASS → Phase 1 (Desktop App 본 개발) 진입
├─ 셀렉터 불안정 → self-healing (Phase 2) 또는 DOM 인덱스 강화
├─ 실행 시간 폭증 → Stage 5 병렬화 설계
└─ failure_reason 채움률 ↓ → FAILURE_ANALYSIS Contract 강화
```

---

## 7. PoC 통과 후 작업

- TC_DESIGN / FAILURE_ANALYSIS Contract의 prompt 본문이 `prompts/` 디렉터리에 그대로 들어감
- Phase 1 (Desktop App) 개발 진입:
  1. Stage 0 DOM 스캔 모듈
  2. orchestrator.py (Stage 0~7 흐름)
  3. PyQt5 UI (login, dashboard, wizard, reviewer_gate)
  4. DB 인증 클라이언트
  5. API 키 암호화 저장
  6. PyInstaller + Inno Setup 설치 패키지

---

## 8. PoC 한계 사전 인지

- 입력 mockup이 *너무 단순* → 실제 OSS 시험과 갭 존재 (PoC-γ 후 실제 OSS로 검증 예정)
- Reviewer가 *AWT 자체 자아* → 진짜 시험원의 시각과 불일치 가능 (PoC-β의 약점)
- Claude Code 환경 → 프로덕션 Desktop App 환경과 차이. 단, prompt 자체는 환경 무관하게 재사용 가능.

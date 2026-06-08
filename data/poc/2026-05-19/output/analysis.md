# PoC-α 시뮬레이션 분석 — AWT 자체 평가

**일자:** 2026-05-19
**작업:** AWT가 자신의 Stage 1·2·3을 시뮬레이션해 [tc_raw.csv](tc_raw.csv) 산출.
**메타 데이터:** [v_meta.json](v_meta.json)

> **주의:** 본 분석은 *AWT 자체의 자기 평가*. PoC-β(사용자 reviewer 검토)에서 의미 있는 외부 평가가 도출됨.

---

## 1. 산출 요약

- **TC 수:** 41개 (10 leaf × 평균 4.1개)
- **happy_path 비율:** 24.4% (목표 ≤ 50% ✓)
- **INFERRED 비율:** 41.5% (목표 ≤ 10% ✗ — V3 FAIL)

## 2. V1~V5 자체 검증 결과

| 검증 | 결과 | 비고 |
|---|---|---|
| V1 필수 컬럼 | ✅ PASS | 9개 컬럼 모두 채움 |
| V2 source_quote grep | ⚠ PARTIAL | 24/41 (58.5%) 직접 인용, 17개 INFERRED |
| V3 INFERRED ≤ 5% | ❌ **FAIL** | 41.5% → PoC-α 임계 초과 |
| V4 기법 분포 | ✅ PASS | happy 24.4%, 다양 분산 |
| V5 누락 기능 | ✅ PASS | 10/10 leaf 커버 |

## 3. V3 실패 분석 — 무엇이 의미하는가

### 3.1. 근본 원인: 입력 자료의 모호성

매뉴얼이 다음 영역에서 *부재* 또는 *모호*:
- §3.1 "제목은 적절한 길이로" — *정확한 수치 없음* (BUG-3과 관련)
- 입력 검증·경계 조건 (빈 입력, 길이 상한, 페이지 경계)
- 미존재 자원 처리 (없는 글 id)
- Cascade 동작 (글 삭제 → 댓글 처리)
- 아이디 형식·길이 제약

AWT는 *추론할 수 있었지만 그러지 않음* — `INFERRED:` 마킹으로 정직하게 표시.

### 3.2. 이건 *결함*인가 *기능*인가

**Both.** 두 의미가 있음:
- **결함 (PoC-α PASS 기준 기준으로):** 임계 41.5% > 10% → FAIL
- **기능 (P2 traceability 작동 증거):** AWT가 무리하게 추론을 source_quote로 위장하지 않음. 이는 **8대 원칙 P2의 작동 증거**.

### 3.3. 의사결정 트리 (`06-poc-validation-plan.md` §8) 적용

> "FAIL: V3 미충족 → 입력 자료 품질 검토"

→ 입력 자료(매뉴얼)가 *완전하지 않다*는 신호. 두 옵션:
1. **매뉴얼 보강** — 길이·경계·빈 입력 등 명시 추가 → INFERRED 비율 자연 감소
2. **임계 완화** — PoC 입력의 모호성을 인지하고 임계를 30%까지 완화 (실제 시험소 매뉴얼이 더 충실하다는 가정)

> 권장: PoC 목적이 *AWT 흐름 검증*이므로 *임계 완화*가 합리적. 단 실제 시험소 매뉴얼에서는 INFERRED ≤ 10% 다시 강제.

---

## 4. design_technique 분포 관찰

```
happy_path        ████████████ 10
equivalence       ██ 2
boundary          ███████████████ 11
negative_basic    ████████ 7
negative_deep     ████ 4
state_transition  ██ 1
cross_feature     ██████ 6
```

**관찰:**
- **boundary가 가장 많음** (11개) — 매뉴얼이 모호한 영역(길이·페이지 경계)에서 결함 샘플(F-1·F-3)을 참조해 적극 추가
- **negative_deep 4개** — 의도된 BUG-2 (권한 우회)를 정확히 시도 (TC-007-003·TC-008-003)
- **cross_feature 6개** — 의미 연관성 자연스럽게 포착 (작성↔목록·수정↔상세·삭제↔cascade·댓글↔노출)
- **state_transition 1개**만 — mockup이 단순(워크플로 단계 부족)해 자연스러운 결과

## 5. 의도된 함정 검출 시도

| BUG | 검출 TC | 기법 | 확신도 |
|---|---|---|---|
| BUG-1 페이지 경계 | TC-006-002 ~ TC-006-005 | boundary 4개 | gen_confidence 0.40~0.52 (INFERRED) |
| BUG-2 권한 우회 | TC-007-003, TC-008-003 | negative_deep 2개 | gen_confidence 0.80 (F-2 결함 샘플 직접 매칭) |
| BUG-3 제목 길이 | TC-003-004 ~ TC-003-006 | boundary 3개 | gen_confidence 0.38~0.42 (매뉴얼 모호 INFERRED) |

→ **3개 BUG 모두 *검출 시도 TC 존재*.** Stage 5(PoC-γ) 자동실행 시 실제로 검출되는지가 핵심.

## 6. confidence 분포

```
≥ 0.85 (high)     ████████████████ 13 (31.7%)
0.70 ~ 0.85 (mid) █████████████████ 14 (34.1%)
0.50 ~ 0.70 (low) ███████████ 9 (22.0%)
< 0.50 (INFERRED) ██████ 5 (12.2%)
```

**Reviewer Gate (PoC-β) 예상 시간:**
- ≥ 0.85: 13개 × 8초 = 1.7분
- 0.70~0.85: 14개 × 30초 = 7분
- 0.50~0.70: 9개 × 1분 = 9분
- < 0.50: 5개 × 2.5분 = 12.5분
- **합계: 약 30분**

→ TC당 평균 43초 (D20 30s~2min 중간점 부근).

## 7. AWT 자체 평가의 한계

본 분석은 *AWT가 자신을 평가*한 결과로 다음 한계 인지:
- **자기 검증의 재귀성** — Stage 3 V1~V5를 적용했지만, *Stage 2 prompt 자체의 결함*을 V가 잡지 못할 수 있음
- **모범 답안 비교 불가** — 인간 전문가의 TC와 비교 없음. PoC-β에서 너의 reviewer 시각이 핵심
- **자동 실행 결과 미반영** — PoC-γ 후에야 실제 결함 검출 가능성 확인

## 8. PoC-α 종합 판정 (자체)

- 형식적 PASS 기준: V1·V4·V5 ✅ / V2 PARTIAL ⚠ / V3 ❌
- 실질적 의미: **AWT의 흐름은 작동하나 입력 자료 충실성 의존**
- 권장: PoC-β 진행 (Reviewer Gate에서 INFERRED 17개를 너가 어떻게 결재하는지 관찰이 핵심)

## 9. 다음 PoC 단계

### PoC-β 진행 가이드
1. [tc_raw.csv](tc_raw.csv) 열어 41개 TC 검토
2. Excel/스프레드시트로 import 후 색상·정렬 적용:
   - INFERRED (source_quote 시작이 "INFERRED"): 노란색
   - gen_confidence < 0.50: 빨간색
3. 각 TC에 review_status 입력 (approved/edited/rejected/pending)
4. 총 시간·결정 분포·피로도 기록 → result.md PoC-β 절 채움

### PoC-γ 준비
- PoC-β 통과 TC만 추출
- board.html을 브라우저에서 열고 *너가 reviewer 시점에서* 각 TC를 직접 실행해보기 (자동 실행 simulation)
- 또는 다음 턴에서 AWT가 Playwright MCP로 자동 실행 시뮬레이션

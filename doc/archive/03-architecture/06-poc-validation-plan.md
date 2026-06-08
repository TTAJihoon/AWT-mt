# PoC 검증 계획서 — Phase 1.0 (Standalone, D25 후 재작성)

**작성일:** 2026-05-19 (D25 pivot 후 재작성. 이전 버전은 git history 참조.)
**선행 문서:** `00-existing-method-interview.md`, `00b-gap-analysis.md`, `05-prompt-augmentation.md`

> **D25 pivot 이후 변화:** 이전 PoC는 *외부 skill과의 호환성 검증* 6종이 핵심이었다. Standalone 결정 후 이 부분이 *전부 N/A*가 됨. 새 PoC는 *AWT 자체의 동작 확인* 3종 (α·β·γ).

---

## 1. 검증 대상 (재정의)

| ID | 질문 | 영향 |
|---|---|---|
| **PoC-α** | AWT가 standalone으로 작은 제품에 대해 *기준 충족 TC*를 생성할 수 있는가 | E1·E2 prompt 유효성 |
| **PoC-β** | Reviewer Gate에서 시험원이 *시간 budget 내* 검토·결재 가능한가 | E5 워크플로 유효성 + D20 검증 |
| **PoC-γ** | 승인된 TC가 Playwright MCP로 *실제 실행*되고 결과·실패원인이 기록되는가 | E3·E4 + 자동실행 통합 |

부수 검증 (PoC-α 결과에서 동시 도출):
- Q-PA-1: source_quote grep 정확도
- Q-PA-2: INFERRED 비율 적정성
- Q-PA-3: 재호출 사이클 효용

---

## 2. PoC 환경

- **대상 제품:** **간단한 한국어 오픈소스 게시판** (D31). 구체 후보는 §3에서.
- **합성 입력:** 매뉴얼·기능리스트·결함샘플은 AWT가 *합성*해서 PoC 입력으로 사용 (실제 시험소 자료 사용 불요)
- **시간 budget:** 총 2~3시간 (사용자 직접 수행)
- **도구:** Claude Code (skill 호출), Playwright MCP, pdf/xlsx 스킬, 브라우저
- **기록 위치:** `data/poc/<YYYY-MM-DD>/`

---

## 3. 대상 제품 후보 (Q-PROD-1)

후보 게시판 옵션:

| 후보 | 특징 | 장점 | 단점 |
|---|---|---|---|
| **A. PHP/MySQL 간단 게시판** (예: zeroboard 유사 OSS) | 글작성·댓글·로그인 | 시험소 도메인 친숙 | 설치 필요 |
| **B. Next.js 기반 OSS 게시판** | 모던 SPA | DOM 스캔 정확 | 설치 복잡할 수 있음 |
| **C. 정적 호스팅 가능한 마크다운 블로그 + 댓글 (예: utterances)** | 즉시 시험 가능 | 환경 불요 | 게시판이라기엔 약함 |
| **D. AWT가 자체 합성한 *최소 게시판 mockup*** | URL은 임시 호스팅 또는 file:// | 통제 완벽 | 실제성 ↓ |

**1순위 추천:** 옵션 **D** — AWT가 *최소 기능 게시판 HTML mockup*을 합성. URL은 file:// 또는 임시 정적 호스팅.

이유:
- PoC 목적은 *AWT 흐름 검증*이지 *실제 시험소 작업*이 아님
- 환경 셋업 시간 = 0
- 결과가 *완전히 재현 가능*
- AWT가 매뉴얼·기능리스트·게시판 HTML 모두 합성하면 *입력·출력의 일관성*이 명확

대안: 옵션 A·B를 선호하면 구체 OSS 검색은 별도 단계.

---

## 4. PoC-α — TC 생성 품질

### 4.1. 시나리오

1. AWT가 미니 게시판 mockup + 합성 매뉴얼·기능리스트·결함샘플을 *PoC 입력 폴더*에 배치
2. AWT를 Claude Code skill로 호출:
   ```
   /awt
   입력 폴더: data/poc/<date>/sample-board/input/
   대상 URL: file:///data/poc/<date>/sample-board/board.html
   ```
3. AWT가 Stage 1~3을 수행해 `tc_verified.xlsx` 산출

### 4.2. 측정 (사용자가 결과 검토)

- TC 수 (목표: 50~150)
- 필수 컬럼 모두 채워짐: Y/N
- design_technique 분포: happy_path 비율 ≤ 50%
- source_quote가 매뉴얼에 실제 존재: 10개 무작위 sample → M1·M2·M3 매칭률
- INFERRED 비율 ≤ 5% (또는 10% 한도)
- V1~V5 자동 재호출 횟수

### 4.3. PASS 기준

다음 모두 충족:
- TC 수 ≥ 50
- 필수 컬럼 100% 채움
- happy_path 비율 ≤ 60%
- M2 매칭률 ≥ 85%
- INFERRED ≤ 10%
- 자동 재호출 ≤ 3회로 통과

**예상 소요:** 30~60분

---

## 5. PoC-β — Reviewer Gate 워크플로

### 5.1. 시나리오

1. PoC-α 산출 Excel을 열어 색상·정렬 확인
2. 사용자가 *직접 reviewer 역할* — TC 1개씩 검토:
   - 회색(≥0.9): approved 일괄
   - 기본·노랑: 5~30초 확인
   - 빨강·INFERRED: 30초~2분 심층
3. 모든 TC에 결정 입력 (approved / edited / rejected / pending)
4. 종료 시간 기록

### 5.2. 측정

- 총 검토 시간 (분)
- TC당 평균 시간 (초)
- 각 결정의 비율 (approved %, edited %, rejected %, pending %)
- 사용자 본인의 *주관적 피로도 1~5*

### 5.3. PASS 기준

- TC당 평균 시간 ≤ 60초 (D20 30s~2min 중간점)
- pending ≤ 5%
- 사용자가 *Gate 워크플로를 *다시 사용할 의향*이 있음* (3 이상 / 5)

**예상 소요:** 30~60분

---

## 6. PoC-γ — 자동 실행과 결과 보강

### 6.1. 시나리오

1. PoC-β 결과 (approved + edited)만 추출
2. AWT의 Stage 5 (Playwright MCP 자동 실행) 호출
3. result + actual + oracle_reason + failure_reason + exec_confidence 채움
4. tc_final.xlsx 검토

### 6.2. 측정

- 자동 실행 완료한 TC 수
- 실행 시간 (총·평균/TC)
- FAIL TC 중 failure_reason 4축이 모두 채워진 비율
- 사용자가 *결과 신뢰* 1~5

### 6.3. PASS 기준

- 자동 실행 완료율 ≥ 90% (실행 불가 셀렉터·환경 문제 ≤ 10%)
- TC당 평균 실행 시간 ≤ 30초 (간단 mockup 기준)
- FAIL TC의 failure_reason 4축 채움률 ≥ 80%
- 사용자 신뢰도 ≥ 3 / 5

**예상 소요:** 30~60분

---

## 7. 종료 조건 (Phase 1.1 진입 가능 여부)

| 조건 | 기준 |
|---|---|
| PoC-α | §4.3 PASS 기준 모두 충족 |
| PoC-β | §5.3 PASS 기준 모두 충족 |
| PoC-γ | §6.3 PASS 기준 모두 충족 |

모두 통과 → Phase 1.1 (정식 강화 단계) 진입. 일부 통과 → 미통과 항목별 prompt·설계 조정 후 부분 재PoC.

---

## 8. 의사결정 트리

```
PoC-α
├─ PASS → PoC-β
├─ FAIL: V1 미충족 → prompt 컬럼 강제 강화
├─ FAIL: V2 미충족 → source_quote 정규화 전략 강화
├─ FAIL: V4 미충족 → 설계 기법 분포 강제 강화
└─ FAIL: 자동 재호출 한계 → 입력 자료 품질 검토

PoC-β
├─ PASS → PoC-γ
├─ FAIL: 시간 폭증 → confidence 분포 조정
├─ FAIL: pending 다발 → 명세 모호성 (입력 자료 보강 필요)
└─ FAIL: 피로도 ↑ → Gate UX 조정 (색상·정렬·매크로)

PoC-γ
├─ PASS → Phase 1.1 진입
├─ FAIL: 셀렉터 불안정 → self-healing (Phase 2) 또는 Stage 1 DOM 인덱스 강화
├─ FAIL: 실행 시간 폭증 → Stage 5 병렬화 설계
└─ FAIL: failure_reason 채움 ↓ → E3 prompt 강화
```

---

## 9. PoC 실행자(사용자) 가이드

PoC 실행 절차:
1. AWT가 미니 게시판 mockup + 합성 입력 자료를 `data/poc/<date>/sample-board/` 폴더에 생성 (사전 단계)
2. 사용자가 AWT skill 호출
3. PoC-α 결과 검토 → 결과 양식 채움
4. PoC-β로 진행 → reviewer 사이클 수행
5. PoC-γ로 진행 → 자동 실행 결과 검토
6. 최종 결과를 `data/poc/<date>/result.md`에 정리

---

## 10. PoC 결과 보고 양식

```
PoC 일자: YYYY-MM-DD
대상 제품: 미니 게시판 mockup (또는 OSS)
총 소요: __ 시간

PoC-α:
  TC 수: ___
  필수 컬럼 채움률: ___%
  design_technique 분포: happy=__%, equiv=__%, bound=__%, neg_basic=__%, neg_deep=__%, state=__%, cross=__%
  source_quote M2 매칭률: __%
  INFERRED 비율: __%
  자동 재호출 횟수: __
  PASS / FAIL: ___ (사유)

PoC-β:
  총 검토 시간: __분
  TC당 평균: __초
  approved: __%, edited: __%, rejected: __%, pending: __%
  피로도: __/5
  PASS / FAIL: ___

PoC-γ:
  실행 완료율: __%
  TC당 평균 실행 시간: __초
  failure_reason 4축 채움률: __%
  신뢰도: __/5
  PASS / FAIL: ___

종합 판정: Phase 1.1 진입 가능? Y/N
잔여 조정 사항: ___
```

---

## 11. PoC 후 다음 작업

PoC 완료 후:
- TC 스키마 §4·§5 자동 해소 (D27·D28로 N/A)
- E3·E4 prompt 본문 작성 (`07-prompt-augmentation-e3e4.md`)
- Phase 1 구현 본격 진입 (`prompts/`, `tools/`, `skills/` 폴더 작성)

PoC가 실패하는 경우의 fallback은 §8 의사결정 트리 참조.

# Layer 1 — AWT 자동 시험 상세

**적용 범위:** `01-characteristics-matrix.md` §5에서 L1으로 분류된 모든 메트릭.
**책임 주체:** AWT (생성 + 실행 + 판정 자동). 시험원은 Gate에서 confidence 기반 빠른 확인만.

> **L1의 약속:** 시험소 처리량 증가의 70~80%는 여기서 발생. 단, *AI 환각 차단을 위한 source_quote·confidence 강제*가 전제.

---

## 1. Functional Suitability

가장 큰 비중. 4인 토론 결론과 사용자 인터뷰 모두 *AI 강점 영역*으로 합의됨.

### 1.1. Functional Completeness — 기능 완전성

**메트릭:** 명세된 기능 중 시험된 기능의 비율
```
FC = (TC가 존재하는 기능 수) / (기능리스트 최하위 분류 총 수)
```

**입력:**
- 기능리스트 Excel의 최하위 분류 행 집합
- AWT가 생성한 TC 집합의 `requirement_id`

**처리:**
1. 기능리스트의 모든 최하위 분류를 `set_F`로 구성
2. TC의 requirement_id를 `set_T`로 구성
3. `FC = |set_T| / |set_F|`
4. 미커버 기능 목록 별도 출력

**산출:**
- 메트릭 값 (%)
- 미커버 기능 리스트 → 재호출 prompt 자동 반영(V5)

**Confidence 산정:**
- `gen_confidence`: 기능리스트 명세 충실성에 따라 결정. 기능명만 있고 설명 없으면 ↓
- `exec_confidence`: 해당 없음 (메트릭은 실행 무관)

**한계:**
- "시험된" 정의가 단순 *TC 존재*인지 *TC 통과*인지에 따라 결과 다름 → §8-metric-definitions에서 시험소 정의 확정 필요

### 1.2. Functional Correctness — 기능 정확성

**메트릭:** TC 실행 결과 PASS 비율
```
FCo = (PASS TC 수) / (실행된 TC 총 수)
```

**입력:**
- TC Excel `result` 컬럼 집합

**처리:**
- 단순 카운트. 단, *false PASS 제거*를 위해 `oracle_reason`·`source_quote` 부재 TC는 제외 옵션

**Confidence 산정:**
- 각 TC의 `exec_confidence`를 곱한 가중 평균 옵션 (Phase 2)

**핵심 강화:** E1(source_quote 강제) + E3(oracle_reason 자동 기록)이 이 메트릭의 *신뢰성*을 결정.

### 1.3. TC 생성 패턴 (E2 기법 매핑)

각 기능에 대해 다음 기법별로 TC 생성:

| 기법 | 적용 조건 | 최소 TC 수 | 기대 효과 |
|---|---|---|---|
| `happy_path` | 모든 기능 | 1 | 기본 동작 검증 |
| `equivalence` | 입력 도메인 ≥ 2 | 도메인 수 | 입력 분할 커버리지 |
| `boundary` | 수치/길이 제약 존재 | 경계 양쪽 2 | 경계값 결함 차단 |
| `negative_basic` | 모든 기능 | 1 | 잘못된 입력 거부 |
| `negative_deep` | UI 표시 기능 | 1 | 에러 메시지 4축 (위치/한국어/이해성/보안) |
| `state_transition` | 다단계 워크플로 | 단계 수 - 1 | 중간 step 누락 검출 |
| `cross_feature` | 의미적 연관 기능 ≥ 2 | 1 | 기능 결합 시나리오 |

---

## 2. Performance Efficiency — Time Behavior

**메트릭:** 응답시간 분포 (평균/p50/p95/p99)

**입력:**
- Playwright의 timing API (`page.goto`, `page.click` 등 각 액션의 소요)

**처리:**
1. 각 TC 실행 시 주요 액션별 timing 측정
2. 기능별·전체 분포 산출

**산출:**
- 별도 시트 `Performance_Time` 권장 (Phase 2)
- 시험원에게는 *임계 초과 TC*만 부각

**Confidence 산정:**
- 단일 측정은 노이즈 → 동일 TC를 3회 반복 평균이 권장 (Phase 2)
- 1회 측정은 `exec_confidence` ≤ 0.6 책정

**한계:**
- 클라이언트 측 timing만 측정. 서버 측 부하는 부하시험 도구 별도 (L3, Capacity)

---

## 3. Compatibility — 웹 브라우저 호환성

**메트릭:** 주요 브라우저별 PASS 비율
```
BC_browser = PASS in <browser> / TC 총 수 (실행된 것)
```

**입력:**
- Playwright의 multi-browser 지원 (`chromium`, `firefox`, `webkit`)

**처리:**
- 동일 TC를 N개 브라우저에서 반복 실행
- 브라우저별 PASS/FAIL 비교

**산출:**
- TC × Browser 매트릭스 (보통 별도 시트)

**비용 고려:**
- 모든 TC × 모든 브라우저 = N배 실행 시간. 시험소 SLA와 트레이드오프
- 권장: *핵심 TC만 multi-browser*. 핵심 = happy_path + 결제·인증 등 위험 큰 기능
- TC 양식에 `multi_browser_required` 컬럼 추가 검토 (Phase 2)

**Phase 1 정책:** 단일 브라우저(chromium) 우선. 다중 브라우저는 Phase 2.

---

## 4. Reliability — Maturity (결함 밀도)

**메트릭:** 결함 밀도
```
DD = (FAIL TC 수) / (TC 총 수)
```

**입력:** TC 실행 결과 `result` 컬럼

**처리:** 단순 카운트 + 기능별 분포

**산출:**
- 전체 + 기능별 결함 밀도
- 결함 *집중 기능* TOP-N 자동 식별

**연결:**
- §5 RUSP의 *시험 문서*는 결함 리포트 자동 생성에 본 데이터 활용

---

## 5. ISO/IEC 25051 — 시험 문서 자체

> 이 메트릭은 *AWT가 산출하는 결과물의 품질에 대한* 메트릭. 즉 AWT의 자기 메타 측정.

**요구사항:**
- 모든 TC가 식별 가능한 ID (D9)
- 각 TC가 source_quote로 명세 traceable (E1)
- 실행 결과·실패 원인 기록 (E3)
- 시험 절차 재현 가능

**자동 자기 점검:**
- TC schema 검증 (`doc/04-tc-design-spec/01-tc-schema.md` §3)
- V1~V5 통과 여부 (`doc/03-architecture/05-prompt-augmentation.md` §4)
- 결과 보고서 양식 정합성

**산출:**
- 시험 보고서에 *자기 점검 결과* 헤더 포함 (Phase 2):
  ```
  AWT Self-Audit: V1 ✓ / V2 98.3% / V3 3.1% INFERRED / V4 ✓ / V5 ✓
  ```

---

## 6. L1에서 *자동화는 가능하나 신중해야 할* 영역

다음은 *기술적으로 L1이지만 false PASS/FAIL 위험이 큼*:

| 영역 | 위험 | 완화책 |
|---|---|---|
| 비동기 UI (lazy load, infinite scroll) | "expected 텍스트 없음" 1초 후 등장 → false FAIL | Playwright의 `waitFor` 명시 + exec_confidence 하향 |
| 동적 셀렉터 (auto-generated id) | 셀렉터 깨짐 → 재시도 무한루프 | self-healing selector (Phase 2) + 최대 재시도 N회 |
| 다국어 (i18n) | 한국어 매뉴얼이지만 영어 UI → expected mismatch | 매뉴얼 언어와 UI 언어 일치성 검증 prompt |
| 인증 필요 페이지 | 로그인 만료로 page 미진입 | 매 TC 시작 시 세션 검증 step |
| 결제·외부 API | 실거래 위험 | 격리 환경(stub/sandbox) 강제. 실거래 TC는 L3로 강등 |

이런 경우는 **`exec_confidence`를 의도적으로 낮춰** Gate에서 우선 검토되게 함.

---

## 7. Phase별 발전

| Phase | L1 강화 |
|---|---|
| 1 | E1·E2·E3·E4·E5로 신뢰 기반 확립 |
| 2 | 메트릭 % 자동 계산 + 보고서 통합, multi-browser, self-healing |
| 3 | 25059 stochastic 메트릭, differential testing |

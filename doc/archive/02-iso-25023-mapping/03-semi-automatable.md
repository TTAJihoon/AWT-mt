# Layer 2 — AWT 보조 + 시험원 검토 상세

**적용 범위:** `01-characteristics-matrix.md`에서 L2로 분류된 모든 메트릭.
**책임 주체:** **AWT가 증거 자료·후보안을 정리해 제공 → 시험원이 Gate에서 검토·판정.** AWT가 단독으로 PASS/FAIL을 확정하지 않음.

> **L2의 본질:** 시험원의 판단을 *대체*하지 않고 *시간 단축 + 누락 방지*. AWT 산출은 항상 *제안*이지 *결론*이 아님.

---

## 1. L2에서 AWT의 표준 출력 패턴

L2 메트릭은 `result` 컬럼이 `pass` / `fail`이 아닌 다음 4값 중 하나:

| 값 | 의미 | 시험원 처리 |
|---|---|---|
| `pass_suggested` | AWT는 PASS로 본다 (confidence 동반) | 빠른 확인 |
| `fail_suggested` | AWT는 FAIL로 본다 (failure_reason 동반) | 빠른 확인 |
| `human_review_required` | AWT가 판정 불가 | 심층 확인 |
| `evidence_only` | AWT는 증거만 수집, 판정 안 함 | 시험원 판정 |

→ Gate 워크플로에서 `human_review_required` + `fail_suggested`는 자동으로 빨간색 정렬 우선.

---

## 2. 영역별 상세

### 2.1. Functional Appropriateness — 기능 적절성

**왜 L2:** "이 기능이 사용 목적 달성에 적절한가"는 도메인 지식 요구.

**AWT 보조:**
- 기능리스트와 매뉴얼에서 *기능의 목적 진술*을 추출
- TC 결과가 그 목적을 충족하는지 *AWT 의견* 제시 + `oracle_reason`에 근거 인용
- `result = pass_suggested` 또는 `human_review_required`

**시험원 가이드:**
- 도메인이 익숙한 경우 → 빠른 승인
- 도메인이 익숙하지 않은 경우 → 매뉴얼 원문 + AWT의 oracle_reason을 같이 보고 판정

### 2.2. Operability·User Error Protection·Accessibility (UX 일부)

**Operability:**
- AWT 자동: 탭 순서·키보드 only 워크플로 가능성·버튼 클릭 영역
- 시험원 판정: 전체적 사용 편의

**User Error Protection (negative_deep TC):**
- AWT 자동: 잘못된 입력에 *에러 메시지가 표시되는가* (위치·존재)
- 시험원 판정 4축:
  1. 위치: 적절한가
  2. 한국어: 자연스러운가
  3. 이해성: 비기술 사용자가 이해 가능한가
  4. 보안노출: 내부 경로·스택트레이스·SQL 노출 없는가

**Accessibility:**
- AWT 자동: axe-core 류 자동 검사 (WCAG의 30~40%)
- 시험원 판정: 스크린리더 실사용·키보드 only 완주·색대비 인지

### 2.3. Resource Utilization·Fault Tolerance·Recoverability

**Resource Utilization:**
- AWT 자동: 브라우저 메모리·네트워크 사용량 timing
- 시험원 판정: 임계 적정성

**Fault Tolerance:**
- AWT 자동: 의도된 결함 주입 TC (negative_deep) 결과
- 시험원 판정: 결함 발생 시 *허용 가능한 거동*인지

**Recoverability:**
- AWT 자동: 복구 시나리오 실행 + 시간 측정
- 시험원 판정: 복구의 *완전성* (데이터 손실 없음 등)

### 2.4. Security 기초

**AWT 자동 (기초):**
- 인증되지 않은 URL 직접 접근 (단순 IDOR)
- 권한별 페이지 노출 차이
- 기본 입력 검증 (XSS 단순 패턴)
- HTTPS·쿠키 secure 플래그

**AWT 한계:**
- 우회 시나리오, 세션 탈취, CSRF 심층은 L3 (별도 표준)
- AWT 자동 점검은 *기초 통과를 확인할 뿐*, *보안성 보증 아님* 명시 필수

### 2.5. ISO/IEC 25051 제품 설명서·사용자 문서 정합성

**중요:** 한국 SW 시험인증에서 큰 비중. L2 워크플로의 핵심 작업 영역.

**AWT 자동 점검:**
- 제품 설명서에 다음 항목이 *존재하는가* 자동 확인:
  - 제품명, 버전, 개발사
  - 시스템 요구사항 (OS, 브라우저, 하드웨어)
  - 주요 기능 목록 (기능리스트와 매칭)
  - 라이선스·저작권 표시
- 사용자 문서에 다음 항목 존재 확인:
  - 설치·접속 안내
  - 주요 기능 사용 방법
  - 문제 해결 가이드 (FAQ·연락처)

**시험원 가이드:**
- 존재 확인은 AWT, *내용의 정확성·완전성·일관성*은 시험원
- 제품 동작과 매뉴얼 내용의 불일치 발견 시 시험원이 결함 리포트로 분리 작성
- 가능한 자동 보조: 제품 동작 결과 vs 매뉴얼 문장의 *주요 단어* 일치 비교 (Phase 2)

### 2.6. ISO/IEC 25059 AI 특화 (조건부)

> AI 기능 포함 제품만 적용. 비AI 제품은 본 절 무시.

**Functional Adaptability:**
- AWT 자동: metamorphic relation 시험 (의미 동등 입력에 의미 동등 출력)
- 시험원 판정: relation의 *의미 등가성* 자체

**User Controllability:**
- AWT 자동: "정지/되돌리기/조정" UI 존재 + 동작 여부
- 시험원 판정: 통제의 *충분성*

**Transparency:**
- AWT 자동: AI 결정에 *설명 UI*가 표시되는가
- 시험원 판정: 설명의 *품질* (이해성, 정확성)

**Robustness:**
- AWT 자동: adversarial 입력 TC (오타, 부정확 데이터, 극단값)
- 시험원 판정: 거동의 *허용 가능성*

**Intervenability:**
- AWT 자동: kill switch·중단 메커니즘 존재
- 시험원 판정: 운영 절차의 *유효성*

---

## 3. Reviewer Gate에서의 L2 처리 우선순위

Gate에서 시험원이 보는 순서 (자동 정렬):

```
1. result = human_review_required + confidence < 0.4    ← 가장 위
2. result = fail_suggested + INFERRED 또는 source_quote 부재
3. result = fail_suggested + confidence < 0.7
4. result = pass_suggested + INFERRED
5. result = pass_suggested + confidence < 0.7
6. result = pass_suggested + confidence ≥ 0.7
7. result = pass_suggested + confidence ≥ 0.9 (자동 일괄 승인 후보)
```

**시간 budget 분배 권장 (TC 1개당 평균 30s~2min, D20 기준):**
- 1·2번: 1~3분/TC
- 3·4번: 30~60초/TC
- 5번: 20~30초/TC
- 6·7번: 5~10초/TC (일괄)

---

## 4. L2 메트릭에 대한 AWT의 *증거 자료 패키지*

각 L2 TC에 대해 AWT가 다음을 함께 제공:

| 자료 | 내용 | 위치 |
|---|---|---|
| 스크린샷 (전·중·후) | 실행 단계별 화면 | 별도 폴더 |
| 매뉴얼 인용 | source_quote 원문 (위치 포함) | TC 행의 source_quote 컬럼 |
| AWT 의견 | oracle_reason 자연어 설명 | TC 행의 oracle_reason 컬럼 |
| confidence 근거 | gen/exec confidence 산정 이유 한 줄 | TC 행의 confidence_reason 컬럼 (옵션) |
| 비교 자료 | (해당 시) 이전 버전 시험 결과 | RAG 참조 (Phase 2) |

시험원이 *AWT 의견의 근거*를 5초 안에 확인 가능해야 함.

---

## 5. 시험원 결정의 기록

Gate에서 시험원이 내린 결정은 다음 컬럼에 기록 (TC schema G4):

- `review_status`: pending / approved / edited / rejected
- `reviewer_note`: 결정 이유 (특히 AWT 의견과 다를 때)
- `reviewer_id`: 시험원 식별 (필수)

**중요:** AWT 의견이 *틀린 경우*의 `reviewer_note`는 RAG의 *피드백 데이터*가 됨 (Phase 2). 누적 후 AWT prompt 개선의 객관 근거.

---

## 6. L2 영역의 AWT 진화 방향 (Phase 2~3)

- **메타모픽 테스팅 자동화** (25059 Functional Adaptability)
- **시각 인식 + LLM judge** (Aesthetics 일부를 L2로 부분 자동화)
- **결함 패턴 RAG** (과거 결함 익명화 누적 → 신제품에서 유사 패턴 자동 제안)
- **시험원 결정의 학습 사이클** (피드백 데이터로 AWT의 oracle·confidence 조정)

→ 장기적으로 일부 L2 항목은 *조건부 L1으로 승격* 가능. 단, 시험원 검토를 완전 제거하지 않음 (책임 소재).

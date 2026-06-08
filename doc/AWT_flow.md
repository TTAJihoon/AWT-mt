# AWT 동작 흐름 설명서

> 이 문서는 AWT(AI-driven Web Testing)의 전체 동작 흐름을 처음 보는 사람도 이해할 수 있도록 정리한 것입니다.
> 최종 갱신: 2026-05-22

---

## 한 줄 요약

**요구사항 문서(매뉴얼) + 테스트 대상 URL → TC 자동 설계 → 자동 실행 → 합격/불합격 판정 → Excel 보고서**

---

## 전체 흐름도

```
[입력]                    [처리]                         [출력]
───────────────────────────────────────────────────────────────
매뉴얼(md/pdf/docx)
  +                  →  Stage 1: 기능 추출          →  기능 목록 (leaf 단위)
대상 URL
  +                  →  Stage 2: TC 설계 (LLM)     →  TC 초안 (111개)
결함 카탈로그/invariant
                     →  Stage 3: TC 검증/보완       →  tc_verified.json
                     →  Stage 4: 사람 검토           →  승인/편집/반려
                     →  Stage 5: 자동 실행 (Playwright) →  PASS/FAIL
                     →  Stage 6: 실패 원인 분석 (LLM) →  결함 분류
                     →  Stage 7: Excel 산출          →  tc_final.xlsx
```

---

## 각 Stage 상세

### Stage 1 — 기능 추출
- **입력**: 매뉴얼 파일 (markdown, PDF, DOCX)
- **동작**: 문서를 파싱해 `대분류 > 중분류 > 소분류` 3단계 기능 계층 추출
- **출력**: 기능 목록 (예: "2.4 게시글 수정", "6.2 비밀글" 등 26개 leaf)
- **핵심**: 이후 모든 TC는 이 leaf 단위로 생성됨

---

### Stage 2 — TC 설계 (LLM 호출)
- **입력**: Stage 1의 기능 목록 + 매뉴얼 발췌 + 자산(결함 카탈로그, 설계 기법 invariants)
- **동작**: 소분류 하나당 LLM(Gemini)이 복수 TC 생성
  - `happy_path`: 정상 동작 검증
  - `negative_basic`: 잘못된 입력 처리
  - `negative_deep`: 보안·권한 경계
  - `boundary`: 입력값 경계
  - `state_transition`: 상태 변화 흐름
- **출력**: 시나리오/사전조건/기대결과/설계기법이 채워진 TC 목록

---

### Stage 3 — TC 검증 및 보완
- **동작**:
  - V1~V5: 형식 검증 (필수 필드, 중복, 모호한 기대결과 등)
  - V10: 누락 카테고리 자동 감지 → LLM으로 TC 추가 생성
  - 신뢰도 점수 부여 (gen_confidence)
- **출력**: `tc_verified.json` — 검토 준비 완료 TC

---

### Stage 4 — Reviewer Gate (사람 검토)
- **동작**: 시험원이 TC를 검토해 `approved / edited / rejected` 결정
- **핵심 설계 원칙**: **Stage 5 실행 전 반드시 사람이 승인** — 자동화만으로는 실행 불가
- **CLI 운영 시**: `--auto-approve` 플래그로 전체 자동 승인 가능 (내부 검토 완료 후)

---

### Stage 5 — Playwright 자동 실행 ★
- **입력**: 승인된 TC 목록 + 대상 URL
- **동작 흐름**:

```
픽스처 설정 (테스트 계정·게시글 생성)
    ↓
TC 1개씩 순서대로 실행
    ↓ (각 TC마다)
    ① 로그인 상태 전환 (없음 / 일반회원 / 관리자)
    ② 대상 URL 이동 (소분류별 URL 라우팅)
    ③ 액션 실행 (폼 입력·버튼 클릭)
    ④ 기대결과 키워드 매칭 → PASS / FAIL
    ↓
결과 기록
```

- **GnuBoard5 전용 엔진(D40)**:
  - gnuboard5 구조에 맞는 URL 26개 매핑
  - CAPTCHA 우회: PHP 헬퍼(`awt_fixture.php`)로 DB 직접 삽입
  - JS alert 자동 dismiss 처리 (Playwright 기본 동작)
  - 비로그인 리다이렉트, write_token 처리 등 gnuboard5 특성 반영

- **출력**: 각 TC에 `result(pass/fail/blocked)` + `actual(실제 화면 텍스트)` 기록

---

### Stage 6 — 실패 원인 분석
- **입력**: FAIL/BLOCKED TC 목록
- **동작**: V6 사전 분류 (선택자 안정성·oracle 명확도 점수 기반)
  - `app_defect`: 앱 로직 결함 — 선택자 안정, oracle 명확
  - `oracle_mismatch`: 기대결과 모호 — oracle 재정의 필요
  - `blocked`: 네트워크/환경 문제
- **출력**: 각 FAIL TC에 `failure_category` + `failure_reason` 기록

---

### Stage 7 — Excel 최종 산출
- **입력**: Stage 6까지의 모든 결과
- **출력**: `tc_final.xlsx`
  - 시트 1: TC 목록 + PASS/FAIL + 실제결과 + 실패 원인
  - 시험소 표준 양식에 맞춘 최종 산출물

---

## 이번 실행 결과 (gnuboard5 대상)

| 항목 | 값 |
|---|---|
| 대상 | gnuboard5 (http://localhost:8080) |
| TC 수 | 111개 |
| PASS | 108개 (97.3%) |
| FAIL | 3개 (2.7%) |
| 실행 시간 | 약 256초 |

### FAIL 3건 요약

| TC | 기능 | 원인 |
|---|---|---|
| TC-006-005 | 게시글 중복 제출 | gnuboard5 write_token 중복 차단 미동작 (앱 결함) |
| TC-009-001 | 게시글 삭제 | 삭제 실행 시 다른 TC 픽스처 파괴 방지를 위해 보류 (oracle 재정의 필요) |
| TC-023-001 | 주문/결제 완료 | 쇼핑몰 주문 플로우 미구성 (환경 미구성) |

---

## LLM API 사용량 (이번 실행)

| 구분 | 호출 수 | 입력 토큰 | 출력 토큰 | 합계 |
|---|---|---|---|---|
| TC_DESIGN (TC 설계) | 20회 | 34,938 | 14,934 | 49,872 |
| TC_REGEN (누락 보완) | 3회 | 11,822 | 4,770 | 16,592 |
| **합계** | **23회** | **46,760** | **19,704** | **66,464** |

- **사용 모델**: gemini-3.1-flash-lite (전량)
- **Stage 5·6 실행**: LLM 호출 없음 (Playwright + 규칙 기반 판정)
- **비고**: Stage 6 실패 분석도 V6 사전 마킹으로 LLM 호출 skip됨

---

## 핵심 설계 원칙

1. **사람 게이트 강제** — Stage 4 승인 없이 Stage 5 실행 불가
2. **LLM은 TC 설계만** — 실행·판정은 Playwright + 규칙 기반 (재현 가능성 확보)
3. **픽스처 분리** — 테스트 계정·데이터는 실행 전 독립적으로 준비 (다른 TC에 영향 없음)
4. **진짜 결함만 FAIL** — 테스트 엔진 버그는 수정, 앱 결함은 그대로 FAIL 기록

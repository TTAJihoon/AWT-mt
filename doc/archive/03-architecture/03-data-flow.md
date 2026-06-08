# 데이터 흐름 — 입력 변환 상세

**목적:** `01-high-level.md` §1·§6의 흐름을 *데이터 단위로 풀어 쓴* 문서. 각 입력이 어떤 변환을 거쳐 어떤 산출이 되는지 1:1 추적.
**참조 시점:** PoC 진행 중, 구현 단계 진입 시.

---

## 1. 입력 5종

사용자가 제품 1개당 입력 폴더에 배치:

| 입력 | 형식 | 필수 | AWT 처리 |
|---|---|---|---|
| 매뉴얼 | PDF / Word / PPT | ✓ | 텍스트 + 페이지 메타 추출 |
| 기능리스트 | Excel (대/중/소 분류 컬럼 고정) | ✓ | 행 단위 정규화, leaf 분류 추출 |
| URL | 텍스트 (단일 또는 다중) | ✓ | DOM 스캔, 이미지 스캔 시드 |
| 결함 샘플 | 품질특성별 문서 (Word/PDF/MD) | ✓ | 결함 패턴 추출, prompt 컨텍스트 주입 |
| 계정·인증 정보 (조건부) | 텍스트 또는 별도 안전 채널 | 보호 영역 진입 시 | 자동 로그인 시나리오 생성 |

---

## 2. 매뉴얼 변환

```
[원본 PDF/Word/PPT]
     │
     ▼ (스킬 anthropic-skills:pdf 또는 docx)
[텍스트 + 페이지/슬라이드 위치 메타]
     │
     ▼
[섹션 구조화: 제목 트리·기능 매핑 시도]
     │
     ▼
[source_quote 검색 인덱스]   ← Post 검증 V2의 grep 대상
     │
     ▼
[prompt 컨텍스트 주입 형태]   ← E1 prompt에 포함
```

**저장 위치:**
- `data/runs/<run-id>/manual_extracted.md`
- `data/runs/<run-id>/manual_index.json` (page → text mapping)

**한계:**
- PDF의 표·이미지 텍스트 추출은 OCR 의존 (스캔 PDF의 경우)
- PPT는 슬라이드 노트까지 포함하면 정보 풍부

**Confidence 영향:**
- 추출률 < 90% → 해당 기능의 `gen_confidence` 자동 하향

---

## 3. 기능리스트 변환

```
[원본 Excel]
     │
     ▼ (스킬 anthropic-skills:xlsx)
[행 단위 dict 리스트]
     │
     ▼ (대분류·중분류·소분류 컬럼 식별)
[leaf 분류 추출: 소분류 우선, 없으면 중분류, 없으면 대분류]
     │
     ▼
[leaf마다 sequential ID 부여 (TC-XXX의 XXX)]
     │
     ▼
[requirement_id 표준화: "대>중>소" 경로]
     │
     ▼
[기능별 메타: 입력 도메인 후보, 상태 다단계 여부 추정]
```

**저장 위치:**
- `data/runs/<run-id>/features_normalized.csv`
- `data/runs/<run-id>/features_meta.json`

**중요 규칙 (D17):**
- ID 자릿수 고정 3자리
- leaf 추출 우선순위: 소 > 중 > 대
- 상위 분류는 ID에 포함 안 됨 (metadata에만)

**E2 기법 매핑:**
- 각 leaf의 메타 추정으로 *적용 가능한 기법 set* 사전 계산
- 예: 다단계 워크플로 추정 → state_transition 기법 필수

---

## 4. URL → DOM / 이미지 변환

```
[URL 텍스트]
     │
     ▼ (기존 skill 또는 Playwright MCP)
[브라우저 접속, 페이지 로드 대기]
     │
     ▼
┌──────────────────────────┬──────────────────────────┐
│   DOM 스캔                │   이미지 스캔             │
│   • 페이지별 HTML 구조    │   • 페이지별 스크린샷     │
│   • 인터랙티브 요소 식별   │   • 디자인 토큰 추출      │
│   • 셀렉터 후보 사전 계산 │   • Layer 3 미적 자료     │
└──────────────────────────┴──────────────────────────┘
     │
     ▼
[DOM 인덱스: 페이지 → 요소 매트릭스]
[이미지 모음: data/runs/<run-id>/screenshots/]
```

**저장 위치:**
- `data/runs/<run-id>/dom_index.json`
- `data/runs/<run-id>/screenshots/`

**보호 영역 처리:**
- 로그인 필요 페이지는 *사전 인증 시나리오*가 시드로 실행되어야 진입 가능
- 인증 정보가 없으면 *공개 영역만 스캔*하고 보호 영역은 N/A 표시

**Multi-page 처리:**
- URL이 단일 진입점이면 link discovery로 N depth까지 자동 확장
- depth 한도 prompt에 명시 (기본 2~3)

---

## 5. 결함 샘플 변환

```
[품질특성별 결함 샘플 문서]
     │
     ▼
[결함 패턴 추출: 결함 유형 + 발생 상황 + 권고]
     │
     ▼
[품질특성별 분류]
     │
     ▼
[prompt 컨텍스트 주입 형태]   ← E2 prompt가 *유사 결함 패턴 인지*하게
     │
     ▼ (Phase 2)
[익명화 → RAG vector DB 축적]
```

**중요:**
- Phase 1에서는 *prompt 컨텍스트 주입*만 (RAG 본격 도입은 Phase 2)
- 결함 샘플은 *현재 시험할 제품과 동일 도메인*일 때 가치 큼

**Phase 1 prompt 주입 예:**
```
[참고 결함 패턴]
- 기능적 적합성: "비밀번호 변경 후 기존 세션이 유지되어 보안 노출" — 유사 패턴 시험 권장
- 사용성: "에러 메시지가 영어로만 표시" — 한국어 검증 권장
```

---

## 6. 인증·계정 정보 처리

**원칙:**
- 인증 정보는 **별도 안전 채널**로 받음 (입력 폴더에 평문 저장 *지양*)
- 옵션:
  - 환경 변수
  - 시험원이 별도 prompt 입력 시점에 직접 전달
  - 보안 저장소 (KeePass 등)

**처리:**
- 받은 인증 정보로 *자동 로그인 시나리오*를 시드로 실행
- 시나리오 자체는 TC로 저장하지만, *실제 자격 증명은 마스킹*
- 시험 종료 후 자격 증명을 *메모리에서 제거* + 로그에 노출 금지

**리스크:**
- 자격 증명 누출 시 RAG·메트릭·보고서에 포함되지 않도록 sanitization 강제 (D16 L2 결함 익명화 규칙과 동일 원칙)

---

## 7. 변환 데이터 → TC 생성 입력

5종 입력 변환 결과를 종합해 *TC 생성 prompt의 컨텍스트*가 됨:

```yaml
context:
  manual:
    extracted_text: "..."  # 매뉴얼 §2
    index_path: "data/runs/<run-id>/manual_index.json"
  features:
    leaves: [{id, path, meta}, ...]  # §3
    count: 87
  ui_structure:
    dom_index: "data/runs/<run-id>/dom_index.json"  # §4
    screenshots_dir: "data/runs/<run-id>/screenshots/"
  defect_patterns:
    by_characteristic: {"Functional": [...], "Usability": [...]}  # §5
  authentication:
    available_roles: ["admin", "user", "guest"]  # 마스킹된 메타만
```

이 컨텍스트가 `05-prompt-augmentation.md` §3.2의 사용자 메시지 wrapper에 채워짐.

---

## 8. TC 생성 → 결과까지

```
[TC 생성 input context]   (§7)
     │
     ▼ (기존 skill Stage 1 + E1·E2 prompt)
[TC Excel: tc_raw.xlsx]
     │
     ▼ (AWT Post 검증 V1~V5)
[tc_verified.xlsx + 검증 메타 v_meta.json]
     │
     ▼ (Reviewer Gate E5)
[tc_gated.xlsx + Gate 메타 g_meta.json]
     │
     ▼ (기존 skill Stage 2 또는 Playwright MCP — PoC-1 결과)
[tc_executed.xlsx + 실행 로그·스크린샷]
     │
     ▼ (AWT 결과 보강 E3·E4)
[tc_final.xlsx]
     │
     ▼ (보고서 작성)
[결함 리포트 + 메트릭 + L3 보조 자료]
```

각 단계 산출은 `data/runs/<run-id>/` 폴더에 누적 보관 (`01-high-level.md` §6).

---

## 9. 결과 → 메트릭 계산

```
[tc_final.xlsx]
     │
     ▼ (메트릭 계산기 — Phase 2 구현)
┌─────────────────────────────────────────────────┐
│  Functional Completeness  = ...                  │
│  Functional Correctness   = ...                  │
│  Defect Density           = ...                  │
│  Time Behavior (p50/p95)  = ...                  │
│  Browser Compatibility    = ...                  │
│  AWT Self-Audit           = ...                  │
└─────────────────────────────────────────────────┘
     │
     ▼
[metrics.json + (선택) 보고서 메트릭 시트]
```

Phase 1에서는 *수치 자동 계산은 안 함* — Phase 2 도입 (D21).

---

## 10. RAG로의 환류 (Phase 2)

```
[tc_final.xlsx]   +   [Gate reviewer_note]   +   [L3 exploratory notes]
     │
     ▼ (익명화 L1+L2 자동, L3+L4 수동 — D16)
[anonymized_run.json]
     │
     ▼ (RAG vector DB)
[다음 제품 시험 시 retrieve]
```

→ 시험소 차별화 자산 누적 흐름. Phase 2 본격 구현.

---

## 11. 분리 배포 sub-skill의 데이터 흐름 (예시)

- **`web-dom-scanner`** — URL → DOM/이미지 변환 (§4 부분)
- **`manual-to-feature-list`** — 매뉴얼 텍스트 → 기능리스트 후보 (역방향)
- **`tc-traceability-validator`** — TC Excel → source_quote grep 검증 (V2)
- **`anonymizer-for-defects`** — 결함 데이터 → 익명화 (§10 익명화 단계)
- **`axe-accessibility-runner`** — URL → axe 결과 (L2 Accessibility)
- **`mutation-score-runner`** — TC 집합 → mutation score (Phase 2)

각 sub-skill의 *입력·출력 사양*은 본 데이터 흐름의 *서브셋*. 외부 사용자가 단독 활용 가능하려면 입력 폴더 구조를 본 §1 그대로 받지 않고 *더 작은 단위*로 받아야 함 (예: `web-dom-scanner`는 URL만).

---

## 12. 데이터 보관·정리 정책

- `data/runs/<run-id>/` — 시험 1회당 폴더, 압축 보관 가능
- 보관 기간 — 시험소 정책에 따름 (제안: 인증 기간 + 1년)
- 익명화 누적 데이터 — `data/anonymized/` (보관 기간 정책 별도)
- 자격 증명 — 시험 종료 즉시 제거
- 메트릭 누적 — `data/metrics/` 영구 보관 (집계 추세 분석용)

---

## 13. 본 문서의 미해결 (구현 단계 결정)

| ID | 항목 | 결정 시점 |
|---|---|---|
| Q-DF-1 | `data/runs/` 디렉토리 구조의 *정확한 파일명 규약* | 구현 단계 |
| Q-DF-2 | 익명화 파이프라인의 *툴체인* (수동 검토 단계의 UI) | Phase 2 |
| Q-DF-3 | 인증 정보 *어느 안전 채널*을 시험소 표준으로 채택 | 운영 단계 |
| Q-DF-4 | multi-page 스캔의 *depth 기본값*과 동적 라우팅 처리 | PoC 또는 구현 단계 |

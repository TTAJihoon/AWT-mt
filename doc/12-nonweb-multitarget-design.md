# 12. 비(非)웹 대상 확장 설계 — API 라이브러리 / Windows 실행프로그램

> AWT 웹 코어(Stage 0~7)를 **재사용**하여 REST API · 로컬 코드 라이브러리(4언어) · Windows GUI 실행프로그램을 동일 파이프라인에서 시험하도록 확장한다.
> 결정 D59~D67. 사용자 확정(2026-06-08): 공용 코어 + 둘 다 동시 / 코어 재사용·확장 / PySide6 데스크탑 GUI / API는 REST+로컬 둘 다 / 로컬 언어 Python·.NET·Java·C 4종.

---

## 1. 핵심 통찰 — 교체 지점은 단 2곳

AWT의 Stage는 다음과 같이 분류된다.

| Stage | 입력/출력 | 제품 의존성 | 처리 |
|---|---|---|---|
| 0 Probe | URL → `feature_spec{features[]}` | **웹 전용 (DOM)** | ★교체 |
| 1 Ingest | 파일+spec → `leaves[]`, `manual_text` | 무관 | 재사용 |
| 1b Consolidate | leaves → leaves | 무관 | 재사용 |
| 2 TC 설계 | leaves+manual → TC[] | 무관 | 재사용 |
| 3 V1~V10 + REGEN | TC[] → TC[] | **V6만 웹 셀렉터** | 재사용(V6 일반화) |
| 4 Reviewer Gate | TC[] → TC[] | 무관 | 재사용 |
| 5 Execute | TC[] → TC[](result/actual) | **웹 전용 (Playwright)** | ★교체 |
| 6 실패분석 | TC[] → TC[] | 무관 | 재사용 |
| 7 Report | TC[] → xlsx | 무관 | 재사용+확장 |

→ **Stage 0와 Stage 5만 `target_kind`로 분기**하면 된다. leaf/TC 스키마가 공통 계약(P1 동결·P2 추적성)이므로 코어는 불변.

---

## 2. 플러그인 아키텍처 (D59)

`app/adapters/` 신설. 대상 유형별로 **3개 인터페이스 + 1개 번들**.

```python
# app/adapters/base.py
class Probe(Protocol):
    def scan(self, cfg: TargetConfig, llm, run_dir, progress_cb, should_stop) -> dict:
        """Stage 0 대체. feature_spec(= {url|target, features:[leaf...]}) 반환."""

class Executor(Protocol):
    def setup(self, cfg, ctx) -> None: ...
    def run_tc(self, tc: dict, ctx) -> None:
        """TC를 실행하고 tc['result'|'actual'|'exec_confidence'|'step_results']를 채움."""
    def teardown(self, ctx) -> None: ...

class OracleVerifier(Protocol):
    def verify(self, expected: str, actual: "Actual", methods: list[str]) -> "Verdict":
        """기대 vs 실제 → {status, confidence, evidence}."""

class TargetLocator(Protocol):
    def stability(self, target_ref: dict) -> float:   # V6 일반화
        ...

@dataclass
class TargetAdapter:
    target_kind: str                 # web | api_rest | api_code | gui
    probe: Probe
    make_executor: Callable[..., Executor]
    oracle: OracleVerifier
    locator: TargetLocator
    negative_category_map: Callable[[dict], list[str]]  # leaf → 적용 negative 카테고리
    grade_rules: Callable[[dict], tuple[str, str]]      # TC → (automation_grade, manual_action)
```

레지스트리(`app/adapters/registry.py`)가 `target_kind → TargetAdapter` 매핑. Orchestrator는 Stage 0/5에서 어댑터에 위임.

**원칙(토론 합의):** 인터페이스는 얇게, 구현은 plugin 내부에 두껍게. GUI의 OCR/팝업/플레이키 처리, API의 status/schema 비교는 각 어댑터 안에 격리 — 코어와 다른 어댑터는 모른다.

---

## 3. 대상별 어댑터 명세

### 3.1 web (기존, 어댑터로 래핑) — D60
- Probe = 기존 `stage0_dom_scan.scan` 위임
- Executor = 기존 `stage5_execute` 위임
- 동작 변화 0 (회귀 방지). 추상화 검증용.

### 3.2 api_rest — REST/HTTP API (OpenAPI) — D61
- **Probe**: OpenAPI/Swagger(JSON·YAML, 파일 또는 URL) 파싱 → **엔드포인트 1개 = leaf 1개**.
  - `category_major` = tag/resource, `category_leaf` = `METHOD path`(예: `POST /users`)
  - `implicit_spec` = 파라미터 타입·required·응답 코드·스키마 요약 (강한 명세 → INFERRED 최소)
  - `target_ref` = `{method, path, op_id, params_schema, responses}`
- **Executor**: `httpx`로 요청. base_url + 인증(헤더/토큰/OAuth) + test_data → status·body·headers·timing 수집.
- **Oracle**(강함, 대부분 A등급): status 코드 일치 / 응답 JSON 스키마 검증 / 필드 값 / 멱등성 / 에러 코드. "화면 표시 금지" 원칙 자동 충족.
- **negative_category 맵**: validation_failure=400/malformed body·타입오류, permission_denied=401/403·만료토큰, boundary_violation=길이·overflow·page limit, duplicate_or_conflict=409·동시요청, injection_or_security=SQLi/path traversal/oversized payload.
- **property/metamorphic**(Phase 2): 타입 파라미터 자동 경계폭격, 검색 포함관계 등.

### 3.3 api_code — 로컬 코드 라이브러리 (4언어) — D62
- **Probe(리플렉션)**: 대상 라이브러리의 공개 심볼 → **함수/메서드 1개 = leaf 1개**.
  - `implicit_spec` = 시그니처 + 파라미터 타입 + docstring/주석 + 반환·예외
  - `target_ref` = `{lang, module, symbol, signature}`
- **Executor(언어별 하네스)** — `app/adapters/api_code/runners/`:
  | 언어 | Probe 방식 | 호출 방식 | 의존 |
  |---|---|---|---|
  | python | `importlib`+`inspect` | in-process 호출 | (내장) |
  | dotnet | reflection (pythonnet) | pythonnet | `pythonnet` |
  | java | reflection (jpype) | jpype | `JPype1` |
  | c | 헤더/시그니처 명세 입력 | `ctypes`/`cffi` | (내장) |
  - C/네이티브는 리플렉션 불가 → 사용자가 함수 시그니처(헤더 또는 JSON)를 입력으로 제공.
- **Oracle**(강함): 반환값 비교 / 예외 타입·메시지 / side-effect(파일·DB) / 타입 계약.
- **격리**: 대상 라이브러리가 프로세스를 죽일 수 있으므로 **subprocess 샌드박스 실행 옵션**(특히 C/native)을 둔다.

### 3.4 gui — Windows 실행프로그램 — D63
업로드 가이드(§4.2~4.8) 전면 반영. 도구가 Python이므로 **Python UIA 스택**:
- **Product Profiler**: exe 실행·메인윈도우 탐지·권한·기동 대기(가이드 §4.2).
- **Probe(UIA)**: `uiautomation` 트리 수집 → 컨트롤/액션 = leaf. AutomationId/Name/ControlType/Rect/patterns. UIA 빈약 시 **OCR(`pytesseract`)+이미지(OpenCV) 폴백**.
- **Executor**: `pywinauto`(+`uiautomation`) set_value/invoke/select/check/wait; **팝업·모달 탐지** 필수; 조작 우선순위 = AutomationId → Name+ControlType → 부모경로 → Rect좌표 → OCR/이미지 → 수동(가이드 §4.6).
- **Oracle**(약함, 다중소스): UI 텍스트(OCR) + **로그 파일 + DB + 생성 파일** 우선(가이드 §8 검증 우선순위). 화면은 보조 증적.
- **EvidenceCollector**: 전/후/단계 스크린샷, UIA 스냅샷, 로그·DB·파일(가이드 §4.7 디렉터리 구조).

---

## 4. 스키마 확장 (D64) — 기존 G1~G6 유지, 추가만

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `target_kind` | enum | `web/api_rest/api_code/gui` |
| `target_ref` | object | 대상별 위치/호출 정보(§3) |
| `target_stability` | float | V6 일반화 점수 |
| `automation_grade` | enum | **A/B/C/D** (가이드 §5) |
| `manual_action_required` | string | C/D 시 수동 절차 |

**등급 체계 3축은 직교 — 통합하지 않음(토론 합의):**
- `layer`(L1/L2/L3) = ISO 특성의 자동화 *적합성* (설계 시점)
- `automation_grade`(A~D) = 이 TC의 실행 자동화 *가능성* (실행 지향)
- `gen/exec_confidence` = 신뢰도 점수

**자동화 등급 규칙(어댑터별 `grade_rules`):**
- **A**: target_stability ≥ τ_high **그리고** oracle이 객관(반환/예외/status/schema/로그/파일/DB/정확텍스트)
- **B**: 조작 가능하나 검증이 OCR/이미지 의존
- **C**: 일부 단계가 외부조건/사용자입력 필요(인증서·장비·네트워크)
- **D**: 자동화 차단/물리·보안모듈/수동판단 필수
- Reviewer Gate risk_score에 grade C/D를 가중 → 자동 "수동 검토" 버킷.

**실행 규칙(가이드 §9.3):** A 우선 자동 → B는 OCR/로그/파일 동반 → C는 자동 단계까지+수동지점 명시 → D는 미실행+수동절차 산출.

---

## 5. V6 일반화 → TargetStability (D65)

| target_kind | 안정성 산정 |
|---|---|
| web | 기존 9계층 셀렉터 점수 |
| api_rest | 계약 명시=0.95, OpenAPI 추론=0.85 (거의 항상 통과) |
| api_code | 시그니처 명시=0.95, 리플렉션=0.85, C 수기명세=0.7 |
| gui | AutomationId=0.90 / Name+ControlType=0.75 / 부모경로=0.6 / Rect좌표=0.4 / OCR·이미지=0.3 |

`app/validation/v6_selector_stability.py`를 `target_kind` 분기로 확장(웹 경로 불변).

---

## 6. 제품 유형 / 자산 (D66)

`product_types.py`에 신규 추가(형식 불변):
- `REST_API_AUTHZ`, `REST_API_CRUD`, `API_LIB_PY`, `API_LIB_NATIVE`, `WINDOWS_DESKTOP_CRUD`, `WINDOWS_DEVICE_CTRL` 등.
- `domain-invariants/*.yaml`·`defect-catalog/*.json` 형식 그대로, 신규 제품유형 디렉터리만 추가.
  - 예(REST): `jwt_expiration_enforcement`, `permission_scope_isolation`, `rate_limit_header`.
  - 예(GUI): `modal_dialog_modality`, `data_binding_consistency`, `undo_redo_scope`.

---

## 7. UI / 보고서 (D67)

- **Wizard**: 첫 화면에 **대상 유형 선택**(web/REST/코드라이브러리/GUI). 유형별 입력 폼 분기:
  - REST: OpenAPI 경로·base_url·인증
  - 코드라이브러리: 언어·모듈/DLL 경로·(C는 시그니처 파일)
  - GUI: exe 경로·실행인자·매뉴얼/기능리스트
- **Report**: 기존 Excel + **자동화 가능성 요약**(A/B/C/D 건수)·**수동확인 항목**·**종합의견**(가이드 §4.8). 증적 경로 인덱스.

---

## 8. 구현 단계 (Phase)

| # | 범위 | 산출 |
|---|---|---|
| P0 | 어댑터 골격(base/registry) + web 래핑(회귀 0) + 스키마 확장 + orchestrator 분기 | 추상화 검증 |
| P1 | **api_rest** end-to-end (Probe/Executor/Oracle, mock 가능) | REST 시험 동작 |
| P2 | **api_code: python** end-to-end | 로컬 라이브러리(파이썬) |
| P3 | api_code: dotnet/java/c 러너 | 4언어 완성 |
| P4 | **gui** Probe/Executor/Oracle + EvidenceCollector | Windows GUI 시험 |
| P5 | Wizard 분기 UI + Report 확장 | 사용자 완성 |

각 Phase는 기존 코어를 재사용하며 독립적으로 동작 가능. P0→P1 순으로 즉시 가치.

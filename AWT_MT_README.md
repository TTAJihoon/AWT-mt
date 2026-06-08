# AWT-MT — 멀티대상 시험 자동화 도구 (우리 제품)

이 폴더(`C:\AWT2\awt_mt`)가 **개발 중인 제품**이다.
원본 AWT(웹 전용)를 **재사용·확장**하여 **API 라이브러리 / Windows 실행프로그램**까지
동일 파이프라인에서 시험한다.

## 폴더 관계

| 폴더 | 역할 | 편집 |
|---|---|---|
| `C:\AWT2\awt_mt` | **우리 제품** (재사용 코어 + 우리 확장) | ✅ 여기서 개발 |
| `C:\AWT2\repo_awt` | GitHub 클론 — **읽기전용 설계 참고** (pristine) | ❌ 수정 금지 |

> 우리 제품은 AWT 코어의 **파생물(derivative)** 이다. "코어 재사용" 결정에 따라
> Stage 1~4·6·7 구현을 그대로 가져왔으므로, GitHub의 *구현 코드 일부가 이 폴더에
> 복사되어 포함*된다. (설계만 참고한 것이 아니라 코어 구현을 재사용함.)

## 우리가 추가/수정한 것 (확장분)

신규:
- `app/adapters/` — 대상 유형 플러그인
  - `base.py` `registry.py` `grading.py` — 골격(D59)
  - `web_adapter.py` — 기존 Stage 0/5 래핑(회귀 0, D60)
  - `api_rest_adapter.py` — REST/OpenAPI(D61)
  - `api_code_adapter.py` + `api_code/{python,c,dotnet,java}_runner.py` — 로컬 코드 라이브러리(D62)
  - `gui_adapter.py` — Windows UIA + OCR 폴백 + 증적(D63)
  - `report_summary.py` — 자동화등급 보고서(D67, 가이드 §4.8)
- `doc/12-nonweb-multitarget-design.md` — 확장 설계(D59~D67, 4인 토론 결론)
- `tests/test_{api_rest,api_code,api_code_multilang,gui}_adapter.py`, `test_report_summary.py`

수정(비침습):
- `app/core/orchestrator.py` — Stage 0/5를 `target_kind`로 어댑터에 위임 + RunConfig 필드
- `app/main.py` — meta↔RunConfig에 target_kind/target_config 라운드트립
- `app/core/stage7_output.py` — `report/test_report.md` 추가 산출

## 재사용(원본 그대로)
Stage 1 ingest · Stage 1b consolidate · Stage 2 TC설계 · Stage 3 V1~V10 · Stage 4 Reviewer Gate ·
Stage 6 실패분석 · Stage 7 Excel · TC 스키마 · taxonomy · assets(결함카탈로그·invariants) · LLM client.

## 테스트
```
cd C:\AWT2\awt_mt
python -m pytest tests/test_api_rest_adapter.py tests/test_api_code_adapter.py \
  tests/test_api_code_multilang.py tests/test_gui_adapter.py tests/test_report_summary.py -q
# → 22 passed
```
(주의: `tests/test_stage3_v10_regen.py`의 실패 1건은 **원본 저장소에 이미 있던 결함**으로 우리 작업과 무관.)

## 남은 작업
- **P5b**: `app/ui/wizard.py`에 대상유형 선택 폼(콤보 + 유형별 입력) — line 740 `RunConfig(...)`에
  `target_kind`/`target_config` 주입. PySide6 레이아웃이라 라이브 앱 시각 검증 필요.
- 선택 의존성 설치 시 동작: `.NET`=pythonnet, `Java`=JPype1, `GUI`=uiautomation/pywinauto(+pytesseract/opencv).

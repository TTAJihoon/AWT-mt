# AWT-MT — 멀티대상 시험 자동화 도구

원본 AWT(웹 전용)를 **재사용·확장**하여 **웹 / REST API / 로컬 코드 라이브러리(Python·.NET·Java·C) /
Windows 실행프로그램**을 **동일 파이프라인**에서 시험한다. ISO/IEC 25023 기반 TC 설계 →
자동 실행 → 결과 판정 → 보고서까지 end-to-end.

- 설계 근거: [doc/12-nonweb-multitarget-design.md](doc/12-nonweb-multitarget-design.md) (결정 D59~D67, 4인 토론)
- 원격: https://github.com/TTAJihoon/AWT-mt (`main`)

## 폴더 관계
| 폴더 | 역할 |
|---|---|
| `C:\AWT2\awt_mt` | **이 제품** (개발/편집) |
| `C:\AWT2\repo_awt` | GitHub 클론 — **읽기전용 설계 참고**(pristine, 수정 금지) |

> AWT 코어의 파생물 — "코어 재사용" 결정에 따라 Stage 1~4·6·7 구현이 포함됨.

## 아키텍처
**핵심**: Stage 1~4·6·7은 제품 무관 코어(재사용). 웹에 묶였던 **Stage 0(구조 스캔)·Stage 5(실행)만**
`target_kind`로 어댑터에 분기.

```
Stage 0 Probe(플러그인) → 1 Ingest → 1b Consolidate → 2 TC설계(LLM) → 3 V1~V10
   → 4 Reviewer Gate → 5 Execute(플러그인) → 6 실패분석 → 7 Excel+보고서
```
- 플러그인 인터페이스(`app/adapters/base.py`): `Probe` / `Executor` / `OracleVerifier` / `TargetLocator`
- 레지스트리(`app/adapters/registry.py`): `target_kind` → 어댑터. orchestrator가 Stage 0/5를 위임.

## 지원 대상
| target_kind | 스캐너(Probe) | 실행기(Executor) | 오라클 | 상태 |
|---|---|---|---|---|
| `web` | DOM(Playwright) | Playwright | UI/텍스트 | 기존 래핑(회귀 0) |
| `api_rest` | OpenAPI/Swagger | httpx | status·스키마(강) | ✅ 테스트·풀런 |
| `api_code` | 리플렉션 | Python/.NET/Java/C 러너 | 반환·예외(강) | ✅ Python 라이브, 그 외 코드완성 |
| `gui` | UIA(+OCR 폴백) | pywinauto/uiautomation | 로그·파일·DB·UI(약,다중) | ✅ 구현완성(데스크톱 필요) |

## 주요 기능
- **API-aware TC 설계**(`prompts/tc_design_api.md`): 비웹은 status·스키마위반·정확한 negative_category로 설계.
- **매뉴얼-무의존 값 합성**(`value_synth.py`): 파라미터 이름/타입/format 휴리스틱 → 매뉴얼 없이도 시험.
- **LLM test_data**(`llm_test_data.py`): docstring/명세 규칙 의존 값은 LLM이 생성(실행기가 우선 사용).
- **자동화 등급 A/B/C/D** + 수동확인 분리(가이드 §5·§9.3), `TargetStability`(V6 일반화).
- **증적**(`EvidenceCollector`) + **보고서**(`report_summary.py`: 등급요약·실패상세·수동확인·종합의견).
- **API 키 입력 UI**: 새 실행 시 `ApiKeyDialog` 자동 노출(또는 대시보드 설정 탭). Fernet 암호화 저장.

## 배포/설치 (클라이언트 .exe + 중앙 DB)
**중앙 DB(PostgreSQL)는 서버에서 가동**하고, 다른 PC에는 **클라이언트 실행파일만** 배포한다.
1. (배포 측, 1회) 빌드 머신에서 `.\installer\build.ps1` → `installer/output/AWT_Setup.exe` 생성·배포
   (Python 불필요한 단일 패키지 — `installer/PACKAGING.md`).
2. (사용자 PC) `AWT_Setup.exe` 실행으로 설치 → 앱 실행.
3. **첫 실행 시 ‘중앙 DB 접속 설정’ 창**에 host/port(+DB 계정) 입력 — **현재값이 미리 채워져 있고 수정 가능**.
   (로그인 창의 "DB 설정"으로 언제든 재설정)
4. **로그인 창에서 ID/PW** 입력.
   - 방화벽 등으로 DB 접속이 막혀도 **특별 관리자 계정 `jh91082`** 으로는 **DB 없이 로그인** 가능(break-glass, admin).

> 개발/소스 실행 또는 **중앙 DB 서버를 새로 세울 때**는 `setup.bat`(venv+의존성) /
> `installer/docker-compose.auth.yml`(PostgreSQL 컨테이너) / `installer/db_init.sql` 사용.

## Quickstart
```bash
# 테스트 (154 passed)
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q

# 데모 (외부 키 불필요)
python scripts/demo_nonweb.py          # api_code(python) + api_rest(로컬 HTTP) 어댑터
python scripts/demo_full_pipeline.py   # Stage 0~7 풀런(MockLLM) → tc_final.xlsx + 보고서
python scripts/demo_llm_direct.py      # 에이전트=LLM로 명세 기반 test_data 생성

# 라이브 다국어/GUI (도구·런타임·데스크톱 필요)
python examples/live-targets/run_live.py     # examples/live-targets/README.md 참고

# 앱 실행 / .exe 빌드
python -m app.main                      # 데스크톱 앱(로그인 DB 필요)
.\installer\build.ps1                   # PyInstaller+Inno Setup (installer/PACKAGING.md)
```

## 상태
- 테스트 **154 passed / 0 failed**.
- 선택 의존(pythonnet/JPype1/uiautomation/pywinauto)은 미설치 시 **안내 예외로 graceful 처리**.
- 실 LLM 라이브 풀런은 유효 키 필요(설정 다이얼로그 입력). `.NET/Java/C/GUI` 라이브 실행은 해당 런타임·데스크톱 필요.

## 디렉터리
```
app/adapters/      # 대상 어댑터(base·registry·web·api_rest·api_code(+runners)·gui·value_synth·llm_test_data·report_summary·grading)
app/core/          # Stage 0~7 코어(재사용)
app/ui/            # PySide6 (api_key_dialog·wizard·dashboard 등)
prompts/           # tc_design_api·tc_testdata 등 LLM 프롬프트
examples/live-targets/   # .NET/Java/C/GUI 샘플 + run_live
installer/         # PyInstaller spec + Inno Setup + PACKAGING.md
scripts/           # 데모(demo_nonweb·demo_full_pipeline·demo_llm_direct)
doc/12-...md       # 확장 설계(D59~D67)
```

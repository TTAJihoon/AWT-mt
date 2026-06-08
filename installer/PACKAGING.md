# 패키징/배포 (.exe) — AWT-MT

PySide6 데스크탑 앱을 Windows 단일 폴더 + 인스톨러로 빌드한다.
빌드는 **Windows 빌드 머신**(Python 3.11+, 인터넷)에서 수행한다.

## 빌드 (원클릭)
```powershell
.\installer\build.ps1
```
순서: venv 생성 → `pip install -r requirements.txt` + `pyinstaller` →
`playwright install chromium`(web 대상용) → `pyinstaller installer\awt.spec` →
(ISCC 있으면) `awt_setup.iss`로 인스톨러 생성.

산출물: `dist/AWT/AWT.exe` + (Inno Setup 설치 시) `installer/output/AWT_Setup.exe`.

## 번들 내용 (awt.spec)
- `app/` 전체 (어댑터 포함, hiddenimports로 동적 등록 모듈 명시)
- `prompts/` — TC 설계/검증 프롬프트(**tc_design_api.md·tc_testdata.md 포함**)
- `data/assets/` — 도메인 불변규칙(YAML) + 결함 카탈로그(JSON) (런타임 로더가 읽음)
- httpx/openai/anthropic 등 LLM·HTTP 의존

## 선택 의존성 (기본 번들 안 함)
아래는 해당 대상 시험에만 필요하며, 어댑터가 **미설치 시 안내 예외로 graceful 처리**한다.
사용하려면 **빌드 머신에 미리 설치**하면 자동 포함된다:
```powershell
pip install pythonnet      # 로컬 .NET(C#) 라이브러리 시험
pip install JPype1         # 로컬 Java 라이브러리 시험
pip install uiautomation pywinauto      # Windows GUI 시험
pip install pytesseract opencv-python   # GUI OCR/이미지 폴백
```
- .NET 대상은 빌드/실행 머신에 **.NET 런타임**, Java는 **JDK**가 별도로 있어야 한다.
- GUI 자동화는 **인터랙티브 데스크톱 세션**에서만 동작(서비스 세션 불가).

## API 키
- 최초 실행 시 새 실행을 누르면 **API 키 입력 다이얼로그**가 뜬다(또는 대시보드 설정 탭).
- 키는 머신 고유값으로 Fernet 암호화되어 `%USERPROFILE%\.awt\settings.enc`에 저장.

## 주의
- 헤드리스/CI 환경에서는 전체 GUI 빌드가 무겁고 실패하기 쉽다 → 반드시 데스크탑 빌드 머신 사용.
- `data/runs/`·`.env`·`secrets.json`은 .gitignore 대상(번들/커밋 제외).

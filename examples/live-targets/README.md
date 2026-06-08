# 라이브 시험 타깃 (작업 2)

`.NET / Java / C / GUI` 어댑터를 **실제 런타임·대상으로** 검증하기 위한 샘플 타깃과
실행 스크립트. 이 환경(현 개발 머신)에는 .NET/JDK/C 컴파일러/인터랙티브 데스크톱이
없어 실행 불가하므로, **도구가 갖춰진 Windows 머신**에서 아래 절차로 실행한다.

## 0. Python 브리지 설치 (공통)
```
pip install pythonnet JPype1 uiautomation pywinauto
# OCR 폴백까지 원하면: pip install pytesseract opencv-python
```

## 1. 각 타깃 빌드

| 대상 | 필요 | 빌드 명령 | 산출물 |
|---|---|---|---|
| .NET | .NET SDK 6+ | `cd dotnet && dotnet build -c Release` | `dotnet/bin/Release/netstandard2.0/Calculator.dll` |
| Java | JDK 8+ | `cd java && javac Calculator.java` | `java/Calculator.class` |
| C | MinGW gcc 또는 MSVC | `cd c && gcc -shared -o mathlib.dll mathlib.c`<br>(MSVC: `cl /LD mathlib.c`) | `c/mathlib.dll` |
| GUI | PySide6 (이미 설치됨) | (빌드 불필요) | `gui/sample_app.py` |

## 2. 실행
```
PYTHONIOENCODING=utf-8 python examples/live-targets/run_live.py
```
- 빌드 안 된 대상·런타임 없는 대상은 자동으로 `[SKIP]` 처리되고 안내가 출력된다.
- 결과는 콘솔 + `examples/live-targets/live_report.md`(자동화등급/결과 요약).

## 예상 동작
- **.NET**: `Calc.Add` happy → 정상 반환(2) PASS / `Calc.Divide` (b=0, test_data로 주입) → `DivideByZeroException` → 음성 기대대로 PASS
- **Java**: `Calculator.add` happy PASS / `Calculator.divide` (b=0) → `ArithmeticException` PASS
- **C**: `add`/`mul` happy PASS
- **GUI**: 샘플 앱을 띄워 UIA로 컨트롤 수집(Probe) 후, **실제 조작**까지 수행 —
  `txtInput`에 "안녕" 입력 → `btnEcho` 클릭 → `lblResult`가 "echo: 안녕"인지 검증(_run_live).
  전/후 스크린샷은 `evidence/`에 저장. (인터랙티브 데스크톱 세션 필수)

## 비고
- 각 언어 러너의 **심볼 리플렉션 + 호출 + 오라클(반환/예외)** 경로는 단위테스트로 검증됨
  (`tests/test_api_code_*`). 본 디렉터리는 *실 런타임 통합*을 확인하는 용도.
- GUI 실행 자동화는 **인터랙티브 데스크톱 세션**이 필수(서비스/헤드리스 세션에서는 UIA 불가).

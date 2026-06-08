"""작업2 라이브 실행 — 가용한 대상만 자동 감지해 어댑터로 실행.

도구/런타임/데스크톱이 갖춰진 머신에서 실행:
  PYTHONIOENCODING=utf-8 python examples/live-targets/run_live.py

각 대상은 (1) 빌드 산출물 존재 여부 (2) 런타임/브리지 설치 여부를 보고
없으면 건너뛰며 안내한다. README.md의 빌드·설치 절차를 먼저 수행하라.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))  # repo 루트(app 패키지)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.adapters import get_adapter
from app.adapters.grading import annotate_grades
from app.adapters.report_summary import build_report_md


def _tc(tc_id, leaf, tech, td=None, negcat=""):
    d = {"tc_id": tc_id, "소분류": leaf, "design_technique": tech,
         "negative_category": negcat, "expected": "", "review_status": "approved"}
    if td is not None:
        d["test_data"] = td
    return d


def _exec(kind, cfg, tcs, label):
    adapter = get_adapter(kind)
    try:
        spec = adapter.probe.scan(config=cfg, llm=None, run_dir=HERE,
                                  progress_cb=lambda m: None, should_stop=lambda: False)
    except Exception as e:  # noqa: BLE001 — 런타임/브리지/데스크톱 부재
        print(f"[SKIP] {label}: {str(e).splitlines()[0][:120]}")
        return []
    print(f"\n[{label}] leaf:", [f["category_leaf"] for f in spec["features"]][:12])
    if not tcs:
        return []
    adapter.executor.execute(tcs=tcs, config=cfg, run_dir=HERE, progress_cb=lambda m: None,
                             is_paused=lambda: False, is_stopped=lambda: False)
    annotate_grades(tcs, adapter)
    for tc in tcs:
        print(f"   [{tc['result'].upper():8}] {tc['tc_id']:12} {str(tc.get('소분류')):16} "
              f"grade={tc.get('automation_grade')} :: {str(tc.get('actual'))[:64]}")
    return tcs


def main() -> None:
    collected: list[dict] = []

    # ── .NET / C# (pythonnet) ────────────────────────────────────────────
    dll = HERE / "dotnet" / "bin" / "Release" / "netstandard2.0" / "Calculator.dll"
    if dll.exists():
        cfg = SimpleNamespace(target_config={
            "lang": "dotnet", "dll_path": str(dll), "types": ["Calculator.Calc"]})
        collected += _exec("api_code", cfg, [
            _tc("TC-NET-001", "Calc.Add", "happy_path"),
            _tc("TC-NET-002", "Calc.Divide", "negative_basic",
                td={"kwargs": {"a": 1, "b": 0}, "expect_exception": True},
                negcat="boundary_violation"),
        ], ".NET/C#")
    else:
        print("[SKIP] .NET: examples/live-targets/dotnet 에서 `dotnet build -c Release` 먼저")

    # ── Java (JPype1 + JDK) ──────────────────────────────────────────────
    if (HERE / "java" / "Calculator.class").exists():
        cfg = SimpleNamespace(target_config={
            "lang": "java", "classpath": str(HERE / "java"), "classes": ["Calculator"]})
        collected += _exec("api_code", cfg, [
            _tc("TC-JAVA-001", "Calculator.add", "happy_path"),
            _tc("TC-JAVA-002", "Calculator.divide", "negative_basic",
                td={"kwargs": {"arg0": 1, "arg1": 0}, "expect_exception": True}),
        ], "Java")
    else:
        print("[SKIP] Java: examples/live-targets/java 에서 `javac Calculator.java` 먼저")

    # ── C 네이티브 DLL (ctypes) ──────────────────────────────────────────
    cdll = HERE / "c" / "mathlib.dll"
    if cdll.exists():
        cfg = SimpleNamespace(target_config={
            "lang": "c", "dll_path": str(cdll),
            "signatures_path": str(HERE / "c" / "signatures.json")})
        collected += _exec("api_code", cfg, [
            _tc("TC-C-001", "add", "happy_path"),
            _tc("TC-C-002", "mul", "happy_path"),
        ], "C/native")
    else:
        print("[SKIP] C: examples/live-targets/c 에서 `gcc -shared -o mathlib.dll mathlib.c` 먼저")

    # ── GUI (uiautomation/pywinauto + 인터랙티브 데스크톱) ───────────────
    #     _run_live가 실제 UIA 조작(입력→클릭→결과 검증)을 수행한다(데스크톱 필요).
    cfg = SimpleNamespace(target_config={
        "exe_path": sys.executable,
        "args": [str(HERE / "gui" / "sample_app.py")],
        "window_title": "AWT Sample App", "startup_wait": 3.0})
    gui_tcs = [
        {"tc_id": "TC-GUI-001", "소분류": "txtInput", "design_technique": "happy_path",
         "scenario": "입력창에 텍스트 입력", "test_data": {"value": "안녕"},
         "expected": "입력값 반영", "review_status": "approved", "verification_methods": []},
        {"tc_id": "TC-GUI-002", "소분류": "btnEcho", "design_technique": "happy_path",
         "scenario": "Echo 버튼 클릭", "expected": "echo: 안녕",
         "review_status": "approved", "verification_methods": []},
    ]
    _exec("gui", cfg, gui_tcs, "GUI(샘플 PySide6 앱)")

    # ── 보고서 ───────────────────────────────────────────────────────────
    if collected:
        out = HERE / "live_report.md"
        out.write_text(build_report_md(collected,
                       meta={"run_id": "live", "target_kind": "api_code(live)"}),
                       encoding="utf-8")
        print(f"\n보고서 → {out}")


if __name__ == "__main__":
    main()

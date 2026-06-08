"""api_code 어댑터 (D62) — 로컬 코드 라이브러리 (Python/.NET/Java/C).

언어별 Runner가 심볼 리플렉션 + 호출을 담당. 어댑터는 공통 흐름만 가진다.
오라클(강함): 정상 기법=무예외 / 음성 기법=예외 발생 → 등급 대부분 A.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.adapters.api_code.base_runner import Runner, Symbol, synth_call, _POSITIVE_TECH
from app.adapters.base import ProgressCb, StopFn, TargetAdapter, Verdict
from app.adapters.registry import register


def _get_runner(lang: str | None) -> Runner:
    lang = (lang or "python").lower()
    if lang in ("python", "py"):
        from app.adapters.api_code.python_runner import PythonRunner
        return PythonRunner()
    if lang in ("dotnet", ".net", "csharp", "cs"):
        from app.adapters.api_code.dotnet_runner import DotNetRunner
        return DotNetRunner()
    if lang == "java":
        from app.adapters.api_code.java_runner import JavaRunner
        return JavaRunner()
    if lang in ("c", "native", "dll"):
        from app.adapters.api_code.c_runner import CRunner
        return CRunner()
    raise ValueError(f"api_code: 미지원 언어 {lang!r}")


def _spec_text(sym: Symbol) -> str:
    lines = [f"{sym.name}{sym.signature}".strip()]
    if sym.returns:
        lines.append(f"반환: {sym.returns}")
    if sym.doc:
        lines.append(sym.doc[:400])
    if sym.params:
        req = [p["name"] for p in sym.params if p.get("required")]
        if req:
            lines.append("필수 인자: " + ", ".join(req))
    if sym.raises:
        lines.append("발생 예외: " + ", ".join(sym.raises))
    return "\n".join(lines)


class CodeOracle:
    def verify(self, expected: str, actual: Any, methods: list[str]) -> Verdict:
        # actual = {"result": invoke결과|None, "expect_exception": bool, "skipped": bool}
        if actual.get("skipped"):
            return Verdict("blocked", 0.3, "인자 없는 함수 — 음성 합성 불가(수동)", [])
        r = actual["result"]
        expect_exc = actual["expect_exception"]
        raised = (not r["ok"])
        if expect_exc:
            ok = raised
            msg = (f"예외 {r['exception']} 발생(기대대로)" if raised
                   else f"예외 없음(반환 {r['return']}) — 기대 위반")
        else:
            ok = not raised
            msg = (f"정상 반환: {r['return']}" if not raised
                   else f"예기치 않은 예외 {r['exception']}: {r['message']}")
        return Verdict("pass" if ok else "fail", 0.85, msg, [])


class ApiCodeProbe:
    def scan(self, *, config: Any, llm: Any, run_dir: Path,
             progress_cb: ProgressCb, should_stop: StopFn):
        tc = config.target_config or {}
        runner = _get_runner(tc.get("lang"))
        syms = runner.list_symbols(tc)
        mod_name = Path(str(tc.get("module_path") or tc.get("module") or "lib")).stem
        progress_cb(f"  {runner.lang} 리플렉션 — 심볼 {len(syms)}개 ({mod_name})")
        features = [{
            "category_major": mod_name,
            "category_mid": "함수",
            "category_leaf": s.symbol,
            "implicit_spec": _spec_text(s),
            "confidence": "HIGH",
            "source_url": mod_name,
            "source_element": s.qualname or s.name,
        } for s in syms]
        return {"target": mod_name, "code_lib": True,
                "lang": runner.lang, "pages_scanned": len(features),
                "features": features}


class ApiCodeExecutor:
    def execute(self, *, tcs: list[dict], config: Any, run_dir: Path,
                progress_cb: ProgressCb, is_paused: StopFn, is_stopped: StopFn):
        tcfg = config.target_config or {}
        runner = _get_runner(tcfg.get("lang"))
        smap = {s.symbol: s for s in runner.list_symbols(tcfg)}
        oracle = CodeOracle()

        runnable = [tc for tc in tcs if tc.get("review_status") in ("approved", "edited")]
        progress_cb(f"Stage 5(api_code/{runner.lang}): {len(runnable)}개 TC 실행")

        for i, tc in enumerate(runnable, 1):
            if is_stopped and is_stopped():
                progress_cb(f"⏹ 중단 — {i-1}/{len(runnable)} 후 종료")
                break
            sym = smap.get((tc.get("소분류") or "").strip())
            if sym is None:
                tc["result"] = "blocked"
                tc["actual"] = f"심볼 매핑 실패: {tc.get('소분류')!r}"
                tc["exec_confidence"] = 0.2
                continue
            # test_data 우선(LLM/사용자 제공) → 없으면 휴리스틱 합성
            td = tc.get("test_data") or {}
            if isinstance(td, dict) and ("kwargs" in td or "args" in td):
                kwargs = td.get("kwargs", {})
                expect_exc = bool(td.get("expect_exception",
                                         tc.get("design_technique", "") not in _POSITIVE_TECH
                                         and tc.get("design_technique", "") != ""))
                synth = (kwargs, expect_exc)
            else:
                synth = synth_call(sym, tc.get("design_technique", ""), tc.get("negative_category", ""))
            if synth is None:
                verdict = oracle.verify(tc.get("expected", ""), {"skipped": True}, [])
            else:
                kwargs, expect_exc = synth
                res = runner.invoke(sym, list(td.get("args", [])), kwargs, tcfg)
                verdict = oracle.verify(
                    tc.get("expected", ""),
                    {"result": res, "expect_exception": expect_exc, "skipped": False}, [])
            tc["result"] = verdict.status
            tc["actual"] = verdict.actual
            tc["exec_confidence"] = verdict.confidence
            tc["target_ref"] = {"lang": runner.lang, "symbol": sym.symbol, "explicit": True}
            progress_cb(f"  ({i}/{len(runnable)}) {tc['tc_id']} {sym.symbol} → {tc['result']}")

        for tc in tcs:
            if tc.get("review_status") not in ("approved", "edited"):
                tc["result"] = "not_executed"
        progress_cb(f"Stage 5(api_code/{runner.lang}) 완료")
        return tcs


class _CodeLocator:
    def stability(self, target_ref: dict) -> float:
        return 0.95 if target_ref.get("explicit") else 0.7


def _code_negative_map(leaf: dict) -> list[str]:
    return ["validation_failure", "boundary_violation", "injection_or_security"]


def _code_grade(tc: dict, adapter: TargetAdapter) -> tuple[str, str]:
    if tc.get("result") == "blocked":
        return "C", "수동 호출 확인 필요(인자/인스턴스 합성 불가)"
    return "A", ""


def _factory() -> TargetAdapter:
    return TargetAdapter(
        target_kind="api_code",
        probe=ApiCodeProbe(),
        executor=ApiCodeExecutor(),
        locator=_CodeLocator(),
        oracle=CodeOracle(),
        negative_category_map=_code_negative_map,
        grade_rules=_code_grade,
        label="로컬 코드 라이브러리",
    )


register("api_code", _factory, label="로컬 코드 라이브러리")

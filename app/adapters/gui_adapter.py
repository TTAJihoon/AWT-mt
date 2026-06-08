"""gui 어댑터 (D63) — Windows 실행프로그램 (UIA + OCR 폴백 + 내부상태 검증).

업로드 가이드(§4.2~4.8) 반영. 도구가 Python이므로 uiautomation + pywinauto 스택.
무거운/선택적 의존(uiautomation, pywinauto, pytesseract, cv2)은 scan/execute
시점에만 lazy import. 미설치 시 명확한 안내 예외.

오라클(약함, 다중소스): 화면 표시만으로 판정 금지(가이드 §8). 검증 우선순위
  DB > 생성 파일 > 로그 > UI 텍스트(OCR) > 이미지 비교 > 수동.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from app.adapters.base import ProgressCb, StopFn, TargetAdapter, Verdict
from app.adapters.registry import register


# ─────────────────────────────────────────────────────────────────────────────
# 순수 로직 (의존성 불필요 — 단위 테스트 대상)
# ─────────────────────────────────────────────────────────────────────────────
def gui_stability(ref: dict) -> float:
    """조작 우선순위 기반 안정성(가이드 §4.6·§9.1)."""
    if ref.get("automation_id"):
        return 0.90
    if ref.get("name") and ref.get("control_type"):
        return 0.75
    if ref.get("parent_path"):
        return 0.60
    if ref.get("rect"):
        return 0.40
    if ref.get("ocr") or ref.get("image"):
        return 0.30
    return 0.55


# 자동화 곤란 신호 (가이드 §5·§6)
_D_SIGNALS = ("보안키패드", "보안 키패드", "물리 장비", "실제 선박", "하드웨어 키", "지문", "생체")
_C_SIGNALS = ("인증서", "장비 연결", "시리얼", "com 포트", "usb", "외부 장비", "네트워크 장비", "스캐너")
_OBJECTIVE_VERIF = ("로그", "log", "파일", "file", "db", "데이터베이스", "디비")
_OCR_VERIF = ("ocr", "이미지", "화면", "스크린샷", "캡처")


def gui_grade(tc: dict) -> tuple[str, str]:
    """A/B/C/D 등급 + 수동조치(가이드 §5). target_ref 없으면 TC 텍스트 신호로 추정."""
    text = " ".join(str(tc.get(k, "")) for k in (
        "scenario", "precondition", "expected", "소분류", "중분류"))
    methods = " ".join(str(m) for m in (tc.get("verification_methods") or [])).lower()
    low = text.lower()
    if any(s in low for s in _D_SIGNALS):
        return "D", "물리 장비/보안 모듈 — 수동 시험 절차로 분리(자동 미실행)"
    if any(s in low for s in _C_SIGNALS):
        return "C", "외부 장비/인증서 조건 — 자동 단계까지만 수행 후 수동 확인"
    if any(s in (methods + low) for s in _OBJECTIVE_VERIF):
        return "A", ""
    if any(s in (methods + low) for s in _OCR_VERIF):
        return "B", ""
    return "B", ""   # GUI 기본 — 화면 검증 의존 가능성 → 보수적으로 B


def gui_negative_map(leaf: dict) -> list[str]:
    name = (leaf.get("category_leaf") or "") + (leaf.get("category_mid") or "")
    cats = ["validation_failure", "boundary_violation"]
    if any(k in name for k in ("권한", "로그인", "로그아웃", "관리")):
        cats.append("permission_denied")
    if any(k in name for k in ("등록", "저장", "추가", "생성")):
        cats.append("duplicate_or_conflict")
    return cats


class GuiOracle:
    """다중소스 검증(가이드 §8). 화면은 보조, 내부상태(로그/파일/DB) 우선."""

    @staticmethod
    def verify_file_exists(path: str, min_size: int = 1) -> bool:
        p = Path(path)
        return p.exists() and p.stat().st_size >= min_size

    @staticmethod
    def verify_log_contains(log_path: str, needle: str) -> bool:
        try:
            txt = Path(log_path).read_text(encoding="utf-8", errors="replace")
        except Exception:
            return False
        return needle in txt

    @staticmethod
    def verify_db_value(db_path: str, query: str, expected: Any) -> bool:
        try:
            con = sqlite3.connect(db_path)
            row = con.execute(query).fetchone()
            con.close()
        except Exception:
            return False
        if row is None:
            return expected in (None, "", 0)
        return str(row[0]) == str(expected)

    @staticmethod
    def verify_text(haystack: str, expected: str) -> bool:
        quoted = re.findall(r"[`'\"](.+?)[`'\"]", expected)
        keys = quoted or [w for w in expected.split() if len(w) > 2][:5]
        return any(k in (haystack or "") for k in keys) if keys else False

    def verify(self, expected: str, actual: dict, methods: list[str]) -> Verdict:
        """actual = {db:{path,query,expected}, files:[...], log:{path,needle}, ui_text:str}."""
        # 우선순위: DB > 파일 > 로그 > UI
        if actual.get("db"):
            d = actual["db"]
            ok = self.verify_db_value(d["path"], d["query"], d.get("expected"))
            return Verdict("pass" if ok else "fail", 0.92, f"DB 검증={ok}", [])
        for f in actual.get("files", []):
            if self.verify_file_exists(f):
                return Verdict("pass", 0.88, f"파일 생성 확인: {f}", [f])
        if actual.get("log"):
            lg = actual["log"]
            ok = self.verify_log_contains(lg["path"], lg["needle"])
            return Verdict("pass" if ok else "fail", 0.82, f"로그 검증={ok}", [lg["path"]])
        if actual.get("ui_text") is not None:
            ok = self.verify_text(actual["ui_text"], expected)
            return Verdict("pass" if ok else "fail", 0.55, f"UI 텍스트 검증={ok}", [])
        return Verdict("blocked", 0.3, "검증 가능한 내부상태/화면 없음 — 수동 확인", [])


class EvidenceCollector:
    """가이드 §4.7 증적 디렉터리 구조."""

    def __init__(self, run_dir: Path):
        self.base = Path(run_dir) / "evidence"
        self.base.mkdir(parents=True, exist_ok=True)

    def path(self, tc_id: str, name: str) -> Path:
        d = self.base
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{tc_id}_{name}"

    def save_text(self, tc_id: str, name: str, text: str) -> str:
        p = self.path(tc_id, name)
        p.write_text(text, encoding="utf-8")
        return str(p)


# ─────────────────────────────────────────────────────────────────────────────
# 라이브 경로 (의존성 필요 — lazy import)
# ─────────────────────────────────────────────────────────────────────────────
def _require_uia():
    try:
        import uiautomation  # noqa: F401
        import pywinauto  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "gui 대상: uiautomation/pywinauto 미설치. "
            "`pip install uiautomation pywinauto` (OCR 폴백은 pytesseract opencv-python) 후 재시도."
        ) from e


class GuiProbe:
    def scan(self, *, config: Any, llm: Any, run_dir: Path,
             progress_cb: ProgressCb, should_stop: StopFn):
        _require_uia()
        import uiautomation as auto
        import subprocess
        import time

        tc = config.target_config or {}
        exe = tc.get("exe_path")
        if not exe:
            raise ValueError("gui: target_config['exe_path'] 필요")
        progress_cb(f"  앱 실행: {exe}")
        subprocess.Popen([exe, *(tc.get("args") or [])])
        time.sleep(float(tc.get("startup_wait", 3.0)))

        title_re = tc.get("window_title")
        win = auto.WindowControl(searchDepth=2, RegexName=title_re) if title_re \
            else auto.GetForegroundControl()
        features: list[dict] = []
        out = Path(run_dir) / "gui-scan"
        out.mkdir(parents=True, exist_ok=True)

        def walk(ctrl, depth=0, parent=""):
            if depth > int(tc.get("max_depth", 6)):
                return
            for child in ctrl.GetChildren():
                ctype = child.ControlTypeName
                name = child.Name or ""
                aid = getattr(child, "AutomationId", "") or ""
                if ctype in ("ButtonControl", "EditControl", "ComboBoxControl",
                             "CheckBoxControl", "MenuItemControl", "DataGridControl",
                             "ListControl", "TabItemControl"):
                    ref = {"automation_id": aid, "name": name,
                           "control_type": ctype, "parent_path": parent}
                    features.append({
                        "category_major": (title_re or "앱"),
                        "category_mid": ctype.replace("Control", ""),
                        "category_leaf": name or aid or ctype,
                        "implicit_spec": f"{ctype} '{name}' (AutomationId={aid})",
                        "confidence": "HIGH" if aid else "MID",
                        "source_url": title_re or "main",
                        "source_element": aid or name,
                        "target_ref": ref,
                    })
                walk(child, depth + 1, f"{parent}/{name or ctype}")

        walk(win)
        progress_cb(f"  UIA 트리 — 컨트롤 {len(features)}개 수집")
        if not features and tc.get("ocr_fallback", True):
            progress_cb("  UIA 빈약 → OCR 폴백 권장(가이드 §7) — 별도 구성 필요")
        return {"target": exe, "gui": True,
                "pages_scanned": 1, "features": features}


class GuiExecutor:
    def execute(self, *, tcs: list[dict], config: Any, run_dir: Path,
                progress_cb: ProgressCb, is_paused: StopFn, is_stopped: StopFn):
        oracle = GuiOracle()
        evidence = EvidenceCollector(run_dir)
        runnable = [tc for tc in tcs if tc.get("review_status") in ("approved", "edited")]
        progress_cb(f"Stage 5(gui): {len(runnable)}개 TC — 등급별 실행 정책 적용")

        # D/C 등급은 라이브 의존성 없이도 분류·수동절차 산출 가능(가이드 §9.3)
        live_needed = False
        for tc in runnable:
            grade, manual = gui_grade(tc)
            tc["automation_grade"] = grade
            if grade == "D":
                tc["result"] = "not_executed"
                tc["manual_action_required"] = manual
                tc["actual"] = "자동화 곤란(D) — 수동 시험 절차 분리"
            elif grade == "C":
                tc["result"] = "needs_manual_review"
                tc["manual_action_required"] = manual
                tc["actual"] = "반자동(C) — 자동 단계까지만, 외부조건 수동 확인"
            else:
                live_needed = True

        if live_needed:
            _require_uia()  # A/B 등급은 실제 UIA 조작 필요
            self._run_live([tc for tc in runnable
                            if tc.get("automation_grade") in ("A", "B")],
                           config, oracle, evidence, progress_cb, is_stopped)

        for tc in tcs:
            if tc.get("review_status") not in ("approved", "edited"):
                tc["result"] = "not_executed"
        progress_cb("Stage 5(gui) 완료")
        return tcs

    def _run_live(self, tcs, config, oracle, evidence, progress_cb, is_stopped):
        import uiautomation as auto  # noqa: F401  (실행 환경에서만)
        # 실제 UIA 조작·증적 수집은 대상 앱 종속 — 프레임만 제공.
        for tc in tcs:
            if is_stopped and is_stopped():
                break
            # TODO(P4-live): target_ref로 컨트롤 탐색 → 액션 수행 → 다중소스 오라클.
            tc.setdefault("result", "blocked")
            tc.setdefault("actual", "라이브 UIA 실행 프레임 — 대상 앱 연결 필요")


class _GuiLocator:
    def stability(self, target_ref: dict) -> float:
        return gui_stability(target_ref or {})


def _factory() -> TargetAdapter:
    return TargetAdapter(
        target_kind="gui",
        probe=GuiProbe(),
        executor=GuiExecutor(),
        locator=_GuiLocator(),
        oracle=GuiOracle(),
        negative_category_map=gui_negative_map,
        grade_rules=lambda tc, _a: gui_grade(tc),
        label="Windows 실행프로그램 (UIA)",
    )


register("gui", _factory, label="Windows 실행프로그램 (UIA)")

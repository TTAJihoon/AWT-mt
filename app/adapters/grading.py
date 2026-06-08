"""TC 자동화 등급/대상 메타 주석 (D64).

layer(L1/L2/L3) · automation_grade(A~D) · confidence 3축은 직교 — 통합하지 않는다.
이 모듈은 automation_grade 와 target 메타만 채운다.
"""
from __future__ import annotations

from app.adapters.base import TargetAdapter


def annotate_grades(tcs: list[dict], adapter: TargetAdapter) -> None:
    """실행/검증 후 각 TC에 target_kind / target_stability / automation_grade 주석."""
    for tc in tcs:
        tc.setdefault("target_kind", adapter.target_kind)
        ref = tc.get("target_ref") or {}
        if adapter.locator is not None and "target_stability" not in tc:
            try:
                tc["target_stability"] = round(float(adapter.locator.stability(ref)), 2)
            except Exception:
                pass
        if adapter.grade_rules is not None and not tc.get("automation_grade"):
            try:
                grade, manual = adapter.grade_rules(tc, adapter)
                tc["automation_grade"] = grade
                if manual:
                    tc["manual_action_required"] = manual
            except Exception:
                pass

"""자동화 가능성/수동확인 보고서 요약 (D67, 가이드 §4.8).

excel_builder는 건드리지 않고, tc_final.xlsx 옆에 test_report.md를 추가 산출.
순수 함수 — 단위 테스트 가능.
"""
from __future__ import annotations

from collections import Counter

_GRADE_MEANING = {
    "A": "완전 자동화", "B": "부분 자동화(OCR/이미지/로그)",
    "C": "반자동(외부조건/수동)", "D": "자동화 곤란(수동 시험)",
}
_RESULT_LABEL = {
    "pass": "PASS", "fail": "FAIL", "blocked": "BLOCKED",
    "not_executed": "미실행", "needs_manual_review": "수동확인필요",
}


def automation_summary(tcs: list[dict]) -> dict:
    grades = Counter(tc.get("automation_grade", "") or "(미부여)" for tc in tcs)
    results = Counter(tc.get("result", "") or "(미실행)" for tc in tcs)
    manual = [tc for tc in tcs
              if tc.get("automation_grade") in ("C", "D")
              or tc.get("result") == "needs_manual_review"
              or tc.get("manual_action_required")]
    failures = [tc for tc in tcs if tc.get("result") == "fail"]
    return {
        "total": len(tcs),
        "grades": dict(grades),
        "results": dict(results),
        "manual_count": len(manual),
        "fail_count": len(failures),
        "manual": manual,
        "failures": failures,
    }


def build_report_md(tcs: list[dict], meta: dict | None = None) -> str:
    s = automation_summary(tcs)
    meta = meta or {}
    target_kind = meta.get("target_kind") or (tcs[0].get("target_kind") if tcs else "") or "-"
    out: list[str] = []
    out.append("# 시험 결과 보고서\n")
    out.append("## 1. 개요")
    out.append(f"- 대상 유형: **{target_kind}**")
    out.append(f"- run_id: {meta.get('run_id', '-')}")
    out.append(f"- 전체 TC: {s['total']}건\n")

    out.append("## 2. 자동화 가능성 요약")
    out.append("| 등급 | 의미 | 건수 |")
    out.append("|---|---|---:|")
    for g in ("A", "B", "C", "D"):
        if g in s["grades"]:
            out.append(f"| {g} | {_GRADE_MEANING[g]} | {s['grades'][g]} |")
    for g, n in s["grades"].items():
        if g not in ("A", "B", "C", "D"):
            out.append(f"| {g} | - | {n} |")
    out.append("")

    out.append("## 3. 수행 결과 요약")
    out.append("| 구분 | 건수 |")
    out.append("|---|---:|")
    for k, label in _RESULT_LABEL.items():
        if k in s["results"]:
            out.append(f"| {label} | {s['results'][k]} |")
    for k, n in s["results"].items():
        if k not in _RESULT_LABEL:
            out.append(f"| {k} | {n} |")
    out.append("")

    out.append("## 4. 실패 TC 상세")
    if s["failures"]:
        out.append("| TC ID | 기능 | 기대 | 실제 |")
        out.append("|---|---|---|---|")
        for tc in s["failures"][:200]:
            out.append("| {id} | {leaf} | {exp} | {act} |".format(
                id=tc.get("tc_id", ""), leaf=tc.get("소분류", ""),
                exp=str(tc.get("expected", ""))[:80].replace("|", "/"),
                act=str(tc.get("actual", ""))[:80].replace("|", "/")))
    else:
        out.append("실패 TC 없음.")
    out.append("")

    out.append("## 5. 수동 확인 필요 항목")
    if s["manual"]:
        out.append("| TC ID | 등급 | 수동 조치 |")
        out.append("|---|---|---|")
        for tc in s["manual"][:200]:
            out.append("| {id} | {g} | {m} |".format(
                id=tc.get("tc_id", ""), g=tc.get("automation_grade", ""),
                m=str(tc.get("manual_action_required", "") or tc.get("actual", ""))[:90].replace("|", "/")))
    else:
        out.append("수동 확인 필요 항목 없음.")
    out.append("")

    auto_n = s["grades"].get("A", 0) + s["grades"].get("B", 0)
    out.append("## 6. 종합 의견")
    out.append(
        f"- 자동 실행 가능(A·B) {auto_n}건 / 수동·반자동(C·D) {s['manual_count']}건. "
        f"실패 {s['fail_count']}건은 실패 상세를 검토하고, "
        f"selector/계약 문제와 제품 결함을 구분해 판정하라(가이드 §9.3).")
    return "\n".join(out)

"""Stage 6 — 실패 TC 원인 분석 (LLM FAILURE_ANALYSIS v2.1 호출).

v2.0 변경 (D50):
- failure_category 5enum 강제: selector_broken / scenario_error / expected_mismatch /
                              real_defect / fictional_positive
- V6 정적 분석 결과 우선 (이미 마킹된 TC는 LLM 호출 skip)
- LLM 응답이 enum 위반 시 INFERRED 마킹

v2.1 변경 (D63):
- exec_mode 필드 전달: D39_keyword_match vs D40_scenario
- D39 모드에서 real_defect 과다 판정 억제 (프롬프트 측 우선순위 재조정)
"""
from __future__ import annotations
from typing import Callable

# D50 — 허용 enum (5종)
_VALID_FAILURE_CATEGORIES = frozenset({
    "selector_broken",
    "scenario_error",
    "expected_mismatch",
    "real_defect",
    "fictional_positive",
})

# V6 → D50 매핑 (doc/03-tc-schema.md §6.2)
_V6_TO_D50: dict[str, str] = {
    "selector_unstable": "selector_broken",
    "oracle_mismatch":   "expected_mismatch",
    "app_defect":        "real_defect",
    # "blocked"은 result=blocked로 별도 처리, failure_category 부여 안 함
}


def _reclassify_real_defect_by_log(tc: dict) -> tuple[str, str] | None:
    """[D70] real_defect로 분류되려는 TC의 execution_log를 검사해 오분류 교정.

    Stage 5 실행 시 중간 단계(navigate/login_state/confirm/action 등 assert 제외)에
    명시적 실패가 있으면, 이는 제품 결함이 아니라 자동화 시나리오·셀렉터 한계다.
    V6 정적 분석은 셀렉터 점수만 보고 execution_log를 무시하므로 여기서 보정한다.

    예: TC-003-001(confirm fail)·TC-026-001(register 폼 도달 실패) 등이
        real_defect로 새어 결함 카탈로그를 오염시키는 것을 차단.

    Returns:
        (category, source) 교정값, 또는 None(앞 단계 모두 ok → real_defect 유지).
    """
    log = tc.get("execution_log", [])
    if not log:
        return None
    for s in log:
        if s.get("action") == "assert":
            continue
        if s.get("status") in ("fail", "blocked"):
            act = s.get("action", "")
            if act in ("navigate", "login_state"):
                return ("selector_broken", "d70_log_access_fail")
            return ("scenario_error", "d70_log_scenario_fail")
    return None


def enhance(
    tcs: list[dict],
    llm_client,
    progress_cb: Callable[[str], None] | None = None,
) -> list[dict]:
    """result=fail인 TC에 failure_reason 4축 + failure_category 5enum (D50)을 채운다.

    V6 정적 분석이 이미 분류한 TC는 그 결과를 D50 enum으로 변환만 하고 LLM 호출 skip.
    """
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    failed = [tc for tc in tcs if tc.get("result") == "fail"]
    _cb(f"Stage 6: 실패 TC {len(failed)}개 원인 분석")

    # 1) V6 사전 마킹 처리 — LLM 호출 skip (토큰 절약, doc/03-tc-schema.md §6.1)
    needs_llm: list[dict] = []
    v6_resolved = 0
    inferred_guarded = 0
    d70_guarded = 0
    for tc in failed:
        v6_cat = tc.get("failure_category", "")  # V6가 stage5 직후 채웠을 수 있음
        if v6_cat in _V6_TO_D50:
            mapped = _V6_TO_D50[v6_cat]
            if mapped == "real_defect":
                # [D68] INFERRED 가드: 가공된 명세를 검증하는 TC가 FAIL이면
                # real_defect가 아니라 fictional_positive (판정 우선순위 1번).
                if str(tc.get("source_quote", "")).startswith("INFERRED"):
                    tc["failure_category"] = "fictional_positive"
                    tc["failure_category_source"] = "v6_static_inferred_guard"
                    inferred_guarded += 1
                else:
                    # [D70] execution_log 게이트: 중간 단계 실패면 real_defect 아님
                    reclass = _reclassify_real_defect_by_log(tc)
                    if reclass:
                        tc["failure_category"], tc["failure_category_source"] = reclass
                        d70_guarded += 1
                    else:
                        tc["failure_category"] = "real_defect"
                        tc["failure_category_source"] = "v6_static"
            else:
                tc["failure_category"] = mapped
                tc["failure_category_source"] = "v6_static"
            v6_resolved += 1
        else:
            needs_llm.append(tc)

    if v6_resolved:
        _cb(f"  V6 사전 마킹: {v6_resolved}건 (LLM 호출 skip)")
    if inferred_guarded:
        _cb(f"  INFERRED 가드: {inferred_guarded}건 real_defect→fictional_positive 보정")
    if d70_guarded:
        _cb(f"  execution_log 게이트: {d70_guarded}건 real_defect→scenario/selector 보정")

    # 2) 나머지 — LLM FAILURE_ANALYSIS 호출
    for i, tc in enumerate(needs_llm, 1):
        _cb(f"  분석 중 ({i}/{len(needs_llm)}): {tc['tc_id']}")
        exec_mode = tc.get("exec_mode", "D39_keyword_match")

        # Phase A: execution_log가 있으면 구조화된 로그를 actual_output으로 사용
        exec_log = tc.get("execution_log")
        if exec_log:
            import json as _json
            actual_output = "[execution_log]\n" + _json.dumps(
                exec_log[-5:], ensure_ascii=False
            )[:600]
        else:
            actual_output = tc.get("actual", "")[:500]

        result = llm_client.call("FAILURE_ANALYSIS", {
            "tc_id": tc["tc_id"],
            "exec_mode": exec_mode,
            "scenario": tc.get("scenario", "")[:200],
            "precondition": tc.get("precondition", "")[:300],
            "expected_output": tc.get("expected", "")[:300],
            "actual_output": actual_output,
            "source_quote": tc.get("source_quote", "")[:200],
        })

        # failure_reason 4축 보존
        parts = [
            f"[실제출력] {result.get('actual_output_summary', '')}",
            f"[차이] {result.get('difference', '')}",
            f"[원인후보] {', '.join(result.get('root_cause_candidates', []))}",
            f"[재시도] {result.get('retry_history', '없음')}",
        ]
        # category_evidence가 있으면 추가 (D50 추적성)
        if evidence := result.get("category_evidence", "").strip():
            parts.append(f"[분류근거] {evidence}")
        tc["failure_reason"] = "\n".join(parts)
        tc["exec_confidence"] = result.get("exec_confidence", tc.get("exec_confidence", 0.0))

        # D50 enum 검증
        llm_cat = (result.get("failure_category", "") or "").strip()
        if llm_cat in _VALID_FAILURE_CATEGORIES:
            # [D70] LLM이 real_defect로 판정해도 execution_log 중간 실패가 있으면 교정
            reclass = (
                _reclassify_real_defect_by_log(tc)
                if llm_cat == "real_defect" else None
            )
            if reclass:
                tc["failure_category"], tc["failure_category_source"] = reclass
            else:
                tc["failure_category"] = llm_cat
                tc["failure_category_source"] = "llm_failure_analysis"
        else:
            # LLM이 enum 위반 또는 누락 — INFERRED 마킹
            tc["failure_category"] = "fictional_positive" if (
                str(tc.get("source_quote", "")).startswith("INFERRED")
            ) else ""
            tc["failure_category_source"] = (
                "inferred_fallback" if tc["failure_category"] else "missing"
            )

    _cb("Stage 6 완료")
    return tcs

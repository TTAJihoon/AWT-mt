"""LLM 기반 test_data 생성 (D67, 작업 1).

휴리스틱(value_synth)이 못 맞추는 *명세-의존* 값(형식·접두사·범위·docstring 규칙)을
LLM이 명세를 읽고 채운다. 결과는 tc["test_data"]에 주입되어 실행기가 우선 사용한다.

Stage 2(코어 TC 설계 프롬프트)를 건드리지 않고, 비웹 대상에 대해서만 선택적으로
호출하는 보강 단계. LLM 호출 1건/leaf(그 leaf의 TC들을 한 번에).
"""
from __future__ import annotations

from typing import Any


def _tcs_block(tcs: list[dict]) -> str:
    lines = []
    for tc in tcs:
        lines.append(
            f'- tc_id={tc["tc_id"]} | technique={tc.get("design_technique","")}'
            f' | negative_category={tc.get("negative_category","")}'
            f' | scenario={tc.get("scenario","")}'
        )
    return "\n".join(lines)


def generate(llm: Any, target_kind: str, symbol_spec: str,
             tcs: list[dict]) -> dict[str, dict]:
    """leaf 1개의 명세 + 그 TC들 → {tc_id: test_data}. 실패 시 빈 dict."""
    if not tcs:
        return {}
    try:
        result = llm.call("TC_TESTDATA", {
            "target_kind": target_kind,
            "symbol_spec": symbol_spec,
            "tcs_block": _tcs_block(tcs),
        }, use_cache=True)
    except Exception:
        return {}
    out = result.get("test_data_by_tc") or {}
    return out if isinstance(out, dict) else {}


def enrich(llm: Any, target_kind: str, symbol_spec: str,
           tcs: list[dict]) -> list[dict]:
    """tcs에 test_data를 in-place 주입 후 반환."""
    mapping = generate(llm, target_kind, symbol_spec, tcs)
    for tc in tcs:
        td = mapping.get(tc.get("tc_id"))
        if isinstance(td, dict):
            tc["test_data"] = td
    return tcs

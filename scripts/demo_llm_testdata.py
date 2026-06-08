"""LLM test_data 라이브 데모 (작업 1-B).

휴리스틱(value_synth)이 못 맞추는 *명세-의존* 케이스를 LLM이 명세(docstring 규칙)를
읽고 해결하는 것을 before/after로 보인다.

대상 함수 apply_discount(code) — code는 'SAVE'로 시작해야 함(docstring에만 명시).
  · 휴리스틱: code="test" → 규칙 위반 → happy FAIL
  · LLM:     docstring 규칙 → code="SAVE10" → happy PASS

실행: OPENAI_API_KEY 환경변수 필요.
  PYTHONPATH=. PYTHONIOENCODING=utf-8 python scripts/demo_llm_testdata.py
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import copy
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from app.adapters import get_adapter, llm_test_data

_LIB = '''
def apply_discount(code: str) -> int:
    """할인 코드를 적용한다. code는 반드시 'SAVE'로 시작해야 하며,
    아니면 ValueError를 발생시킨다. 성공 시 할인율(%)을 반환."""
    if not code.startswith("SAVE"):
        raise ValueError("invalid coupon code")
    return 10
'''


def _tcs():
    return [
        {"tc_id": "TC-DISC-001", "소분류": "apply_discount", "design_technique": "happy_path",
         "negative_category": "", "scenario": "유효한 할인 코드 적용", "expected": "할인율 반환",
         "review_status": "approved"},
        {"tc_id": "TC-DISC-002", "소분류": "apply_discount", "design_technique": "negative_basic",
         "negative_category": "validation_failure", "scenario": "규칙 위반 코드 → 오류",
         "expected": "ValueError", "review_status": "approved"},
    ]


def _run(adapter, tcs, cfg, tmp, label):
    adapter.executor.execute(tcs=tcs, config=cfg, run_dir=tmp, progress_cb=lambda m: None,
                             is_paused=lambda: False, is_stopped=lambda: False)
    print(f"\n--- {label} ---")
    for tc in tcs:
        print(f"  [{tc['result'].upper():5}] {tc['tc_id']} :: {tc['actual']}"
              f"  (test_data={tc.get('test_data', '없음(휴리스틱)')})")


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        lib = tmp / "shop.py"; lib.write_text(_LIB, encoding="utf-8")
        cfg = SimpleNamespace(target_config={"lang": "python", "module_path": str(lib)})
        adapter = get_adapter("api_code")

        spec = adapter.probe.scan(config=cfg, llm=None, run_dir=tmp,
                                  progress_cb=lambda m: None, should_stop=lambda: False)
        leaf = next(f for f in spec["features"] if f["category_leaf"] == "apply_discount")
        print("대상 명세(implicit_spec):\n ", leaf["implicit_spec"].replace("\n", "\n  "))

        # 1) 휴리스틱만
        _run(adapter, _tcs(), cfg, tmp, "휴리스틱(value_synth)만 — happy 실패 예상")

        # 2) LLM test_data 보강
        if not key:
            print("\n[LLM 단계 생략] OPENAI_API_KEY 환경변수가 없습니다.")
            return
        from app.api.llm_client import LLMClient
        llm = LLMClient(api_key=key, run_id="demo-llm", model_override="gpt-4o-mini")
        tcs_b = _tcs()
        print("\n[LLM 호출] gpt-4o-mini 로 명세 기반 test_data 생성 중…")
        try:
            llm_test_data.enrich(llm, "api_code", leaf["implicit_spec"], tcs_b)
        except Exception as e:
            print(f"  LLM 호출 실패(네트워크/쿼터 등): {e}")
            return
        _run(adapter, tcs_b, cfg, tmp, "LLM test_data 보강 — happy 통과 예상")


if __name__ == "__main__":
    main()

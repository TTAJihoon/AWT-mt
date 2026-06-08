"""'API 없이 LLM 직접 사용' 데모 (작업 1-B, 외부 API 키 불필요).

외부 LLM API(OpenAI 등) 대신, **에이전트(Claude)가 명세를 직접 읽고 생성한 test_data**를
AgentLLM이 반환한다. 운영에선 이 자리를 LLMClient(OpenAI/Anthropic/Gemini)가 대체.

대상 apply_discount(code): docstring에만 "code는 'SAVE'로 시작" 규칙이 있다.
  · 휴리스틱(value_synth): code="test" → 규칙 위반 → happy FAIL
  · LLM 직접(에이전트): 명세를 읽고 code="SAVE10" → happy PASS

실행: PYTHONIOENCODING=utf-8 python scripts/demo_llm_direct.py
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo 루트(app)

from app.adapters import get_adapter, llm_test_data

_LIB = '''
def apply_discount(code: str) -> int:
    """할인 코드를 적용한다. code는 반드시 'SAVE'로 시작해야 하며,
    아니면 ValueError를 발생시킨다. 성공 시 할인율(%)을 반환."""
    if not code.startswith("SAVE"):
        raise ValueError("invalid coupon code")
    return 10
'''


class AgentLLM:
    """외부 API 없이 — 에이전트(Claude)가 명세를 읽고 생성한 test_data를 반환.

    아래 값은 apply_discount의 docstring 규칙("'SAVE'로 시작")을 읽고 만든 것:
      · happy_path     → 규칙을 만족하는 "SAVE10"
      · validation_failure → 규칙을 위반하는 "NOPE99" (ValueError 유발)
    """
    def call(self, contract_id, inputs, use_cache=True):
        assert contract_id == "TC_TESTDATA"
        return {"test_data_by_tc": {
            "TC-DISC-001": {"kwargs": {"code": "SAVE10"}, "expect_exception": False},
            "TC-DISC-002": {"kwargs": {"code": "NOPE99"}, "expect_exception": True},
        }}


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
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "shop.py").write_text(_LIB, encoding="utf-8")
        cfg = SimpleNamespace(target_config={"lang": "python", "module_path": str(tmp / "shop.py")})
        adapter = get_adapter("api_code")
        leaf = next(f for f in adapter.probe.scan(
            config=cfg, llm=None, run_dir=tmp, progress_cb=lambda m: None,
            should_stop=lambda: False)["features"] if f["category_leaf"] == "apply_discount")
        print("명세(implicit_spec):\n ", leaf["implicit_spec"].replace("\n", "\n  "))

        _run(adapter, _tcs(), cfg, tmp, "① 휴리스틱만 — happy 실패 예상")

        tcs_b = llm_test_data.enrich(AgentLLM(), "api_code", leaf["implicit_spec"], _tcs())
        _run(adapter, tcs_b, cfg, tmp, "② LLM 직접(에이전트 생성 test_data) — happy 통과 예상")


if __name__ == "__main__":
    main()

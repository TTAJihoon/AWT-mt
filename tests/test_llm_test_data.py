"""llm_test_data (작업1) — enrich가 tc['test_data']를 주입하는지 (가짜 LLM)."""
from __future__ import annotations

from app.adapters import llm_test_data


class _FakeLLM:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def call(self, contract_id, inputs, use_cache=True):
        self.calls.append((contract_id, inputs))
        return self._payload


def test_enrich_injects_test_data():
    llm = _FakeLLM({"test_data_by_tc": {
        "TC-1": {"kwargs": {"code": "SAVE10"}, "expect_exception": False},
        "TC-2": {"kwargs": {"code": "BAD"}, "expect_exception": True},
    }})
    tcs = [{"tc_id": "TC-1", "design_technique": "happy_path", "scenario": "정상"},
           {"tc_id": "TC-2", "design_technique": "negative_basic", "scenario": "위반"}]
    out = llm_test_data.enrich(llm, "api_code", "apply_discount(code: str)", tcs)
    assert out[0]["test_data"] == {"kwargs": {"code": "SAVE10"}, "expect_exception": False}
    assert out[1]["test_data"]["kwargs"]["code"] == "BAD"
    assert llm.calls[0][0] == "TC_TESTDATA"
    assert "TC-1" in llm.calls[0][1]["tcs_block"]


def test_generate_handles_llm_error():
    class _Boom:
        def call(self, *a, **k):
            raise RuntimeError("network down")
    assert llm_test_data.generate(_Boom(), "api_code", "spec", [{"tc_id": "X"}]) == {}

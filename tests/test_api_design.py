"""비웹 API-aware TC 설계 (D59) — 컨트랙트 선택 + Mock API 설계 의미 검증."""
from __future__ import annotations

from app.api.mock_llm_client import MockLLMClient
from app.core import stage2_tc_design


def test_mock_api_design_semantics():
    block = "1. [API > items > POST /items]\n2. [API > items > GET /items]"
    out = MockLLMClient().call("TC_DESIGN_API", {"features_block": block})["tcs"]
    by_leaf: dict[int, list] = {}
    for tc in out:
        by_leaf.setdefault(tc["leaf_index"], []).append(tc)
    # POST(쓰기): happy + validation_failure 음성
    t1 = [t["design_technique"] for t in by_leaf[1]]
    assert "happy_path" in t1 and "negative_basic" in t1
    assert any(t["negative_category"] == "validation_failure" for t in by_leaf[1])
    assert any("400" in t["expected"] or "예외" in t["expected"] for t in by_leaf[1])
    # GET(읽기): happy만 (인증 없는 API에 가짜 음성 안 만듦)
    assert [t["design_technique"] for t in by_leaf[2]] == ["happy_path"]


class _FakeLLM:
    def __init__(self):
        self.contracts = []

    def call(self, contract_id, inputs, use_cache=True):
        self.contracts.append(contract_id)
        if contract_id in ("TC_DESIGN_API", "TC_DESIGN_GROUP"):
            return {"tcs": [{"leaf_index": 1, "scenario": "s", "precondition": "p",
                             "expected": "201", "design_technique": "happy_path",
                             "negative_category": None, "source_quote": "INFERRED: x",
                             "gen_confidence": 0.9}]}
        return {"flows": []}


def test_design_uses_api_contract_for_nonweb():
    leaves = [{"requirement_id": "F001", "category_major": "API", "category_mid": "items",
               "category_leaf": "POST /items", "source_url": "items"}]
    llm = _FakeLLM()
    stage2_tc_design.design(leaves, "manual", llm, max_leaves=0,
                            design_contract="TC_DESIGN_API")
    assert "TC_DESIGN_API" in llm.contracts
    assert "TC_DESIGN_GROUP" not in llm.contracts


def test_design_default_contract_is_group():
    leaves = [{"requirement_id": "F001", "category_major": "회원", "category_mid": "로그인",
               "category_leaf": "로그인", "source_url": "/login"}]
    llm = _FakeLLM()
    stage2_tc_design.design(leaves, "manual", llm, max_leaves=0)
    assert "TC_DESIGN_GROUP" in llm.contracts

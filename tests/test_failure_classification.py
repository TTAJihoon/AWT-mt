"""D50 failure_category 5enum 검증 — Stage 6 통합 테스트.

V6 정적 분석 + LLM 동적 분석 통합 흐름 검증:
1. V6가 사전 마킹한 TC는 LLM 호출 skip
2. V6 미마킹 TC만 LLM이 5enum으로 분류
3. LLM 응답이 enum 위반 시 fallback 처리
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core import stage6_enhance
from app.core.stage6_enhance import _V6_TO_D50, _VALID_FAILURE_CATEGORIES


# ──────────────────────────────────────────────────────────────────────────
# V6 → D50 매핑 안정성
# ──────────────────────────────────────────────────────────────────────────

class TestV6Mapping:

    def test_all_v6_mappings_are_valid_d50(self):
        """V6 → D50 매핑의 모든 D50 값이 유효한 5enum 안에 있어야 함."""
        for v6_cat, d50_cat in _V6_TO_D50.items():
            assert d50_cat in _VALID_FAILURE_CATEGORIES, (
                f"V6 {v6_cat} → D50 {d50_cat} 는 유효 enum이 아님"
            )

    def test_v6_blocked_not_in_mapping(self):
        """V6 'blocked'는 D50으로 매핑 안 됨 (result=blocked로 별도 처리)."""
        assert "blocked" not in _V6_TO_D50

    def test_d50_has_two_extra_categories(self):
        """D50은 V6에 없는 scenario_error, fictional_positive를 추가."""
        v6_mapped = set(_V6_TO_D50.values())
        d50_only = _VALID_FAILURE_CATEGORIES - v6_mapped
        assert "scenario_error" in d50_only
        assert "fictional_positive" in d50_only


# ──────────────────────────────────────────────────────────────────────────
# Stage 6 — V6 우선 처리
# ──────────────────────────────────────────────────────────────────────────

class TestV6Priority:

    def test_v6_marked_tcs_skip_llm(self):
        """V6가 분류한 TC는 LLM 호출 안 함."""
        llm = MagicMock()
        tcs = [
            {"tc_id": "TC-001-001", "result": "fail",
             "failure_category": "selector_unstable",  # V6 사전 마킹
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x"},
            {"tc_id": "TC-001-002", "result": "fail",
             "failure_category": "app_defect",  # V6 사전 마킹
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x"},
        ]
        stage6_enhance.enhance(tcs, llm)

        # LLM은 한 번도 호출 안 됨 (V6가 둘 다 처리)
        llm.call.assert_not_called()

        # V6 → D50 매핑 확인
        assert tcs[0]["failure_category"] == "selector_broken"
        assert tcs[0]["failure_category_source"] == "v6_static"
        assert tcs[1]["failure_category"] == "real_defect"
        assert tcs[1]["failure_category_source"] == "v6_static"

    def test_unmarked_tcs_call_llm(self):
        """V6 미마킹 TC는 LLM 호출."""
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "summary",
            "difference": "diff",
            "root_cause_candidates": ["x"],
            "failure_category": "real_defect",
            "category_evidence": "evidence",
            "retry_history": "none",
            "exec_confidence": 0.7,
        }
        tcs = [
            {"tc_id": "TC-001-001", "result": "fail",
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x",
             "source_quote": "MANUAL: x"},
        ]
        stage6_enhance.enhance(tcs, llm)
        llm.call.assert_called_once()
        # 호출 인자에 source_quote가 포함되어야 함 (D50 prompt)
        call_args = llm.call.call_args
        assert "source_quote" in call_args[0][1]
        # 결과
        assert tcs[0]["failure_category"] == "real_defect"
        assert tcs[0]["failure_category_source"] == "llm_failure_analysis"


# ──────────────────────────────────────────────────────────────────────────
# LLM 응답 검증 — enum 위반 처리
# ──────────────────────────────────────────────────────────────────────────

class TestLLMEnumValidation:

    def _base_tc(self, source_quote="MANUAL: x"):
        return {
            "tc_id": "TC-001-001", "result": "fail",
            "scenario": "x", "precondition": "x",
            "expected": "x", "actual": "x",
            "source_quote": source_quote,
        }

    def test_invalid_enum_with_inferred_source_falls_back_to_fictional(self):
        """LLM이 잘못된 enum 반환 + source_quote=INFERRED → fictional_positive."""
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "x", "difference": "x",
            "root_cause_candidates": [],
            "failure_category": "wrong_value",  # 잘못된 enum
            "retry_history": "none", "exec_confidence": 0.5,
        }
        tcs = [self._base_tc(source_quote="INFERRED: guessed")]
        stage6_enhance.enhance(tcs, llm)
        assert tcs[0]["failure_category"] == "fictional_positive"
        assert tcs[0]["failure_category_source"] == "inferred_fallback"

    def test_invalid_enum_with_manual_source_leaves_empty(self):
        """LLM이 잘못된 enum + source_quote=MANUAL → missing 처리."""
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "x", "difference": "x",
            "root_cause_candidates": [],
            "failure_category": "completely_invalid",
            "retry_history": "none", "exec_confidence": 0.5,
        }
        tcs = [self._base_tc(source_quote="MANUAL: x")]
        stage6_enhance.enhance(tcs, llm)
        assert tcs[0]["failure_category"] == ""
        assert tcs[0]["failure_category_source"] == "missing"

    def test_missing_enum_field_also_handled(self):
        """LLM이 failure_category 자체를 빠뜨려도 fallback."""
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "x", "difference": "x",
            "root_cause_candidates": [],
            # failure_category 키 없음
            "retry_history": "none", "exec_confidence": 0.5,
        }
        tcs = [self._base_tc(source_quote="INFERRED: guess")]
        stage6_enhance.enhance(tcs, llm)
        assert tcs[0]["failure_category"] == "fictional_positive"

    @pytest.mark.parametrize("enum_val", [
        "selector_broken", "scenario_error", "expected_mismatch",
        "real_defect", "fictional_positive",
    ])
    def test_all_valid_enums_accepted(self, enum_val):
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "x", "difference": "x",
            "root_cause_candidates": [],
            "failure_category": enum_val,
            "retry_history": "none", "exec_confidence": 0.5,
        }
        tcs = [self._base_tc()]
        stage6_enhance.enhance(tcs, llm)
        assert tcs[0]["failure_category"] == enum_val
        assert tcs[0]["failure_category_source"] == "llm_failure_analysis"


# ──────────────────────────────────────────────────────────────────────────
# 통합 시나리오 — V6와 LLM 혼합
# ──────────────────────────────────────────────────────────────────────────

class TestMixedScenario:

    def test_mixed_v6_and_llm_processing(self):
        """5개 FAIL 중 2개는 V6 처리, 3개는 LLM 처리."""
        llm = MagicMock()
        llm.call.return_value = {
            "actual_output_summary": "x", "difference": "x",
            "root_cause_candidates": [],
            "failure_category": "scenario_error",
            "retry_history": "none", "exec_confidence": 0.5,
        }
        tcs = [
            {"tc_id": "T1", "result": "fail", "failure_category": "selector_unstable",
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x",
             "source_quote": "MANUAL: x"},
            {"tc_id": "T2", "result": "fail", "failure_category": "oracle_mismatch",
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x",
             "source_quote": "MANUAL: x"},
            {"tc_id": "T3", "result": "fail",
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x",
             "source_quote": "MANUAL: x"},
            {"tc_id": "T4", "result": "fail",
             "scenario": "x", "precondition": "x", "expected": "x", "actual": "x",
             "source_quote": "MANUAL: x"},
            {"tc_id": "T5", "result": "pass"},  # 실패 아님 — 처리 안 됨
        ]
        stage6_enhance.enhance(tcs, llm)
        assert llm.call.call_count == 2  # T3, T4만 호출 (T5는 pass)
        assert tcs[0]["failure_category_source"] == "v6_static"
        assert tcs[1]["failure_category_source"] == "v6_static"
        assert tcs[2]["failure_category_source"] == "llm_failure_analysis"
        assert tcs[3]["failure_category_source"] == "llm_failure_analysis"
        assert tcs[4].get("failure_category_source", "") == ""  # 미처리

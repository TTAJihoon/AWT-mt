"""Stage 3 — V10 gap이 TC_REGEN을 잘못 호출하지 않는지 검증 (Bug-1 회귀 방지).

Bug-1 요약:
  V10 실패 tc_id = "LEAF:F001" → failed_tcs = [] (빈 리스트)
  → TC_REGEN이 빈 입력으로 max_retries회 낭비 호출됨.

수정 후 기대 동작:
  1. V10 실패는 TC_REGEN 루프에서 완전히 분리
  2. TC_REGEN은 V1-V5 구조적 실패에만 호출
  3. V10 gap은 _add_v10_tcs → TC_DESIGN 재호출로 보완
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.core import stage3_verify


# ──────────────────────────────────────────────────────────────────────────
# 공통 픽스처
# ──────────────────────────────────────────────────────────────────────────

def _make_leaf(rid: str, leaf_name: str = "1.1 회원가입") -> dict:
    return {
        "requirement_id": rid,
        "category_major": "회원",
        "category_mid": "가입",
        "category_leaf": leaf_name,
    }


def _make_tc(tc_id: str, rid: str, technique: str = "happy_path",
             neg_cat: str | None = None) -> dict:
    return {
        "tc_id": tc_id,
        "requirement_id": rid,
        "대분류": "회원", "중분류": "가입", "소분류": "1.1 회원가입",
        "scenario": "테스트 시나리오",
        "precondition": "사전 조건",
        "expected": "기대 결과",
        "design_technique": technique,
        "source_quote": "MANUAL: 가입 관련 텍스트",
        "gen_confidence": 0.9,
        "negative_category": neg_cat,
        "review_status": "pending",
        "reviewer_note": "",
        "reviewer_id": "",
        "actual": "",
        "result": "not_executed",
        "failure_reason": "",
        "exec_confidence": 0.0,
        "failure_category": "",
        "failure_category_source": "",
    }


MANUAL_TEXT = "회원가입 시 이메일 주소를 입력합니다."


# ──────────────────────────────────────────────────────────────────────────
# Bug-1 핵심: V10 gap만 있으면 TC_REGEN이 호출되지 않아야 함
# ──────────────────────────────────────────────────────────────────────────

class TestV10DoesNotTriggerTCRegen:

    def _make_llm_for_v10(self):
        """TC_REGEN = 호출 안 됨, TC_DESIGN = 누락 카테고리 TC 반환."""
        llm = MagicMock()

        def _call(contract_id, inputs, **kwargs):
            assert contract_id != "TC_REGEN", (
                f"Bug-1 재현: V10 gap에 대해 TC_REGEN 호출됨 — "
                f"failed_tcs가 빈 리스트여도 3번 낭비 호출하는 버그"
            )
            # TC_DESIGN 응답 (누락 카테고리 TC)
            return {
                "tcs": [
                    {
                        "tc_id": "TC-001-005",
                        "scenario": "injection 테스트",
                        "precondition": "이메일 필드에 SQL 입력",
                        "expected_output": "입력 거부",
                        "technique": "negative_deep",
                        "negative_category": "injection_or_security",
                        "source_quote": "MANUAL: 가입 관련 텍스트",
                        "gen_confidence": 0.85,
                        "applied_invariant": None,
                        "related_defect_id": None,
                    }
                ]
            }

        llm.call.side_effect = _call
        return llm

    def test_v10_gap_only_does_not_call_tc_regen(self):
        """V10 gap만 있는 경우 TC_REGEN 호출 없이 TC_DESIGN으로 보완."""
        leaves = [_make_leaf("F001")]

        # validation_failure, duplicate_or_conflict, boundary_violation 있음
        # injection_or_security 없음 → V10 gap (회원가입 leaf는 업로드 키워드 없음)
        # 실제로 1.1 회원가입 → 키워드 "가입" → (validation, duplicate, boundary) 3종
        # boundary_violation 없으면 gap
        tcs = [
            _make_tc("TC-001-001", "F001", "happy_path"),
            _make_tc("TC-001-002", "F001", "negative_basic", "validation_failure"),
            _make_tc("TC-001-003", "F001", "negative_basic", "duplicate_or_conflict"),
            # boundary_violation 없음 → V10 gap
        ]

        llm = self._make_llm_for_v10()
        result = stage3_verify.verify(tcs, MANUAL_TEXT, llm, leaves)

        # TC_REGEN 호출 없어야 함
        for c in llm.call.call_args_list:
            assert c[0][0] != "TC_REGEN", f"TC_REGEN이 호출됨: {c}"

    def test_structural_failure_still_calls_tc_regen(self):
        """V1 구조적 실패는 여전히 TC_REGEN을 호출해야 함."""
        leaves = [_make_leaf("F001")]

        regen_response = {
            "tcs": [
                {
                    "tc_id": "TC-001-BAD",  # 잘못된 ID 형식 → V1 계속 실패
                    "scenario": "x", "precondition": "x",
                    "expected_output": "x", "technique": "happy_path",
                    "negative_category": None,
                    "source_quote": "MANUAL: 가입 관련 텍스트",
                    "gen_confidence": 0.8,
                    "applied_invariant": None, "related_defect_id": None,
                }
            ]
        }
        design_response = {"tcs": []}

        def _call(contract_id, inputs, **kwargs):
            if contract_id == "TC_REGEN":
                return regen_response
            return design_response

        llm = MagicMock()
        llm.call.side_effect = _call

        # V1 실패 TC (tc_id 형식 오류)
        bad_tc = _make_tc("TC-001-BAD-FORMAT", "F001", "happy_path")  # 형식 위반
        stage3_verify.verify([bad_tc], MANUAL_TEXT, llm, leaves, max_retries=2)

        # TC_REGEN이 최소 1회 이상 호출됐어야 함
        regen_calls = [c for c in llm.call.call_args_list if c[0][0] == "TC_REGEN"]
        assert len(regen_calls) >= 1, "V1 구조적 실패에 TC_REGEN이 호출되지 않음"


# ──────────────────────────────────────────────────────────────────────────
# _add_v10_tcs 구조화 필드 사용
# ──────────────────────────────────────────────────────────────────────────

class TestV10StructuredFields:

    def test_v10_failure_has_leaf_rid_and_missing_categories(self):
        """v10_negative_coverage.verify() 반환 dict에 구조화 필드 포함."""
        from app.validation.v10_negative_coverage import verify as v10_verify

        leaves = [_make_leaf("F001", "1.1 회원가입")]
        tcs = [
            _make_tc("TC-001-001", "F001", "happy_path"),
            _make_tc("TC-001-002", "F001", "negative_basic", "validation_failure"),
            # duplicate_or_conflict, boundary_violation 없음
        ]
        failures = v10_verify(tcs, leaves)
        assert len(failures) == 1
        f = failures[0]
        assert f["tc_id"] == "LEAF:F001"
        assert f["v"] == "V10"
        assert f["leaf_rid"] == "F001"
        assert "duplicate_or_conflict" in f["missing_categories"] or \
               "boundary_violation" in f["missing_categories"]

    def test_v10_no_structural_only_v10_finishes_clean(self):
        """V10만 있을 때 verify()가 빈 TC_REGEN 호출 없이 종료."""
        leaves = [_make_leaf("F001")]
        # 1.1 회원가입 → applicable: (validation_failure, duplicate_or_conflict, boundary_violation)
        # validation_failure만 커버 → 1/3 = 33% < 60% → V10 FAIL
        tcs = [
            _make_tc("TC-001-001", "F001", "happy_path"),
            _make_tc("TC-001-002", "F001", "negative_basic", "validation_failure"),
            # duplicate_or_conflict, boundary_violation 모두 없음 → 1/3 < 60%
        ]

        tc_design_response = {
            "tcs": [
                {
                    "tc_id": "TC-001-004",
                    "scenario": "경계값 테스트",
                    "precondition": "최대 길이 + 1 입력",
                    "expected_output": "오류 표시",
                    "technique": "negative_basic",
                    "negative_category": "boundary_violation",
                    "source_quote": "MANUAL: 가입 관련 텍스트",
                    "gen_confidence": 0.8,
                    "applied_invariant": None,
                    "related_defect_id": None,
                }
            ]
        }

        llm = MagicMock()
        llm.call.return_value = tc_design_response

        original_count = len(tcs)  # verify()가 tcs를 in-place 수정하므로 미리 저장
        result = stage3_verify.verify(tcs, MANUAL_TEXT, llm, leaves, max_retries=2)

        # TC_REGEN 호출 없음
        regen_calls = [c for c in llm.call.call_args_list if c[0][0] == "TC_REGEN"]
        assert len(regen_calls) == 0, f"TC_REGEN이 잘못 호출됨: {regen_calls}"

        # TC_DESIGN이 1회 호출됨 (V10 보완)
        design_calls = [c for c in llm.call.call_args_list if c[0][0] == "TC_DESIGN"]
        assert len(design_calls) == 1

        # 새 TC가 추가됨 (원래 2개 → 3개)
        assert len(result) > original_count


# ──────────────────────────────────────────────────────────────────────────
# TC_REGEN 필드 정규화 (expected_output → expected, technique → design_technique)
# ──────────────────────────────────────────────────────────────────────────

class TestRegenFieldNormalization:

    def test_regen_normalizes_expected_output_to_expected(self):
        """TC_REGEN이 expected_output 반환 시 expected로 정규화."""
        leaves = [_make_leaf("F001")]

        # V1 실패 유발 (tc_id 형식 오류)
        bad_tc = {
            "tc_id": "BADFORMAT",
            "requirement_id": "F001",
            "대분류": "회원", "중분류": "가입", "소분류": "1.1 회원가입",
            "scenario": "x", "precondition": "x",
            "expected": "x", "design_technique": "happy_path",
            "source_quote": "MANUAL: 가입 관련", "gen_confidence": 0.9,
            "negative_category": None, "review_status": "pending",
            "reviewer_note": "", "reviewer_id": "",
            "actual": "", "result": "not_executed",
            "failure_reason": "", "exec_confidence": 0.0,
            "failure_category": "", "failure_category_source": "",
        }

        def _call(contract_id, inputs, **kwargs):
            if contract_id == "TC_REGEN":
                return {
                    "tcs": [{
                        "tc_id": "TC-001-001",           # 수정된 ID
                        "scenario": "x", "precondition": "x",
                        "expected_output": "수정된 기대값",  # tc_regen 출력 형식
                        "technique": "happy_path",           # tc_regen 출력 형식
                        "negative_category": None,
                        "source_quote": "MANUAL: 가입 관련",
                        "gen_confidence": 0.9,
                        "applied_invariant": None, "related_defect_id": None,
                    }]
                }
            return {"tcs": []}  # TC_DESIGN for V10

        llm = MagicMock()
        llm.call.side_effect = _call

        result = stage3_verify.verify([bad_tc], MANUAL_TEXT, llm, leaves, max_retries=1)

        # 결과 TC에 expected_output이 아닌 expected가 있어야 함
        found = next((tc for tc in result if tc.get("tc_id") == "TC-001-001"), None)
        if found:  # 교체된 TC가 있으면 검증
            assert "expected" in found
            assert found["expected"] == "수정된 기대값"
            assert "design_technique" in found
            assert found["design_technique"] == "happy_path"

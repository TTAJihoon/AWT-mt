"""V10 negative_category 커버리지 강제 (D49) 단위 테스트.

설계: doc/03-tc-schema.md §7
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.validation.v10_negative_coverage import (
    NEGATIVE_CATEGORIES,
    applicable_categories_for_leaf,
    verify_leaf,
    verify,
    report,
)


# ──────────────────────────────────────────────────────────────────────────
# leaf 이름 → 적용 카테고리 매핑
# ──────────────────────────────────────────────────────────────────────────

class TestApplicableCategories:

    @pytest.mark.parametrize("leaf_name,expected_first", [
        ("1.1 회원가입", "validation_failure"),
        ("1.2 로그인", "validation_failure"),
        ("2.2 게시글 작성", "validation_failure"),
        ("2.4 게시글 수정", "validation_failure"),
        ("2.5 게시글 삭제", "validation_failure"),
        ("3.1 통합 검색", "permission_denied"),
        ("2.1 게시글 목록 조회", "permission_denied"),
        ("6.1 레벨 기반 권한", "permission_denied"),
        ("6.3 IP 차단", "permission_denied"),
        ("2.7 파일 첨부 및 다운로드", "validation_failure"),
        ("8.2 파일 업로드 제한", "validation_failure"),
        ("7.2 주문 및 결제", "validation_failure"),
    ])
    def test_matching_leaves_get_categories(self, leaf_name, expected_first):
        cats = applicable_categories_for_leaf(leaf_name)
        assert len(cats) >= 1
        assert cats[0] == expected_first

    @pytest.mark.parametrize("leaf_name", [
        "기타 알 수 없는 leaf",
        "5.1 기본 환경 설정",  # 키워드 미매칭
        "",
    ])
    def test_unmatched_returns_empty(self, leaf_name):
        cats = applicable_categories_for_leaf(leaf_name)
        assert cats == ()

    def test_file_upload_includes_security(self):
        """파일 업로드는 injection_or_security 포함."""
        cats = applicable_categories_for_leaf("파일 업로드")
        assert "injection_or_security" in cats

    def test_payment_includes_duplicate(self):
        """결제는 duplicate_or_conflict 포함 (중복 결제 방지)."""
        cats = applicable_categories_for_leaf("주문 및 결제")
        assert "duplicate_or_conflict" in cats

    def test_all_returned_categories_are_valid(self):
        """모든 매핑이 5enum 안에 있어야 함."""
        for leaf_name in ("가입", "조회", "권한", "업로드", "결제"):
            cats = applicable_categories_for_leaf(leaf_name)
            for c in cats:
                assert c in NEGATIVE_CATEGORIES


# ──────────────────────────────────────────────────────────────────────────
# leaf 단위 검증
# ──────────────────────────────────────────────────────────────────────────

def _tc(technique: str, negative_category: str | None = None) -> dict:
    return {
        "design_technique": technique,
        "negative_category": negative_category,
    }


class TestVerifyLeaf:

    def test_leaf_with_no_applicable_passes(self):
        """적용 카테고리 없는 leaf는 무조건 PASS (skip)."""
        leaf = {"requirement_id": "F999", "category_leaf": "5.1 기본 환경 설정"}
        result = verify_leaf(leaf, [])
        assert result.passed is True
        assert result.applicable == ()
        assert result.coverage_ratio == 1.0

    def test_full_coverage_passes(self):
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        # 회원가입: validation_failure, duplicate_or_conflict, boundary_violation 적용
        tcs = [
            _tc("negative_basic", "validation_failure"),
            _tc("negative_basic", "duplicate_or_conflict"),
            _tc("negative_basic", "boundary_violation"),
        ]
        result = verify_leaf(leaf, tcs)
        assert result.passed is True
        assert result.coverage_ratio == 1.0
        assert set(result.covered) == set(result.applicable)
        assert result.missing == ()

    def test_partial_coverage_at_threshold_passes(self):
        """3개 중 2개 (66.7%) ≥ 60% — PASS."""
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        tcs = [
            _tc("negative_basic", "validation_failure"),
            _tc("negative_basic", "duplicate_or_conflict"),
        ]
        result = verify_leaf(leaf, tcs, min_coverage=0.6)
        assert result.passed is True
        assert pytest.approx(result.coverage_ratio, abs=0.01) == 2/3

    def test_partial_coverage_below_threshold_fails(self):
        """3개 중 1개 (33%) < 60% — FAIL."""
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        tcs = [_tc("negative_basic", "validation_failure")]
        result = verify_leaf(leaf, tcs, min_coverage=0.6)
        assert result.passed is False
        assert len(result.missing) == 2

    def test_zero_negative_tcs_fails(self):
        """적용 카테고리는 있는데 음성 TC가 0개면 FAIL."""
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        tcs = [
            _tc("happy_path", None),
            _tc("boundary", None),
        ]
        result = verify_leaf(leaf, tcs)
        assert result.passed is False
        assert result.coverage_ratio == 0.0

    def test_negative_without_category_not_counted(self):
        """negative_*인데 category 미지정은 커버리지 카운트 안 됨."""
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        tcs = [
            _tc("negative_basic", None),
            _tc("negative_basic", ""),
        ]
        result = verify_leaf(leaf, tcs)
        assert result.passed is False

    def test_invalid_category_not_counted(self):
        """leaf 적용 카테고리 밖의 값은 카운트 안 됨."""
        leaf = {"requirement_id": "F001", "category_leaf": "1.1 회원가입"}
        # 회원가입에 permission_denied는 적용 카테고리 아님 (입력 폼 분류)
        tcs = [
            _tc("negative_basic", "permission_denied"),
            _tc("negative_basic", "permission_denied"),
        ]
        result = verify_leaf(leaf, tcs)
        assert result.passed is False  # validation/duplicate/boundary 모두 0


# ──────────────────────────────────────────────────────────────────────────
# 전체 verify() — Stage 3 호환 포맷
# ──────────────────────────────────────────────────────────────────────────

class TestVerify:

    def test_all_leaves_pass_returns_empty(self):
        leaves = [{"requirement_id": "F001", "category_leaf": "1.1 회원가입"}]
        tcs = [
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "validation_failure"},
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "duplicate_or_conflict"},
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "boundary_violation"},
        ]
        assert verify(tcs, leaves) == []

    def test_failure_format_is_stage3_compatible(self):
        leaves = [{"requirement_id": "F001", "category_leaf": "1.1 회원가입"}]
        tcs = [{"requirement_id": "F001", "design_technique": "happy_path"}]
        failures = verify(tcs, leaves)
        assert len(failures) == 1
        f = failures[0]
        assert f["v"] == "V10"
        assert f["tc_id"] == "LEAF:F001"
        assert "negative 카테고리" in f["reason"]

    def test_skipped_leaves_not_in_failures(self):
        """적용 카테고리 없는 leaf는 failures에 안 나타남."""
        leaves = [
            {"requirement_id": "F999", "category_leaf": "5.1 기본 환경 설정"},
            {"requirement_id": "F001", "category_leaf": "1.1 회원가입"},
        ]
        tcs = [
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "validation_failure"},
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "duplicate_or_conflict"},
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "boundary_violation"},
        ]
        failures = verify(tcs, leaves)
        assert failures == []  # F999는 skip, F001은 full coverage


# ──────────────────────────────────────────────────────────────────────────
# report() — 통계 요약
# ──────────────────────────────────────────────────────────────────────────

class TestReport:

    def test_report_includes_category_counts(self):
        leaves = [{"requirement_id": "F001", "category_leaf": "1.1 회원가입"}]
        tcs = [
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "validation_failure"},
            {"requirement_id": "F001", "design_technique": "negative_basic",
             "negative_category": "duplicate_or_conflict"},
        ]
        r = report(tcs, leaves)
        assert r["leaf_count"] == 1
        assert r["tcs_by_category"]["validation_failure"] == 1
        assert r["tcs_by_category"]["duplicate_or_conflict"] == 1
        assert r["tcs_by_category"]["permission_denied"] == 0

    def test_report_counts_skipped(self):
        leaves = [
            {"requirement_id": "F001", "category_leaf": "1.1 회원가입"},
            {"requirement_id": "F999", "category_leaf": "5.1 기본 환경 설정"},
        ]
        tcs = []
        r = report(tcs, leaves)
        assert r["leaves_skipped"] == 1
        assert r["leaves_failed"] == 1  # F001은 음성 0개

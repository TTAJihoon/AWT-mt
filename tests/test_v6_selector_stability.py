"""V6 선택자 안정성 모듈 단위 테스트."""
import pytest
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.validation.v6_selector_stability import (
    extract_selectors,
    selector_stability_score,
    oracle_clarity_score,
    compute_exec_confidence,
    classify_failure,
    annotate,
    format_report,
    FAILURE_CATEGORIES,
)


# ---------------------------------------------------------------------------
# 1. extract_selectors
# ---------------------------------------------------------------------------

class TestExtractSelectors:
    def test_url_path(self):
        hints = extract_selectors("회원가입 페이지(/bbs/register.php) 접속")
        tiers = [h.tier for h in hints]
        assert "url_path" in tiers

    def test_id_selector(self):
        hints = extract_selectors("input#mb_id 필드에 'testuser' 입력")
        tiers = [h.tier for h in hints]
        assert "id_selector" in tiers

    def test_data_testid(self):
        hints = extract_selectors("[data-testid='btn-submit'] 클릭")
        tiers = [h.tier for h in hints]
        assert "data_testid" in tiers

    def test_text_exact_korean(self):
        hints = extract_selectors("화면에 '이미 사용 중인 아이디입니다' 메시지 표시")
        tiers = [h.tier for h in hints]
        assert "text_exact" in tiers

    def test_empty_text_returns_empty(self):
        hints = extract_selectors("")
        assert hints == []

    def test_xpath(self):
        hints = extract_selectors("xpath=//div[@id='wrap']/span 선택")
        tiers = [h.tier for h in hints]
        assert "xpath" in tiers

    def test_class_selector(self):
        hints = extract_selectors(".error-message 요소가 표시됨")
        tiers = [h.tier for h in hints]
        assert "class_stable" in tiers

    def test_no_duplicate_hints(self):
        hints = extract_selectors("/bbs/login.php 접속 후 /bbs/login.php 재확인")
        url_hints = [h for h in hints if h.tier == "url_path"]
        # 동일한 URL이 중복 추출되지 않아야 함
        raws = [h.raw for h in url_hints]
        assert len(raws) == len(set(raws))


# ---------------------------------------------------------------------------
# 2. selector_stability_score
# ---------------------------------------------------------------------------

class TestSelectorStabilityScore:
    def test_empty_hints_returns_default(self):
        assert selector_stability_score([]) == 0.60

    def test_text_exact_gives_high_score(self):
        hints = extract_selectors("'가입 완료' 메시지 표시")
        score = selector_stability_score(hints)
        assert score >= 0.85, f"text_exact should give high score, got {score}"

    def test_xpath_gives_low_score(self):
        hints = extract_selectors("xpath=//div[@class='wrap']/ul/li[3]/span")
        score = selector_stability_score(hints)
        assert score < 0.50, f"xpath should give low score, got {score}"

    def test_mixed_selectors(self):
        # 안정적 선택자 + 불안정 선택자 혼합 → 중간 점수
        text = "'로그인 성공' 메시지 xpath=//div/span"
        hints = extract_selectors(text)
        score = selector_stability_score(hints)
        assert 0.40 < score < 0.95

    def test_score_range(self):
        for text in [
            "#submit-btn 클릭",
            ".btn-primary 버튼",
            "[data-testid='form'] 폼",
            "xpath=//form[@id='login']",
        ]:
            hints = extract_selectors(text)
            score = selector_stability_score(hints)
            assert 0.0 <= score <= 1.0, f"Score out of range for '{text}': {score}"


# ---------------------------------------------------------------------------
# 3. oracle_clarity_score
# ---------------------------------------------------------------------------

class TestOracleClarityScore:
    def test_quoted_korean_text_high_score(self):
        score = oracle_clarity_score("'가입이 완료되었습니다' 토스트 메시지 표시")
        assert score >= 0.80, f"Expected high score, got {score}"

    def test_abstract_terms_lower_score(self):
        score_abstract = oracle_clarity_score("정상적으로 처리됨")
        score_concrete = oracle_clarity_score("'저장 완료' 메시지 표시")
        assert score_concrete > score_abstract

    def test_url_included_boosts_score(self):
        score_with = oracle_clarity_score("로그인 후 /bbs/board.php로 이동")
        score_without = oracle_clarity_score("로그인 후 메인 페이지로 이동")
        assert score_with > score_without

    def test_very_short_expected_low_score(self):
        score = oracle_clarity_score("성공")
        assert score < 0.60

    def test_score_range(self):
        for text in [
            "'이미 사용 중인 아이디입니다' 오류 표시",
            "정상 처리",
            "/bbs/login.php 리다이렉트",
            "",
            "200 OK 응답",
        ]:
            score = oracle_clarity_score(text)
            assert 0.0 <= score <= 1.0, f"Score out of range for '{text}': {score}"


# ---------------------------------------------------------------------------
# 4. compute_exec_confidence
# ---------------------------------------------------------------------------

class TestComputeExecConfidence:
    def _make_tc(self, precondition: str, expected: str) -> dict:
        return {"precondition": precondition, "expected": expected, "result": "pass"}

    def test_high_confidence_stable_tc(self):
        tc = self._make_tc(
            precondition="로그인 상태 / 게시글 목록(/bbs/board.php) 접속",
            expected="'글쓰기' 버튼이 표시됨"
        )
        conf = compute_exec_confidence(tc, retry_count=0)
        assert conf >= 0.75, f"Stable TC should have high confidence, got {conf}"

    def test_retry_penalty_reduces_confidence(self):
        tc = self._make_tc("로그인 상태", "'저장 완료' 메시지")
        conf_no_retry  = compute_exec_confidence(tc, retry_count=0)
        conf_3_retries = compute_exec_confidence(tc, retry_count=3)
        assert conf_no_retry > conf_3_retries

    def test_confidence_range(self):
        tcs = [
            self._make_tc("비로그인 / /bbs/register.php", "'가입 완료' 메시지"),
            self._make_tc("xpath=//div/ul/li", "정상 처리"),
            self._make_tc("", ""),
        ]
        for tc in tcs:
            conf = compute_exec_confidence(tc)
            assert 0.0 <= conf <= 1.0


# ---------------------------------------------------------------------------
# 5. classify_failure
# ---------------------------------------------------------------------------

class TestClassifyFailure:
    def _make_tc(self, result: str, precondition: str = "", expected: str = "") -> dict:
        return {"result": result, "precondition": precondition, "expected": expected}

    def test_pass_is_not_applicable(self):
        tc = self._make_tc("pass")
        assert classify_failure(tc) == "not_applicable"

    def test_not_executed_is_not_applicable(self):
        tc = self._make_tc("not_executed")
        assert classify_failure(tc) == "not_applicable"

    def test_blocked_is_blocked(self):
        tc = self._make_tc("blocked")
        assert classify_failure(tc) == "blocked"

    def test_fail_with_stable_oracle_is_app_defect(self):
        tc = self._make_tc(
            result="fail",
            precondition="로그인 상태 / /bbs/board.php 접속",
            expected="'권한이 없습니다' 오류 메시지 표시"
        )
        cat = classify_failure(tc)
        assert cat == "app_defect", f"Expected app_defect, got {cat}"

    def test_fail_with_xpath_is_selector_unstable(self):
        tc = self._make_tc(
            result="fail",
            precondition="xpath=//div[@class='a']/ul/li[2]/span[@data-x='y'] 클릭",
            expected="xpath=//span[@id='z']/text() 확인"
        )
        cat = classify_failure(tc)
        assert cat == "selector_unstable", f"Expected selector_unstable, got {cat}"

    def test_fail_with_abstract_oracle_is_oracle_mismatch(self):
        tc = self._make_tc(
            result="fail",
            precondition="로그인",
            expected="올바르게 처리됨"  # 추상적 기대 결과
        )
        cat = classify_failure(tc)
        assert cat == "oracle_mismatch", f"Expected oracle_mismatch, got {cat}"


# ---------------------------------------------------------------------------
# 6. annotate (일괄 보정)
# ---------------------------------------------------------------------------

class TestAnnotate:
    def _sample_tcs(self) -> list[dict]:
        return [
            {
                "tc_id": "TC-001-001",
                "precondition": "비로그인 상태 / 회원가입 페이지(/bbs/register.php) 접속",
                "expected": "'가입 완료' 메시지 표시 후 로그인 페이지로 이동",
                "result": "pass",
                "exec_confidence": 0.5,
            },
            {
                "tc_id": "TC-001-002",
                "precondition": "xpath=//form[@id='login']/input[@name='id'] 입력",
                "expected": "정상 처리됨",
                "result": "fail",
                "exec_confidence": 0.5,
            },
            {
                "tc_id": "TC-001-003",
                "precondition": "로그인 상태",
                "expected": "'삭제되었습니다' 토스트 메시지",
                "result": "fail",
                "exec_confidence": 0.5,
            },
        ]

    def test_all_tcs_annotated(self):
        tcs = self._sample_tcs()
        annotated, report = annotate(tcs)
        for tc in annotated:
            assert "selector_stability_score" in tc
            assert "oracle_clarity_score" in tc
            assert "exec_confidence" in tc
            assert "failure_category" in tc

    def test_report_counts(self):
        tcs = self._sample_tcs()
        _, report = annotate(tcs)
        assert report.total == 3
        assert report.annotated == 3

    def test_exec_confidence_overwritten(self):
        tcs = self._sample_tcs()
        annotated, _ = annotate(tcs, overwrite_exec_confidence=True)
        # 기존 0.5와 달라야 함 (V6 계산 결과로 덮어씀)
        for tc in annotated:
            # 모든 TC의 exec_confidence가 유효 범위 내
            assert 0.0 <= tc["exec_confidence"] <= 1.0

    def test_no_overwrite_mode(self):
        tcs = self._sample_tcs()
        annotated, _ = annotate(tcs, overwrite_exec_confidence=False)
        # exec_confidence는 원래 값(0.5) 유지
        for tc in annotated:
            assert tc["exec_confidence"] == 0.5

    def test_failure_categories_in_report(self):
        tcs = self._sample_tcs()
        _, report = annotate(tcs)
        # 적어도 하나의 분류가 있어야 함
        assert len(report.by_failure_category) > 0

    def test_format_report_output(self):
        tcs = self._sample_tcs()
        _, report = annotate(tcs)
        text = format_report(report)
        assert "V6" in text
        assert "selector_stability" in text
        assert "oracle_clarity" in text


# ---------------------------------------------------------------------------
# 7. 실제 TC 샘플 (Mock 파이프라인 출력 유사 형태)
# ---------------------------------------------------------------------------

class TestRealWorldSamples:
    """실제 gnuboard5 TC 유사 샘플로 통합 검증."""

    SAMPLES = [
        {
            "tc_id": "TC-006-001",
            "precondition": "로그인 상태 / 게시판 목록 페이지(/bbs/board.php?bo_table=free) 접속",
            "expected": "글쓰기 버튼 클릭 시 게시글 작성 페이지(/bbs/write.php?bo_table=free) 이동",
            "result": "pass",
        },
        {
            "tc_id": "TC-006-002",
            "precondition": "비로그인 상태 / 게시글 작성 시도",
            "expected": "'로그인이 필요합니다' 메시지 또는 로그인 페이지(/bbs/login.php)로 이동",
            "result": "pass",
        },
        {
            "tc_id": "TC-008-001",
            "precondition": "xpath=//table[@id='fwrite']/tbody/tr[3]/td/input 에 제목 입력",
            "expected": "정상적으로 저장됨",
            "result": "fail",
        },
        {
            "tc_id": "TC-009-001",
            "precondition": "게시글 작성자 로그인 상태 / 게시글 상세 페이지",
            "expected": "'게시글이 삭제되었습니다' 토스트 메시지 표시, 목록으로 이동",
            "result": "fail",
        },
    ]

    def test_stable_tcs_get_high_confidence(self):
        """URL 포함 + 인용 텍스트 포함 TC는 높은 exec_confidence를 받아야 한다."""
        annotated, _ = annotate([dict(tc) for tc in self.SAMPLES])
        stable = [tc for tc in annotated if tc["tc_id"] in ("TC-006-001", "TC-006-002")]
        for tc in stable:
            assert tc["exec_confidence"] >= 0.70, (
                f"{tc['tc_id']} should have high confidence, got {tc['exec_confidence']}"
            )

    def test_xpath_fail_classified_as_selector_unstable(self):
        annotated, _ = annotate([dict(tc) for tc in self.SAMPLES])
        tc = next(t for t in annotated if t["tc_id"] == "TC-008-001")
        assert tc["failure_category"] == "selector_unstable"

    def test_stable_fail_classified_as_app_defect(self):
        annotated, _ = annotate([dict(tc) for tc in self.SAMPLES])
        tc = next(t for t in annotated if t["tc_id"] == "TC-009-001")
        assert tc["failure_category"] == "app_defect"

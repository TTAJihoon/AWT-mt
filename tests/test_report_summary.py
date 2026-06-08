"""보고서 요약 (D67, P5) — 자동화 등급/수동확인/실패 요약."""
from __future__ import annotations

from app.adapters.report_summary import automation_summary, build_report_md

_TCS = [
    {"tc_id": "TC-001-001", "소분류": "POST /users", "automation_grade": "A",
     "result": "pass", "expected": "201", "target_kind": "api_rest"},
    {"tc_id": "TC-001-002", "소분류": "POST /users", "automation_grade": "A",
     "result": "fail", "expected": "409", "actual": "HTTP 200"},
    {"tc_id": "TC-002-001", "소분류": "인증서 로그인", "automation_grade": "C",
     "result": "needs_manual_review", "manual_action_required": "인증서 비밀번호 수동 입력"},
    {"tc_id": "TC-003-001", "소분류": "보안키패드", "automation_grade": "D",
     "result": "not_executed", "manual_action_required": "물리 키패드 수동"},
]


def test_automation_summary_counts():
    s = automation_summary(_TCS)
    assert s["total"] == 4
    assert s["grades"]["A"] == 2 and s["grades"]["C"] == 1 and s["grades"]["D"] == 1
    assert s["fail_count"] == 1
    assert s["manual_count"] == 2          # C + D


def test_report_md_sections():
    md = build_report_md(_TCS, meta={"run_id": "abc123", "target_kind": "api_rest"})
    for section in ("## 1. 개요", "## 2. 자동화 가능성 요약",
                    "## 3. 수행 결과 요약", "## 4. 실패 TC 상세",
                    "## 5. 수동 확인 필요 항목", "## 6. 종합 의견"):
        assert section in md
    assert "api_rest" in md
    assert "TC-001-002" in md              # 실패 TC 표기
    assert "인증서 비밀번호 수동 입력" in md   # 수동 조치 표기

"""gui 어댑터 (D63, P4) — 순수 로직(등급/안정성/오라클/증적) + 의존성 부재 처리."""
from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from app.adapters import gui_adapter as ga


def test_stability_by_locator_priority():
    assert ga.gui_stability({"automation_id": "btnOk"}) == 0.90
    assert ga.gui_stability({"name": "확인", "control_type": "ButtonControl"}) == 0.75
    assert ga.gui_stability({"parent_path": "/win/panel"}) == 0.60
    assert ga.gui_stability({"rect": [1, 2, 3, 4]}) == 0.40
    assert ga.gui_stability({"ocr": True}) == 0.30
    assert ga.gui_stability({}) == 0.55


def test_grade_abcd():
    assert ga.gui_grade({"scenario": "보안키패드로 비밀번호 입력"})[0] == "D"
    assert ga.gui_grade({"scenario": "인증서 선택 후 로그인"})[0] == "C"
    assert ga.gui_grade({"scenario": "메시지 전송",
                         "verification_methods": ["로그 파일 확인"]})[0] == "A"
    assert ga.gui_grade({"scenario": "버튼 클릭 후 화면 메시지 확인"})[0] == "B"


def test_oracle_file_log_db(tmp_path):
    o = ga.GuiOracle()
    f = tmp_path / "out.pdf"
    f.write_text("data", encoding="utf-8")
    assert o.verify_file_exists(str(f))
    assert not o.verify_file_exists(str(tmp_path / "missing"))

    lg = tmp_path / "chat.log"
    lg.write_text("INFO start\nSEND_SUCCESS to=TEST001\n", encoding="utf-8")
    assert o.verify_log_contains(str(lg), "SEND_SUCCESS")
    assert not o.verify_log_contains(str(lg), "SEND_FAIL")

    db = tmp_path / "app.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE m(id INTEGER, body TEXT)")
    con.execute("INSERT INTO m VALUES (1,'hello')")
    con.commit(); con.close()
    assert o.verify_db_value(str(db), "SELECT body FROM m WHERE id=1", "hello")
    assert not o.verify_db_value(str(db), "SELECT body FROM m WHERE id=1", "bye")


def test_oracle_verify_priority(tmp_path):
    o = ga.GuiOracle()
    f = tmp_path / "report.xlsx"
    f.write_text("x", encoding="utf-8")
    v = o.verify("보고서 생성", {"files": [str(f)], "ui_text": "완료"}, [])
    assert v.status == "pass" and "파일" in v.actual   # 파일 > UI 우선


def test_negative_map():
    cats = ga.gui_negative_map({"category_leaf": "회원 등록", "category_mid": "권한"})
    assert "validation_failure" in cats
    assert "permission_denied" in cats and "duplicate_or_conflict" in cats


def test_evidence_collector(tmp_path):
    ev = ga.EvidenceCollector(tmp_path)
    p = ev.save_text("TC-001-001", "before.txt", "초기 상태")
    assert (tmp_path / "evidence" / "TC-001-001_before.txt").exists()


def test_executor_classifies_cd_without_deps(tmp_path):
    # D/C 등급은 의존성 없이도 분류·수동절차 산출(가이드 §9.3)
    tcs = [
        {"tc_id": "TC-001-001", "scenario": "보안키패드 입력", "review_status": "approved"},
        {"tc_id": "TC-002-001", "scenario": "인증서 선택", "review_status": "approved"},
    ]
    out = ga.GuiExecutor().execute(
        tcs=tcs, config=SimpleNamespace(target_config={}), run_dir=tmp_path,
        progress_cb=lambda m: None, is_paused=lambda: False, is_stopped=lambda: False)
    by = {t["tc_id"]: t for t in out}
    assert by["TC-001-001"]["automation_grade"] == "D"
    assert by["TC-001-001"]["result"] == "not_executed"
    assert by["TC-002-001"]["automation_grade"] == "C"
    assert by["TC-002-001"]["result"] == "needs_manual_review"


def test_ab_grade_requires_deps(tmp_path):
    # A/B 등급은 실제 UIA 필요 — 미설치 환경에선 명확한 안내 예외
    tcs = [{"tc_id": "TC-003-001", "scenario": "메시지 전송",
            "verification_methods": ["로그 파일 확인"], "review_status": "approved"}]
    with pytest.raises(RuntimeError, match="uiautomation"):
        ga.GuiExecutor().execute(
            tcs=tcs, config=SimpleNamespace(target_config={}), run_dir=tmp_path,
            progress_cb=lambda m: None, is_paused=lambda: False, is_stopped=lambda: False)


def test_gui_action_inference():
    assert ga._gui_action({}, "ButtonControl") == "invoke"
    assert ga._gui_action({}, "MenuItemControl") == "invoke"
    assert ga._gui_action({}, "EditControl") == "set_value"
    assert ga._gui_action({}, "ComboBoxControl") == "set_value"
    assert ga._gui_action({"scenario": "전송 버튼 클릭"}, "PaneControl") == "invoke"
    assert ga._gui_action({"scenario": "메시지 입력"}, "PaneControl") == "set_value"
    assert ga._gui_action({"scenario": "결과 확인"}, "TextControl") == "read"


def test_gui_input_value():
    assert ga._gui_input_value({"test_data": {"value": "hello"}}) == "hello"
    assert ga._gui_input_value({"test_data": {"kwargs": {"msg": "hi"}}}) == "hi"
    assert ga._gui_input_value({}) == "테스트입력"


def test_find_control():
    idx = {"btnSend": "B", "txtMsg": "E"}
    assert ga._find_control(idx, {"소분류": "btnSend"}) == "B"
    assert ga._find_control(idx, {"소분류": "Msg"}) == "E"
    assert ga._find_control(idx, {"소분류": "nope"}) is None


def test_probe_requires_deps(tmp_path):
    with pytest.raises(RuntimeError, match="uiautomation"):
        ga.GuiProbe().scan(config=SimpleNamespace(target_config={"exe_path": "x.exe"}),
                           llm=None, run_dir=tmp_path,
                           progress_cb=lambda m: None, should_stop=lambda: False)

"""특별 관리자 계정(DB 없이 로그인) 검증."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.auth import special_account as sa


def test_check_correct():
    assert sa.check("jh91082", "12sqec34!") is True


def test_check_wrong():
    assert sa.check("jh91082", "wrong") is False
    assert sa.check("other", "12sqec34!") is False
    assert sa.check("", "") is False


def test_token_and_user_helpers():
    assert sa.is_special_token(sa.SPECIAL_TOKEN)
    assert not sa.is_special_token("nope")
    assert sa.is_special_user("jh91082")
    assert not sa.is_special_user("bob")


def test_login_window_special_bypasses_db():
    """LoginWindow가 특별계정을 DB 없이 즉시 통과(토큰=SPECIAL)."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841

    from app.ui.login_window import LoginWindow
    w = LoginWindow()                      # DB 미가용이어도 생성 가능(지연 연결)
    captured = {}
    w.logged_in.connect(lambda t, u, k: captured.update(token=t, user=u))
    w._user_edit.setText("jh91082")
    w._pw_edit.setText("12sqec34!")
    w._do_login()                          # DB 워커 미사용, 즉시 emit
    assert captured.get("token") == sa.SPECIAL_TOKEN
    assert captured.get("user") == "jh91082"
    # 로그인 버튼은 DB 불가여도 활성 상태(특별계정 진입 보장)
    assert w._login_btn.isEnabled()

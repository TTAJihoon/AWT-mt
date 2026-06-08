"""Wizard 대상유형 분기 (P5b) — offscreen QApplication으로 런타임 검증."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def wiz(_app):
    from app.ui.wizard import RunWizard
    return RunWizard(api_key="test-key")


def _select_lang(wiz, data: str):
    for i in range(wiz._code_lang.count()):
        if wiz._code_lang.itemData(i) == data:
            wiz._code_lang.setCurrentIndex(i)
            return
    raise AssertionError(f"lang {data} 없음")


def test_default_is_web_and_stack_syncs(wiz):
    assert wiz._target_kind_combo.currentData() == "web"
    for i in range(4):
        wiz._target_kind_combo.setCurrentIndex(i)
        assert wiz._target_stack.currentIndex() == i


def test_target_config_rest(wiz):
    wiz._target_kind_combo.setCurrentIndex(1)  # api_rest
    wiz._rest_openapi.setText("/tmp/openapi.json")
    wiz._rest_base.setText("http://api.x")
    wiz._rest_token.setText("tok123")
    assert wiz._build_target_config() == {
        "openapi_path": "/tmp/openapi.json",
        "base_url": "http://api.x",
        "auth": {"type": "bearer", "token": "tok123"},
    }
    # URL이면 openapi_url로
    wiz._rest_openapi.setText("https://x/openapi.json")
    wiz._rest_token.setText("")
    cfg = wiz._build_target_config()
    assert cfg["openapi_url"] == "https://x/openapi.json" and "auth" not in cfg


def test_target_config_code_all_langs(wiz):
    wiz._target_kind_combo.setCurrentIndex(2)  # api_code
    _select_lang(wiz, "python"); wiz._code_module.setText("/tmp/lib.py"); wiz._code_extra.setText("")
    assert wiz._build_target_config() == {"lang": "python", "module_path": "/tmp/lib.py"}

    _select_lang(wiz, "dotnet"); wiz._code_module.setText("/tmp/Lib.dll")
    assert wiz._build_target_config() == {"lang": "dotnet", "dll_path": "/tmp/Lib.dll"}

    _select_lang(wiz, "java"); wiz._code_module.setText("/tmp/a.jar")
    wiz._code_extra.setText("com.x.A, com.x.B")
    cfg = wiz._build_target_config()
    assert cfg["classpath"] == "/tmp/a.jar" and cfg["classes"] == ["com.x.A", "com.x.B"]

    _select_lang(wiz, "c"); wiz._code_module.setText("/tmp/lib.dll"); wiz._code_extra.setText("/tmp/sig.json")
    assert wiz._build_target_config() == {
        "lang": "c", "dll_path": "/tmp/lib.dll", "signatures_path": "/tmp/sig.json"}


def test_target_config_gui_and_validate(wiz):
    wiz._target_kind_combo.setCurrentIndex(3)  # gui
    wiz._gui_exe.setText("C:/app.exe"); wiz._gui_args.setText("--a --b"); wiz._gui_window.setText("Main.*")
    assert wiz._build_target_config() == {
        "exe_path": "C:/app.exe", "args": ["--a", "--b"], "window_title": "Main.*"}
    assert wiz._validate_page1() is True   # 필수 채워짐 → 다이얼로그 없이 통과

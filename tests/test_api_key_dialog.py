"""API 키 입력 다이얼로그 (요청) — offscreen으로 저장/로드 라운드트립 검증."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_saves_and_loads_key(_app, tmp_path, monkeypatch):
    from app.config import settings as s
    # 실제 ~/.awt를 건드리지 않도록 격리
    monkeypatch.setattr(s, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(s, "_CONFIG_FILE", tmp_path / "settings.enc")
    # 모달 다이얼로그 차단 방지
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    from app.ui.api_key_dialog import ApiKeyDialog
    dlg = ApiKeyDialog()
    for i in range(dlg._provider.count()):
        if dlg._provider.itemData(i) == "openai":
            dlg._provider.setCurrentIndex(i)
    dlg._key.setText("sk-test-abc")
    dlg._model.setText("gpt-4o-mini")
    dlg._save()

    assert s.load_api_key("openai") == "sk-test-abc"
    assert s.get_provider_model("openai") == "gpt-4o-mini"


def test_provider_switch_loads_that_key(_app, tmp_path, monkeypatch):
    from app.config import settings as s
    monkeypatch.setattr(s, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(s, "_CONFIG_FILE", tmp_path / "settings.enc")
    s.save_api_key("anthropic-key", "anthropic")
    s.save_api_key("openai-key", "openai")

    from app.ui.api_key_dialog import ApiKeyDialog
    dlg = ApiKeyDialog()
    for i in range(dlg._provider.count()):
        if dlg._provider.itemData(i) == "anthropic":
            dlg._provider.setCurrentIndex(i)
    assert dlg._key.text() == "anthropic-key"

"""중앙 DB 접속 설정 — 저장/병합 우선순위 + 첫 실행 다이얼로그."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def _isolate(monkeypatch, tmp_path):
    from app.config import settings as s
    monkeypatch.setattr(s, "_CONFIG_DIR", tmp_path)
    monkeypatch.setattr(s, "_CONFIG_FILE", tmp_path / "settings.enc")
    for k in ("AWT_DB_HOST", "AWT_DB_PORT", "AWT_DB_NAME", "AWT_DB_USER", "AWT_DB_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    return s


def test_roundtrip_and_has(monkeypatch, tmp_path):
    s = _isolate(monkeypatch, tmp_path)
    assert s.has_db_settings() is False
    s.save_db_settings({"host": "10.0.0.5", "port": 5433, "dbname": "awt",
                        "user": "awt_user", "password": "pw"})
    assert s.has_db_settings() is True
    eff = s.effective_db_settings()
    assert eff["host"] == "10.0.0.5" and eff["port"] == 5433 and eff["password"] == "pw"


def test_effective_defaults(monkeypatch, tmp_path):
    s = _isolate(monkeypatch, tmp_path)
    eff = s.effective_db_settings()
    assert eff == {"host": "localhost", "port": 5432, "dbname": "awt",
                   "user": "awt_user", "password": ""}


def test_dbconfig_prefers_stored(monkeypatch, tmp_path):
    s = _isolate(monkeypatch, tmp_path)
    s.save_db_settings({"host": "db.example.com", "port": 6000})
    from app.config.db_config import DBConfig
    cfg = DBConfig.from_env()
    assert cfg.host == "db.example.com" and cfg.port == 6000 and cfg.user == "awt_user"


def test_dialog_saves(monkeypatch, tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])  # noqa: F841
    s = _isolate(monkeypatch, tmp_path)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    from app.ui.db_settings_dialog import DbSettingsDialog
    d = DbSettingsDialog()
    # 기본값 pre-fill 확인
    assert d._host.text() == "localhost" and d._port.text() == "5432"
    d._host.setText("1.2.3.4")
    d._pw.setText("secret")
    d._save()
    assert s.get_db_settings()["host"] == "1.2.3.4"
    assert s.effective_db_settings()["password"] == "secret"

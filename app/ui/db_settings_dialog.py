"""중앙 DB 접속 설정 다이얼로그 (클라이언트 첫 실행/재설정).

host/port/dbname/user/password를 현재값(기본값)으로 채워 보여주고 수정 가능.
저장 시 머신 고유값 Fernet 암호화 저장(settings.save_db_settings).
ID/PW(앱 로그인)는 별도 — 실행 시 로그인 창에서 입력.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.config.settings import effective_db_settings, save_db_settings


class DbSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("중앙 DB 접속 설정")
        self.setMinimumWidth(440)
        s = effective_db_settings()

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>중앙 DB 접속 설정</b>"))
        lay.addWidget(QLabel("현재 값이 입력돼 있습니다. 다른 서버에 접속하려면 수정하세요."))

        form = QFormLayout()
        self._host = QLineEdit(str(s["host"]))
        self._host.setPlaceholderText("예: 192.168.0.10 또는 db.example.com")
        self._port = QLineEdit(str(s["port"]))
        self._dbname = QLineEdit(str(s["dbname"]))
        self._user = QLineEdit(str(s["user"]))
        self._pw = QLineEdit(str(s["password"]))
        self._pw.setEchoMode(QLineEdit.Password)
        form.addRow("호스트(host)", self._host)
        form.addRow("포트(port)", self._port)
        form.addRow("DB 이름(dbname)", self._dbname)
        form.addRow("DB 계정(user)", self._user)
        form.addRow("DB 비밀번호", self._pw)
        lay.addLayout(form)

        btns = QHBoxLayout()
        test = QPushButton("연결 테스트")
        test.clicked.connect(self._test)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setDefault(True)
        save.clicked.connect(self._save)
        btns.addWidget(test)
        btns.addStretch()
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

    def _collect(self) -> dict:
        return {
            "host": self._host.text().strip(),
            "port": int((self._port.text().strip() or "5432")),
            "dbname": self._dbname.text().strip(),
            "user": self._user.text().strip(),
            "password": self._pw.text(),
        }

    def _test(self) -> None:
        from app.auth.db_client import DBClient
        from app.config.db_config import DBConfig
        try:
            c = self._collect()
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "포트는 숫자여야 합니다.")
            return
        cfg = DBConfig(host=c["host"], port=c["port"], dbname=c["dbname"],
                       user=c["user"], password=c["password"])
        ok = DBClient.is_available(cfg)
        if ok:
            QMessageBox.information(self, "연결 테스트", "성공 — DB에 연결되었습니다.")
        else:
            QMessageBox.warning(self, "연결 테스트",
                                "실패 — 연결할 수 없습니다(호스트/포트/방화벽 확인).")

    def _save(self) -> None:
        try:
            c = self._collect()
        except ValueError:
            QMessageBox.warning(self, "입력 오류", "포트는 숫자여야 합니다.")
            return
        if not c["host"]:
            QMessageBox.warning(self, "입력 필요", "호스트를 입력하세요.")
            return
        save_db_settings(c)
        QMessageBox.information(self, "저장됨", "DB 접속 설정이 저장되었습니다.")
        self.accept()

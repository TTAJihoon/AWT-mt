"""AWT-MT 라이브 시험 샘플 — 간단한 Windows GUI 앱 (PySide6).

실행: python examples/live-targets/gui/sample_app.py
  - 입력창(txtInput) + Echo 버튼(btnEcho) + 결과 라벨(lblResult)
  - objectName/accessibleName을 지정해 UIA가 AutomationId/Name으로 식별 가능
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)


class SampleApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AWT Sample App")
        self.resize(320, 160)
        lay = QVBoxLayout(self)

        self.inp = QLineEdit()
        self.inp.setObjectName("txtInput")
        self.inp.setAccessibleName("txtInput")
        self.inp.setPlaceholderText("텍스트 입력")

        self.btn = QPushButton("Echo")
        self.btn.setObjectName("btnEcho")
        self.btn.setAccessibleName("btnEcho")

        self.lbl = QLabel("(결과)")
        self.lbl.setObjectName("lblResult")
        self.lbl.setAccessibleName("lblResult")

        for w in (self.inp, self.btn, self.lbl):
            lay.addWidget(w)
        self.btn.clicked.connect(
            lambda: self.lbl.setText(f"echo: {self.inp.text()}"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SampleApp()
    w.show()
    sys.exit(app.exec())

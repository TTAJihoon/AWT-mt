"""API 키 입력 다이얼로그 (D42·D48) — 로그인/설정탭 없이도 키를 직접 입력.

설정 탭과 동일한 백엔드(settings.save_api_key/load_api_key)를 쓰되, 새 실행 직전이나
키 미설정 시 바로 띄울 수 있는 독립 다이얼로그.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.config.settings import (
    DEFAULT_MODELS, VALID_PROVIDERS, get_active_provider, get_provider_model,
    load_api_key, save_api_key, set_active_provider, set_provider_model,
)

_LABELS = {
    "anthropic": "Anthropic (Claude)",
    "openai": "OpenAI (GPT)",
    "google": "Google (Gemini)",
}
_PLACEHOLDERS = {
    "anthropic": "sk-ant-...",
    "openai": "sk-...",
    "google": "AIza...",
}


class ApiKeyDialog(QDialog):
    """provider 선택 + API 키 입력(+마스킹/표시) + 기본 모델 저장."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 키 입력")
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>LLM API 키 입력</b>"))
        lay.addWidget(QLabel("선택한 provider의 키가 암호화되어 로컬에 저장됩니다."))

        self._provider = QComboBox()
        for p in VALID_PROVIDERS:
            self._provider.addItem(_LABELS[p], p)
        cur = get_active_provider()
        if cur in VALID_PROVIDERS:
            self._provider.setCurrentIndex(list(VALID_PROVIDERS).index(cur))
        self._provider.currentIndexChanged.connect(self._on_provider)
        lay.addWidget(QLabel("Provider"))
        lay.addWidget(self._provider)

        self._key = QLineEdit(load_api_key(cur) or "")
        self._key.setEchoMode(QLineEdit.Password)
        self._key.setPlaceholderText(_PLACEHOLDERS.get(cur, "API Key"))
        show = QPushButton("👁")
        show.setCheckable(True)
        show.setFixedWidth(40)
        show.setToolTip("키 보이기/숨기기")
        show.toggled.connect(
            lambda v: self._key.setEchoMode(QLineEdit.Normal if v else QLineEdit.Password))
        krow = QHBoxLayout()
        krow.addWidget(self._key)
        krow.addWidget(show)
        lay.addWidget(QLabel("API Key"))
        lay.addLayout(krow)

        self._model = QLineEdit(get_provider_model(cur) or DEFAULT_MODELS.get(cur, ""))
        lay.addWidget(QLabel("기본 모델 (선택)"))
        lay.addWidget(self._model)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        save = QPushButton("저장")
        save.setDefault(True)
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

    def _on_provider(self, idx: int) -> None:
        p = self._provider.itemData(idx)
        self._key.setText(load_api_key(p) or "")
        self._key.setPlaceholderText(_PLACEHOLDERS.get(p, "API Key"))
        self._model.setText(get_provider_model(p) or DEFAULT_MODELS.get(p, ""))

    def _save(self) -> None:
        p = self._provider.currentData()
        k = self._key.text().strip()
        if not k:
            QMessageBox.warning(self, "입력 필요", "API 키를 입력하세요.")
            return
        save_api_key(k, p)
        set_active_provider(p)
        if self._model.text().strip():
            set_provider_model(p, self._model.text().strip())
        QMessageBox.information(self, "저장됨", f"{_LABELS[p]} 키가 저장되었습니다.")
        self.accept()

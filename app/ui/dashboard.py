"""대시보드 창 — 실행 이력·사용자 관리·설정 (D45: PySide6)."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QLineEdit, QComboBox, QMessageBox,
    QHeaderView, QFrame, QStatusBar, QMenu, QApplication,
)

from app.auth.db_client import DBClient
from app.config.settings import (
    save_api_key, load_api_key, delete_api_key,
    get_active_provider, set_active_provider, VALID_PROVIDERS,
    get_provider_model, set_provider_model, DEFAULT_MODELS,
)

# Provider 표시 라벨 (UI용)
_PROVIDER_LABELS = {
    "anthropic": "Anthropic (Claude)",
    "openai":    "OpenAI (GPT)",
    "google":    "Google (Gemini)",
}
_PROVIDER_PLACEHOLDERS = {
    "anthropic": "sk-ant-...",
    "openai":    "sk-...",
    "google":    "AIza...",
}

RUNS_DIR = Path("data/runs")


class Dashboard(QMainWindow):
    """로그인 후 첫 화면. 새 실행, 이력 조회, 설정."""

    new_run_requested = Signal()       # → wizard 열기
    open_run_requested = Signal(str)   # run_id → pipeline_view 열기
    clone_run_requested = Signal(str)  # run_id → wizard(전체 설정 prefill) 열기
    resume_run_requested = Signal(str, int)   # (run_id, from_stage) → 재개
    logout_requested = Signal()        # → 로그아웃

    def __init__(
        self,
        token: str,
        username: str,
        role: str,
        api_key: str,
        db: DBClient,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"AWT 대시보드 — {username}")
        self.resize(900, 580)
        self._token = token
        self._username = username
        self._role = role
        self._api_key = api_key
        self._db = db

        self._build_ui()
        self._load_runs()

        # 자동 새로고침 (10초마다) — 백그라운드 실행 중인 run의 stage 갱신
        from PySide6.QtCore import QTimer
        self._auto_refresh_timer = QTimer(self)
        self._auto_refresh_timer.setInterval(10_000)   # 10초
        self._auto_refresh_timer.timeout.connect(self._auto_refresh_runs)
        self._auto_refresh_timer.start()

    def _auto_refresh_runs(self) -> None:
        """런닝 중인 run이 있을 때만 새로고침 (UX/성능 절충).

        모든 run이 종료(stage=done) 상태면 굳이 갱신할 필요 없음.
        사용자가 체크박스로 삭제 대상을 고르는 중이면 새로고침을 건너뛴다
        (선택이 날아가는 것을 방지 — _load_runs가 체크를 복원하지만
         진행 중 깜빡임/포커스 변화를 줄이기 위해 아예 스킵).
        """
        try:
            # admin이 체크박스로 선택 중이면 새로고침 보류
            if self._role == "admin" and self._collect_checked_rows():
                return
            # 빠른 검사: meta.json들을 살펴서 진행 중인 게 있는지
            in_progress = False
            if RUNS_DIR.exists():
                for run_dir in RUNS_DIR.iterdir():
                    if not run_dir.is_dir():
                        continue
                    meta = run_dir / "meta.json"
                    if not meta.exists():
                        continue
                    try:
                        m = json.loads(meta.read_text(encoding="utf-8"))
                        st = (m.get("stage") or "").lower()
                        if st and st not in ("done", "error", "started"):
                            # started는 거의 즉시 다른 단계로 넘어가니까 추적용으로 포함
                            in_progress = True
                            break
                        if st == "started":
                            in_progress = True
                            break
                    except Exception:
                        continue
            if in_progress:
                self._load_runs()
        except Exception:
            pass

    # ── UI 구성 ──────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet("QWidget#dash_central { background-color: #f1f5f9; }")
        central.setObjectName("dash_central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 상단 헤더 (global-nav) ────────────────────────────────────────
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("QFrame { background: #000000; border: none; }")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(20, 0, 20, 0)
        h_lay.setSpacing(0)

        lbl = QLabel("AWT")
        lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        lbl.setStyleSheet("color: #ffffff; background: transparent; border: none; letter-spacing: 1px;")
        h_lay.addWidget(lbl)
        h_lay.addStretch()

        user_lbl = QLabel(f"{self._username}  ·  {self._role}")
        user_lbl.setStyleSheet(
            "color: #64748b; font-size: 12px; background: transparent; border: none;"
        )
        h_lay.addWidget(user_lbl)
        h_lay.addSpacing(16)

        logout_btn = QPushButton("로그아웃")
        logout_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #64748b; border: none;"
            " border-radius: 0; padding: 0 4px; font-size: 12px; min-height: 0; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        logout_btn.setCursor(Qt.PointingHandCursor)
        logout_btn.clicked.connect(self.logout_requested)
        h_lay.addWidget(logout_btn)
        root.addWidget(header)

        # ── 탭 ───────────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setStyleSheet(
            "QTabWidget::pane { background: #f1f5f9; border: none; }"
            "QTabBar::tab { background: transparent; color: #64748b;"
            " padding: 10px 20px; font-size: 13px; font-weight: 500;"
            " border: none; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #3b82f6;"
            " border-bottom: 2px solid #3b82f6; font-weight: 600; }"
            "QTabBar::tab:hover { color: #1e293b; }"
            "QTabWidget > QWidget { background: #f1f5f9; }"
        )
        root.addWidget(tabs)

        tabs.addTab(self._build_runs_tab(), "실행 이력")
        tabs.addTab(self._build_settings_tab(), "설정")
        if self._role == "admin":
            tabs.addTab(self._build_users_tab(), "사용자 관리")

        # 상태바
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비")

    def _build_runs_tab(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: #f1f5f9;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(12, 12, 12, 12)
        outer_lay.setSpacing(8)

        # 카드
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #ffffff; border-radius: 8px;"
            " border: 1px solid #e2e8f0; }"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(10)

        # 상단: 제목 + 새로고침 + 새 실행 버튼
        top = QHBoxLayout()
        hdr = QLabel("실행 이력")
        hdr.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 15px; font-weight: 700; color: #1e293b; }"
        )
        top.addWidget(hdr)
        top.addStretch()

        refresh_btn = QPushButton("↺  새로고침")
        refresh_btn.setFixedHeight(34)
        refresh_btn.setStyleSheet(
            "QPushButton { background: #ffffff; color: #64748b;"
            " border-radius: 6px; padding: 0 14px; font-size: 13px;"
            " font-weight: 600; border: 1px solid #e2e8f0; }"
            "QPushButton:hover { background: #f8fafc; color: #1e293b; }"
        )
        refresh_btn.clicked.connect(self._load_runs)
        top.addWidget(refresh_btn)
        top.addSpacing(8)

        # admin 전용: 이력 삭제 버튼
        if self._role == "admin":
            self._del_run_btn = QPushButton("🗑  이력 삭제")
            self._del_run_btn.setFixedHeight(34)
            self._del_run_btn.setStyleSheet(
                "QPushButton { background: #ffffff; color: #ef4444;"
                " border-radius: 6px; padding: 0 14px; font-size: 13px;"
                " font-weight: 600; border: 1px solid #fca5a5; }"
                "QPushButton:hover { background: #fee2e2; }"
                "QPushButton:disabled { color: #cbd5e1; border-color: #e2e8f0; }"
            )
            self._del_run_btn.setEnabled(False)
            self._del_run_btn.setToolTip("선택한 실행 이력과 모든 관련 파일을 영구 삭제합니다")
            self._del_run_btn.clicked.connect(self._delete_run)
            top.addWidget(self._del_run_btn)
            top.addSpacing(8)

        self._new_btn = QPushButton("＋  새 실행")
        self._new_btn.setFixedHeight(34)
        self._new_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: #ffffff;"
            " border-radius: 6px; padding: 0 16px; font-size: 13px;"
            " font-weight: 600; border: none; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        self._new_btn.clicked.connect(self.new_run_requested)
        top.addWidget(self._new_btn)
        lay.addLayout(top)

        # 테이블 (admin: 체크박스 컬럼 포함 6열, reviewer: 5열)
        col_count = 6 if self._role == "admin" else 5
        labels = (
            ["선택", "Run ID", "대상 URL", "TC 수", "단계", "일시"]
            if self._role == "admin"
            else ["Run ID", "대상 URL", "TC 수", "단계", "일시"]
        )
        self._runs_table = QTableWidget(0, col_count)
        self._runs_table.setHorizontalHeaderLabels(labels)
        # 'URL' 컬럼의 인덱스 (admin: 2, reviewer: 1)
        self._url_col = 2 if self._role == "admin" else 1
        # 'Run ID' 컬럼 인덱스 (admin: 1, reviewer: 0)
        self._runid_col = 1 if self._role == "admin" else 0

        hh = self._runs_table.horizontalHeader()
        if self._role == "admin":
            hh.setSectionResizeMode(0, QHeaderView.Fixed)
            self._runs_table.setColumnWidth(0, 50)
        hh.setSectionResizeMode(self._url_col, QHeaderView.Stretch)

        self._runs_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._runs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._runs_table.doubleClicked.connect(self._open_run)
        self._runs_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._runs_table.customContextMenuRequested.connect(self._on_runs_context_menu)
        # shift+click 범위 선택용 — 마지막 클릭 행 추적
        self._last_check_row: int = -1
        # admin: 체크박스 변경/선택 시 삭제 버튼 활성화
        if self._role == "admin":
            self._runs_table.itemChanged.connect(self._on_check_item_changed)
        self._runs_table.setStyleSheet(
            "QTableWidget { border: none; background: #ffffff; }"
            "QHeaderView::section { background-color: #f8fafc; color: #64748b;"
            " font-size: 12px; font-weight: 600; padding: 7px 8px;"
            " border: none; border-bottom: 1px solid #e2e8f0; }"
            "QTableWidget::item { border-bottom: 1px solid #f1f5f9;"
            " padding: 6px 8px; color: #334155; }"
            "QTableWidget::item:selected { background: #eff6ff; color: #1e293b; }"
        )

        # ── 빈 상태 / 테이블 스택 ─────────────────────────────────────────
        from PySide6.QtWidgets import QStackedWidget
        self._runs_stack = QStackedWidget()
        self._runs_stack.addWidget(self._runs_table)         # idx 0
        self._runs_stack.addWidget(self._build_runs_empty()) # idx 1
        lay.addWidget(self._runs_stack)

        outer_lay.addWidget(card)
        return outer

    def _build_runs_empty(self) -> QWidget:
        """실행 이력이 없을 때 표시할 환영 화면 (CTA + 빠른 가이드)."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(14)
        lay.addStretch()

        # 큰 아이콘
        icon = QLabel("🎯")
        icon.setStyleSheet(
            "QLabel { font-size: 56px; background: transparent; border: none; }"
        )
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)

        # 제목
        title = QLabel("AWT에 오신 것을 환영합니다")
        title.setStyleSheet(
            "QLabel { font-size: 20px; font-weight: 700; color: #1e293b;"
            " background: transparent; border: none; }"
        )
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        # 부제
        desc = QLabel(
            "웹사이트 URL만 있으면 AI가 자동으로\n"
            "테스트 케이스를 설계·실행·판정합니다."
        )
        desc.setStyleSheet(
            "QLabel { font-size: 13px; color: #64748b; line-height: 1.5;"
            " background: transparent; border: none; }"
        )
        desc.setAlignment(Qt.AlignCenter)
        lay.addWidget(desc)

        # 빠른 가이드 (3단계)
        steps_box = QFrame()
        steps_box.setMaximumWidth(560)
        steps_box.setStyleSheet(
            "QFrame { background: #f8fafc; border: 1px solid #e2e8f0;"
            " border-radius: 8px; }"
        )
        s_lay = QVBoxLayout(steps_box)
        s_lay.setContentsMargins(20, 14, 20, 14)
        s_lay.setSpacing(8)
        for n, txt in [
            ("1", "URL과 요구사항 문서 입력"),
            ("2", "로그인이 필요하면 인증 단계 설정"),
            ("3", "AI 모델 선택 후 '실행 시작' — 끝!"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(10)
            badge = QLabel(n)
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                "QLabel { background: #3b82f6; color: #ffffff;"
                " border-radius: 11px; font-size: 12px; font-weight: 700;"
                " border: none; }"
            )
            row.addWidget(badge)
            txt_lbl = QLabel(txt)
            txt_lbl.setStyleSheet(
                "QLabel { color: #334155; font-size: 13px;"
                " background: transparent; border: none; }"
            )
            row.addWidget(txt_lbl)
            row.addStretch()
            s_lay.addLayout(row)
        # 가운데 정렬용 wrapper
        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addWidget(steps_box)
        wrap.addStretch()
        lay.addLayout(wrap)

        # 큰 CTA 버튼
        cta_btn = QPushButton("＋  첫 실행 시작하기")
        cta_btn.setFixedSize(220, 48)
        cta_btn.setStyleSheet(
            "QPushButton {"
            " background: #3b82f6; color: #ffffff;"
            " border: none; border-radius: 8px;"
            " padding: 0 20px; font-size: 15px; font-weight: 600;"
            "}"
            "QPushButton:hover { background: #2563eb; }"
        )
        cta_btn.clicked.connect(self.new_run_requested)
        cta_wrap = QHBoxLayout()
        cta_wrap.addStretch()
        cta_wrap.addWidget(cta_btn)
        cta_wrap.addStretch()
        lay.addLayout(cta_wrap)

        lay.addStretch()
        return w

    def _build_settings_tab(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background: #f1f5f9;")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(12, 12, 12, 12)
        outer_lay.setSpacing(8)

        # 카드
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #ffffff; border-radius: 8px;"
            " border: 1px solid #e2e8f0; }"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(14)

        hdr = QLabel("API 설정")
        hdr.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 15px; font-weight: 700; color: #1e293b;"
            " padding-bottom: 4px; border-bottom: 1px solid #f1f5f9; }"
        )
        lay.addWidget(hdr)

        # ── Provider 선택 ─────────────────────────────────────────────────
        lbl_prov = QLabel("LLM Provider")
        lbl_prov.setStyleSheet(
            "QLabel { font-size: 12px; font-weight: 600; color: #374151;"
            " background: transparent; border: none; }"
        )
        lay.addWidget(lbl_prov)
        self._provider_combo = QComboBox()
        for p in VALID_PROVIDERS:
            self._provider_combo.addItem(_PROVIDER_LABELS[p], userData=p)
        current = get_active_provider()
        idx = list(VALID_PROVIDERS).index(current) if current in VALID_PROVIDERS else 0
        self._provider_combo.setCurrentIndex(idx)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        lay.addWidget(self._provider_combo)

        # ── API Key ───────────────────────────────────────────────────────
        self._api_label = QLabel(f"{_PROVIDER_LABELS[current]} API Key")
        self._api_label.setStyleSheet(
            "QLabel { font-size: 12px; font-weight: 600; color: #374151;"
            " background: transparent; border: none; }"
        )
        lay.addWidget(self._api_label)

        api_row = QHBoxLayout()
        api_row.setSpacing(8)
        self._api_edit = QLineEdit(load_api_key(current) or "")
        self._api_edit.setEchoMode(QLineEdit.Password)
        self._api_edit.setPlaceholderText(_PROVIDER_PLACEHOLDERS[current])
        self._api_edit.setFixedHeight(36)
        api_row.addWidget(self._api_edit)

        # API key 보이기/숨기기 토글
        self._api_show_btn = QPushButton("👁")
        self._api_show_btn.setCheckable(True)
        self._api_show_btn.setFixedSize(40, 36)
        self._api_show_btn.setToolTip("API Key 보이기/숨기기")
        self._api_show_btn.setStyleSheet(
            "QPushButton { background: #ffffff; color: #64748b;"
            " border: 1px solid #e2e8f0; border-radius: 6px;"
            " font-size: 14px; padding: 0; }"
            "QPushButton:hover { background: #f1f5f9; }"
            "QPushButton:checked { background: #eff6ff; color: #1d4ed8;"
            " border-color: #93c5fd; }"
        )
        self._api_show_btn.toggled.connect(self._toggle_api_visible)
        api_row.addWidget(self._api_show_btn)

        _btn_style = (
            "QPushButton { border-radius: 6px; padding: 0 14px; font-size: 12px;"
            " font-weight: 600; height: 36px; }"
        )
        save_btn = QPushButton("저장")
        save_btn.setFixedHeight(36)
        save_btn.setStyleSheet(
            _btn_style +
            "QPushButton { background: #3b82f6; color: #fff; border: none; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        save_btn.clicked.connect(self._save_api_key)
        api_row.addWidget(save_btn)

        del_btn = QPushButton("삭제")
        del_btn.setFixedHeight(36)
        del_btn.setStyleSheet(
            _btn_style +
            "QPushButton { background: #fff; color: #ef4444;"
            " border: 1px solid #fca5a5; }"
            "QPushButton:hover { background: #fee2e2; }"
        )
        del_btn.clicked.connect(self._delete_api_key)
        api_row.addWidget(del_btn)
        lay.addLayout(api_row)

        # ── 기본 모델 ─────────────────────────────────────────────────────
        lbl_model = QLabel(f"{_PROVIDER_LABELS[current]} 기본 모델")
        lbl_model.setStyleSheet(
            "QLabel { font-size: 12px; font-weight: 600; color: #374151;"
            " background: transparent; border: none; }"
        )
        lay.addWidget(lbl_model)
        self._model_label = lbl_model

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self._model_edit = QLineEdit(get_provider_model(current) or "")
        self._model_edit.setPlaceholderText(DEFAULT_MODELS.get(current, ""))
        self._model_edit.setFixedHeight(36)
        model_row.addWidget(self._model_edit)

        model_save_btn = QPushButton("저장")
        model_save_btn.setFixedHeight(36)
        model_save_btn.setStyleSheet(
            "QPushButton { border-radius: 6px; padding: 0 14px; font-size: 12px;"
            " font-weight: 600; height: 36px;"
            " background: #3b82f6; color: #fff; border: none; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        model_save_btn.clicked.connect(self._save_provider_model)
        model_row.addWidget(model_save_btn)
        lay.addLayout(model_row)

        # 안내
        hint = QLabel(
            "Provider별 API 키와 기본 모델은 각각 따로 저장됩니다.\n"
            "Provider를 전환하면 해당 provider의 키와 모델이 자동으로 적용됩니다.\n"
            "기본 모델을 비워두면 내장 기본값(claude-sonnet-4-6 / gpt-4o / gemini-2.5-flash)을 사용합니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "QLabel { color: #94a3b8; font-size: 11px;"
            " background: transparent; border: none; }"
        )
        lay.addWidget(hint)
        lay.addStretch()

        outer_lay.addWidget(card)
        outer_lay.addStretch()
        return outer

    def _toggle_api_visible(self, visible: bool) -> None:
        """API Key 입력란의 마스킹 토글."""
        self._api_edit.setEchoMode(
            QLineEdit.Normal if visible else QLineEdit.Password
        )
        self._api_show_btn.setText("🙈" if visible else "👁")

    def _on_provider_changed(self, index: int) -> None:
        """Provider 드롭다운 변경 시 — 활성 provider 갱신 + 해당 키/모델 로드."""
        provider = self._provider_combo.itemData(index)
        if not provider:
            return
        set_active_provider(provider)
        label = _PROVIDER_LABELS[provider]
        self._api_label.setText(f"{label} API Key")
        self._api_edit.setText(load_api_key(provider) or "")
        self._api_edit.setPlaceholderText(_PROVIDER_PLACEHOLDERS[provider])
        self._model_label.setText(f"{label} 기본 모델")
        self._model_edit.setText(get_provider_model(provider) or "")
        self._model_edit.setPlaceholderText(DEFAULT_MODELS.get(provider, ""))
        self.statusBar().showMessage(f"Provider 전환: {label}", 3000)

    def _save_provider_model(self) -> None:
        """기본 모델 저장."""
        provider = self._provider_combo.currentData()
        model = self._model_edit.text().strip()
        if not model:
            # 빈 값이면 저장된 값 삭제 → 내장 기본값으로 복귀
            from app.config.settings import _load_payload, _save_payload
            data = _load_payload()
            data.pop(f"{provider}_model", None)
            _save_payload(data)
            self.statusBar().showMessage("기본 모델 초기화 (내장 기본값 사용)", 3000)
            return
        try:
            set_provider_model(provider, model)
            self.statusBar().showMessage(f"기본 모델 저장: {model}", 3000)
        except ValueError as e:
            QMessageBox.warning(self, "저장 실패", str(e))

    def _build_users_tab(self) -> QWidget:
        """admin 전용 사용자 관리 탭."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        form = QHBoxLayout()
        self._new_user_edit = QLineEdit()
        self._new_user_edit.setPlaceholderText("사용자명")
        self._new_pw_edit = QLineEdit()
        self._new_pw_edit.setPlaceholderText("초기 비밀번호")
        self._new_pw_edit.setEchoMode(QLineEdit.Password)
        self._role_combo = QComboBox()
        self._role_combo.addItems(["reviewer", "admin"])
        add_btn = QPushButton("추가")
        add_btn.clicked.connect(self._add_user)
        form.addWidget(self._new_user_edit)
        form.addWidget(self._new_pw_edit)
        form.addWidget(self._role_combo)
        form.addWidget(add_btn)
        lay.addLayout(form)

        self._users_table = QTableWidget(0, 3)
        self._users_table.setHorizontalHeaderLabels(["사용자명", "역할", "생성일"])
        self._users_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self._users_table)

        del_btn2 = QPushButton("선택 사용자 삭제")
        del_btn2.clicked.connect(self._delete_user)
        lay.addWidget(del_btn2, alignment=Qt.AlignRight)

        self._refresh_users()
        return w

    # ── 데이터 로딩 ──────────────────────────────────────────────────────
    def _load_runs(self) -> None:
        # 재로딩 전 체크된 run_id 보존 (자동 새로고침에 선택이 날아가지 않도록)
        checked_ids: set[str] = set()
        if self._role == "admin":
            for r in range(self._runs_table.rowCount()):
                chk = self._runs_table.item(r, 0)
                rid_item = self._runs_table.item(r, self._runid_col)
                if chk is not None and rid_item is not None and chk.checkState() == Qt.Checked:
                    checked_ids.add(rid_item.text())

        # itemChanged 폭탄 방지
        self._runs_table.blockSignals(True)
        try:
            self._runs_table.setRowCount(0)
            if not RUNS_DIR.exists():
                return
            runs = sorted(RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            is_admin = self._role == "admin"
            for run_dir in runs[:50]:
                meta_path = run_dir / "meta.json"
                meta: dict = {}
                if meta_path.exists():
                    try:
                        meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                tc_count = "?"
                tc_path = run_dir / "tc_raw.json"
                if tc_path.exists():
                    try:
                        tc_count = str(len(json.loads(tc_path.read_text(encoding="utf-8"))))
                    except Exception:
                        pass
                row = self._runs_table.rowCount()
                self._runs_table.insertRow(row)

                col_offset = 0
                if is_admin:
                    # 열 0: 체크박스 (이전에 체크돼 있던 run이면 유지)
                    chk = QTableWidgetItem()
                    chk.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
                    )
                    chk.setCheckState(
                        Qt.Checked if run_dir.name in checked_ids else Qt.Unchecked
                    )
                    chk.setTextAlignment(Qt.AlignCenter)
                    self._runs_table.setItem(row, 0, chk)
                    col_offset = 1

                self._runs_table.setItem(row, col_offset + 0, QTableWidgetItem(run_dir.name))
                self._runs_table.setItem(row, col_offset + 1, QTableWidgetItem(meta.get("target_url", "-")))
                self._runs_table.setItem(row, col_offset + 2, QTableWidgetItem(tc_count))
                self._runs_table.setItem(row, col_offset + 3, QTableWidgetItem(meta.get("stage", "-")))
                self._runs_table.setItem(row, col_offset + 4, QTableWidgetItem(meta.get("created_at", "-")))
        finally:
            self._runs_table.blockSignals(False)
        # 행 수에 따라 빈 상태 / 테이블 자동 전환
        if hasattr(self, "_runs_stack"):
            self._runs_stack.setCurrentIndex(
                1 if self._runs_table.rowCount() == 0 else 0
            )
        # 로드 후 삭제 버튼 상태 갱신
        if self._role == "admin":
            self._on_check_changed()

    def _open_run(self) -> None:
        row = self._runs_table.currentRow()
        if row < 0:
            return
        item = self._runs_table.item(row, self._runid_col)
        if not item:
            return
        run_id = item.text()
        self.open_run_requested.emit(run_id)

    def _on_run_selection_changed(self) -> None:
        """행 선택 변경 시(체크 상태와 무관) 삭제 버튼 상태 갱신."""
        # admin: 체크박스 우선, 선택 행은 대체 트리거
        self._on_check_changed()

    def _on_check_item_changed(self, item) -> None:
        """체크박스 변경 핸들러 — shift+click 시 범위 다중 선택 (기존 체크 유지)."""
        if self._role != "admin" or item is None or item.column() != 0:
            self._on_check_changed()
            return

        row = item.row()
        target_state = item.checkState()

        mods = QApplication.keyboardModifiers()
        if (
            (mods & Qt.ShiftModifier)
            and self._last_check_row >= 0
            and self._last_check_row != row
        ):
            lo, hi = sorted([self._last_check_row, row])
            self._runs_table.blockSignals(True)
            try:
                for r in range(lo, hi + 1):
                    if r == row:
                        continue
                    chk = self._runs_table.item(r, 0)
                    if chk is not None:
                        chk.setCheckState(target_state)
            finally:
                self._runs_table.blockSignals(False)

        self._last_check_row = row
        self._on_check_changed()

    def _on_check_changed(self, _item=None) -> None:
        """삭제 버튼 활성화/비활성화 + 라벨에 개수 표시."""
        if self._role != "admin":
            return
        checked_rows = self._collect_checked_rows()
        n = len(checked_rows)
        if n > 0:
            self._del_run_btn.setText(f"🗑  이력 삭제 ({n})")
            self._del_run_btn.setEnabled(True)
        else:
            self._del_run_btn.setText("🗑  이력 삭제")
            self._del_run_btn.setEnabled(False)

    def _collect_checked_rows(self) -> list[int]:
        """체크된 행 인덱스 목록을 반환 (admin 전용)."""
        if self._role != "admin":
            return []
        rows: list[int] = []
        for r in range(self._runs_table.rowCount()):
            chk = self._runs_table.item(r, 0)
            if chk is not None and chk.checkState() == Qt.Checked:
                rows.append(r)
        return rows

    def _on_runs_context_menu(self, pos) -> None:
        """우클릭 컨텍스트 메뉴 — 복제 / 이어서 진행 / admin이면 삭제도."""
        row = self._runs_table.rowAt(pos.y())
        if row < 0:
            return
        url_item   = self._runs_table.item(row, self._url_col)
        runid_item = self._runs_table.item(row, self._runid_col)
        url   = url_item.text() if url_item else ""
        run_id = runid_item.text() if runid_item else ""
        has_url = bool(url) and url != "-"

        # 재개 가능 여부 검사 — tc_gated.json / tc_verified.json 존재 확인
        resume_stage: int | None = None
        if run_id:
            from app.core.orchestrator import Orchestrator
            run_dir = RUNS_DIR / run_id
            resume_stage = Orchestrator.suggest_resume_stage(run_dir)

        menu = QMenu(self)
        clone_action = menu.addAction("복제 (모든 설정 복사 + 새 마법사)")
        clone_action.setEnabled(bool(run_id))

        resume_action = None
        if resume_stage is not None:
            menu.addSeparator()
            label = (
                "🔄  Stage 4 (Reviewer Gate)부터 재개"
                if resume_stage == 4
                else "🔄  Stage 5~7부터 재개 (Gate 결정 보존)"
            )
            resume_action = menu.addAction(label)

        delete_action = None
        if self._role == "admin":
            menu.addSeparator()
            delete_action = menu.addAction("🗑  이력 삭제")

        action = menu.exec(self._runs_table.viewport().mapToGlobal(pos))
        if action == clone_action and run_id:
            if has_url:
                QApplication.clipboard().setText(url)
            self.clone_run_requested.emit(run_id)
            self.statusBar().showMessage(f"'{run_id}' 설정을 복제합니다", 3000)
        elif resume_action is not None and action == resume_action:
            self.resume_run_requested.emit(run_id, resume_stage)
        elif action is not None and action == delete_action:
            # 우클릭 → 해당 행만 체크 후 삭제 (다중 체크된 상태 보존)
            chk = self._runs_table.item(row, 0)
            if chk is not None:
                chk.setCheckState(Qt.Checked)
            self._runs_table.selectRow(row)
            self._delete_run()

    def _delete_run(self) -> None:
        """체크된 실행 이력을 영구 삭제 (admin 전용, 다중 가능)."""
        if self._role != "admin":
            return

        checked_rows = self._collect_checked_rows()
        # 체크박스 없으면 현재 선택 행 사용 (단건 폴백)
        if not checked_rows:
            cur = self._runs_table.currentRow()
            if cur < 0:
                QMessageBox.information(
                    self, "알림",
                    "체크박스로 삭제할 이력을 선택하거나, 행을 선택한 뒤 다시 누르세요."
                )
                return
            checked_rows = [cur]

        # 삭제 대상 정보 수집
        targets: list[tuple[str, str, str]] = []   # (run_id, url, tc_count)
        for r in checked_rows:
            runid_item = self._runs_table.item(r, self._runid_col)
            url_item   = self._runs_table.item(r, self._url_col)
            tc_item    = self._runs_table.item(r, self._url_col + 1)
            if runid_item:
                targets.append((
                    runid_item.text(),
                    url_item.text() if url_item else "-",
                    tc_item.text()  if tc_item  else "?",
                ))

        if not targets:
            return

        # 확인 다이얼로그
        n = len(targets)
        if n == 1:
            rid, url, tc_n = targets[0]
            body = (
                f"아래 이력과 관련 파일(스크린샷, TC 파일, LLM 로그 등)을 모두 영구 삭제합니다.\n\n"
                f"  Run ID : {rid}\n"
                f"  URL    : {url}\n"
                f"  TC 수  : {tc_n}\n\n"
                "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
            )
        else:
            lines = "\n".join(
                f"  • {rid}  ({url} / TC {tc_n})" for rid, url, tc_n in targets[:10]
            )
            extra = f"\n  … 외 {n - 10}건" if n > 10 else ""
            body = (
                f"아래 {n}개 이력과 관련 파일을 모두 영구 삭제합니다.\n\n"
                f"{lines}{extra}\n\n"
                "이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?"
            )

        confirmed = QMessageBox.warning(
            self,
            "실행 이력 삭제",
            body,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirmed != QMessageBox.Yes:
            return

        # 일괄 삭제 (실패한 건 모아서 보고)
        failed: list[tuple[str, str]] = []
        ok = 0
        for rid, _, _ in targets:
            run_dir = RUNS_DIR / rid
            try:
                if run_dir.exists():
                    shutil.rmtree(run_dir)
                ok += 1
            except Exception as e:
                failed.append((rid, str(e)))

        self._load_runs()
        if failed:
            msg = "\n".join(f"  • {rid} → {err}" for rid, err in failed[:5])
            QMessageBox.critical(
                self, "일부 삭제 실패",
                f"{ok}개 삭제 / {len(failed)}개 실패\n\n{msg}"
            )
        else:
            self.statusBar().showMessage(f"{ok}개 이력 삭제 완료", 4000)

    # ── 설정 액션 ────────────────────────────────────────────────────────
    def _save_api_key(self) -> None:
        provider = self._provider_combo.currentData()
        key = self._api_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "경고", "API Key가 비어있습니다.")
            return
        save_api_key(key, provider=provider)
        # 저장 확인 — 실제로 읽혀지는지 검증
        saved = load_api_key(provider)
        if saved != key:
            QMessageBox.critical(
                self, "저장 실패",
                "API Key 저장 중 오류가 발생했습니다.\n다시 시도해 주세요."
            )
            return
        label = _PROVIDER_LABELS[provider]
        masked = key[:8] + "..." + key[-4:]
        QMessageBox.information(
            self, "저장 완료",
            f"{label} API Key가 저장되었습니다.\n\n"
            f"  Provider : {label}\n"
            f"  Key      : {masked}\n\n"
            "다음 실행부터 적용됩니다."
        )
        self.statusBar().showMessage(f"{label} API Key 저장 완료", 3000)

    def _delete_api_key(self) -> None:
        provider = self._provider_combo.currentData()
        delete_api_key(provider=provider)
        self._api_edit.clear()
        self.statusBar().showMessage(
            f"{_PROVIDER_LABELS[provider]} API Key 삭제 완료", 3000
        )

    # ── 사용자 관리 액션 ──────────────────────────────────────────────────
    def _refresh_users(self) -> None:
        try:
            users = self._db.list_users()
        except Exception:
            return
        self._users_table.setRowCount(0)
        for u in users:
            row = self._users_table.rowCount()
            self._users_table.insertRow(row)
            self._users_table.setItem(row, 0, QTableWidgetItem(u["username"]))
            self._users_table.setItem(row, 1, QTableWidgetItem(u["role"]))
            self._users_table.setItem(row, 2, QTableWidgetItem(str(u.get("created_at", ""))))

    def _add_user(self) -> None:
        username = self._new_user_edit.text().strip()
        password = self._new_pw_edit.text()
        role = self._role_combo.currentText()
        if not username or not password:
            QMessageBox.warning(self, "입력 오류", "사용자명과 비밀번호를 입력하세요.")
            return
        try:
            self._db.create_user(username, password, role)
            self._new_user_edit.clear()
            self._new_pw_edit.clear()
            self._refresh_users()
        except ValueError as e:
            QMessageBox.warning(self, "오류", str(e))

    def _delete_user(self) -> None:
        row = self._users_table.currentRow()
        if row < 0:
            return
        username = self._users_table.item(row, 0).text()
        if username == self._username:
            QMessageBox.warning(self, "오류", "본인 계정은 삭제할 수 없습니다.")
            return
        confirmed = QMessageBox.question(
            self, "확인", f"'{username}'을(를) 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirmed == QMessageBox.Yes:
            self._db.delete_user(username)
            self._refresh_users()

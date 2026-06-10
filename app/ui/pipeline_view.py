"""파이프라인 실행 진행 창 — Stage 0~7 실시간 로그 (D45: PySide6)."""
from __future__ import annotations
import json
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QFont, QColor, QTextCursor, QTextBlockFormat, QFontMetrics, QIcon,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QPlainTextEdit, QLineEdit,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QStatusBar, QFileDialog, QDialog, QSystemTrayIcon,
    QApplication, QStyle, QCheckBox,
)

from app.core.orchestrator import Orchestrator, RunConfig
from app.ui.theme import pill_btn

# ── 한글 변환 테이블 ──────────────────────────────────────────────────────────
_TECHNIQUE_KO: dict[str, str] = {
    "happy_path":       "정상 흐름",
    "negative_basic":   "오류 기본",
    "negative_deep":    "오류 심층",
    "boundary":         "경계값 분석",
    "equivalence":      "동등 분할",
    "state_transition": "상태 전이",
    "cross_feature":    "기능 간 연계",
}

_STATUS_KO: dict[str, str] = {
    "pending":  "검토 전",
    "approved": "승인",
    "edited":   "수정",
    "rejected": "거부",
}

_RESULT_KO: dict[str, str] = {
    "not_executed": "실행 전",
    "pass":         "통과",
    "fail":         "실패",
    "blocked":      "차단",
}

# ── Stage 원형 스타일 ─────────────────────────────────────────────────────────
_CIRCLE_DONE = (
    "QLabel { background-color: #3b82f6; color: #ffffff;"
    " border-radius: 16px; font-size: 13px; font-weight: 700; border: none; }"
)
_CIRCLE_CURRENT = (
    "QLabel { background-color: #ffffff; color: #3b82f6;"
    " border-radius: 16px; border: 3px solid #3b82f6;"
    " font-size: 13px; font-weight: 700; }"
)
_CIRCLE_FUTURE = (
    "QLabel { background-color: #f8fafc; color: #94a3b8;"
    " border-radius: 16px; border: 2px solid #cbd5e1;"
    " font-size: 13px; font-weight: 700; }"
)
_LINE_DONE    = "QFrame { background-color: #3b82f6; border: none; }"
_LINE_PENDING = "QFrame { background-color: #e2e8f0; border: none; }"

# ── 카드 공통 스타일 ──────────────────────────────────────────────────────────
_CARD = (
    "QFrame { background-color: #ffffff; border-radius: 8px;"
    " border: 1px solid #e2e8f0; }"
)


# ── Stage 원형 — 클릭 가능 라벨 ────────────────────────────────────────────────
class _StageCircle(QLabel):
    """Stage 진행 원. 클릭 시 stage 번호와 함께 시그널 발사."""
    clicked = Signal(int)

    def __init__(self, stage_num: int, parent=None):
        super().__init__(str(stage_num), parent)
        self._stage_num = stage_num
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(32, 32)
        # 커서는 _update_circles에서 진행 상태에 따라 동적 설정 (초기엔 기본 화살표)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._stage_num)
        super().mousePressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Worker threads
# ─────────────────────────────────────────────────────────────────────────────

class _PreGateWorker(QThread):
    """Stage 0~3 백그라운드 실행.

    D53 기능 확정 게이트 지원:
      - stop_after_ingest=True  → Stage 0~1만 실행 후 ingest_ready(leaves) emit하고 정지.
      - resume_from_stage2=True → Stage 0~1 생략, Stage 2~3만 실행(게이트 확정 후 재개).
      - 둘 다 False(기본)      → Stage 0~3 연속 실행(게이트 미사용 기존 동작).
    """
    stage_done   = Signal(int)
    finished     = Signal(list)
    error        = Signal(str)
    ingest_ready = Signal(list)   # D53 — Stage 1 후 leaves 전달(게이트용)

    def __init__(self, orch: Orchestrator, has_files: bool, reuse_stage0: bool = False,
                 stop_after_ingest: bool = False, resume_from_stage2: bool = False):
        super().__init__()
        self._orch      = orch
        self._has_files = has_files
        self._reuse_stage0 = reuse_stage0   # 기존 Stage 0 draft 재사용 (재스캔 생략)
        self._stop_after_ingest  = stop_after_ingest
        self._resume_from_stage2 = resume_from_stage2

    # 사용자 중단 시그널 — 중단되어도 부분 TC를 넘김
    stopped = Signal(list)

    def run(self) -> None:
        try:
            if not self._resume_from_stage2:
                feature_spec = None
                has_url = bool(self._orch.config.target_url)
                # 비웹 대상(REST/코드라이브러리/GUI)은 target_url이 없고 정보가
                # target_config에 있다 → URL 유무와 무관하게 어댑터 probe(Stage 0)를 실행.
                target_kind = getattr(self._orch.config, "target_kind", "web") or "web"
                is_nonweb = target_kind in ("api_rest", "api_code", "gui")

                # Stage 0 실행 조건:
                # 1) 매뉴얼 파일 없이 URL만 있을 때 (원래 동작)
                # 2) 매뉴얼 파일이 있더라도 URL이 있으면 스크린샷/DOM 수집 실행
                #    (매뉴얼+URL 동시 사용 시에도 스크린샷이 저장되어야 하므로)
                should_run_stage0 = has_url and not self._reuse_stage0 and not self._orch.has_stage0_draft()
                should_reuse_stage0 = has_url and self._reuse_stage0

                if is_nonweb:
                    # 어댑터 probe로 대상 구조 스캔(OpenAPI 파싱·심볼 리플렉션·UIA 등)
                    feature_spec = self._orch.run_stage0()
                    if self._orch.is_stopped():
                        self.stopped.emit([]); return
                    self.stage_done.emit(1)
                elif should_reuse_stage0:
                    # 기존 분석 결과 로드 — DOM 재스캔/페이지선택 생략
                    feature_spec = self._orch.load_stage0_draft()
                    if feature_spec is None:
                        feature_spec = self._orch.run_stage0()
                    if self._orch.is_stopped():
                        self.stopped.emit([]); return
                    self.stage_done.emit(1)
                elif should_run_stage0:
                    feature_spec = self._orch.run_stage0()
                    if self._orch.is_stopped():
                        self.stopped.emit([]); return
                    self.stage_done.emit(1)
                elif not self._has_files:
                    # URL도 없고 파일도 없는 경우 (비정상) — 기존 동작 유지
                    pass
                self._orch.run_stage1(feature_spec)
                if self._orch.is_stopped():
                    self.stopped.emit([]); return
                self.stage_done.emit(2)
                if self._stop_after_ingest:
                    # D53 — 게이트로 leaves 전달 후 정지(메인스레드가 Stage 2~3 재개)
                    leaves = (self._orch.ingest_result or {}).get("leaves", [])
                    self.ingest_ready.emit(leaves)
                    return
            self._orch.run_stage2()
            if self._orch.is_stopped():
                # Stage 2 중단 — 지금까지 만든 TC가 있으면 보존
                self.stopped.emit(self._orch.tcs or []); return
            self.stage_done.emit(3)
            tcs = self._orch.run_stage3()
            self.stage_done.emit(4)
            self.finished.emit(tcs)
        except Exception:
            self.error.emit(traceback.format_exc())


class _PostGateWorker(QThread):
    """Stage 5~7 백그라운드 실행."""
    stage_done    = Signal(int)
    finished      = Signal(object)   # Path
    error         = Signal(str)
    defects_found = Signal(int)      # Stage 6B: 신규 결함 수

    def __init__(self, orch: Orchestrator):
        super().__init__()
        self._orch = orch

    def run(self) -> None:
        try:
            self._orch.run_stage5()
            self.stage_done.emit(5)
            self._orch.run_stage6()
            self.stage_done.emit(6)
            new_defects = self._orch.run_stage6b()
            self.defects_found.emit(len(new_defects))
            out = self._orch.run_stage7()
            self.stage_done.emit(7)
            self.finished.emit(out)
        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# PipelineView
# ─────────────────────────────────────────────────────────────────────────────

class PipelineView(QMainWindow):
    """파이프라인 실행 창."""

    gate_review_requested = Signal(list)
    clone_requested = Signal(str)   # run_id → 설정 복제하여 재실행(main.py가 처리)
    _log_signal     = Signal(str)
    _raw_log_signal = Signal(str)   # 상세 로그(humanize 전 원본)

    @property
    def config(self) -> RunConfig:
        """main.py에서 run_id 접근용 (pv.config.run_id)."""
        return self._config

    def __init__(self, config: RunConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"AWT 실행 — {config.run_id}")
        self.resize(1120, 720)
        self._config      = config
        self._orch        = Orchestrator(
            config,
            progress_cb=self._log_signal.emit,
            raw_progress_cb=self._raw_log_signal.emit,
        )
        self._pre_worker:  _PreGateWorker | None = None
        self._post_worker: _PostGateWorker | None = None
        self._tcs: list[dict] = []

        self._build_ui()
        self._log_signal.connect(self._append_log)
        self._raw_log_signal.connect(self._append_raw_log)
        self._write_meta("started")

        # 시스템 트레이 알림 (Stage 5/7 완료 / 오류 발생 시 OS 알림)
        self._tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            try:
                self._tray = QSystemTrayIcon(self)
                # 시스템 기본 정보 아이콘 사용 (별도 리소스 의존 X)
                self._tray.setIcon(
                    self.style().standardIcon(QStyle.SP_ComputerIcon)
                )
                self._tray.setToolTip(f"AWT — {config.run_id}")
                self._tray.show()
            except Exception:
                self._tray = None

    # ── UI 구성 ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet("QWidget#central { background-color: #f1f5f9; }")
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── 상단 바 ──────────────────────────────────────────────────────────
        top_card = QFrame()
        top_card.setStyleSheet(_CARD)
        top_card.setFixedHeight(52)
        top_lay = QHBoxLayout(top_card)
        top_lay.setContentsMargins(16, 0, 16, 0)

        url_lbl = QLabel(f"대상 URL :  {self._config.target_url}")
        url_lbl.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 14px; font-weight: 500; color: #1e293b; }"
        )
        top_lay.addWidget(url_lbl)
        top_lay.addStretch()

        cur_lbl = QLabel("현재 진행")
        cur_lbl.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 12px; font-weight: 600; color: #64748b; }"
        )
        top_lay.addWidget(cur_lbl)

        self._stage_badge = QLabel("준비 중")
        self._stage_badge.setStyleSheet(
            "QLabel { background-color: #eff6ff; color: #1d4ed8;"
            " border: 1px solid #bfdbfe; border-radius: 6px;"
            " padding: 4px 14px; font-size: 13px; font-weight: 700; }"
        )
        top_lay.addWidget(self._stage_badge)
        root.addWidget(top_card)

        # ── Stage 진행 원형 표시기 ────────────────────────────────────────────
        prog_card = QFrame()
        prog_card.setStyleSheet(_CARD)
        prog_card.setFixedHeight(64)
        prog_lay = QHBoxLayout(prog_card)
        prog_lay.setContentsMargins(32, 0, 32, 0)

        self._circles: list[_StageCircle] = []
        self._lines:   list[QFrame] = []
        # 진행했던 최대 stage 번호 — 클릭으로 과거/현재 stage 보기 위함
        self._max_progress: int = 0

        for i in range(1, 8):
            circle = _StageCircle(i)
            circle.setStyleSheet(_CIRCLE_FUTURE)
            circle.clicked.connect(self._on_stage_circle_clicked)
            circle.setToolTip(f"Stage {i} 보기 (진행한 단계만 클릭 가능)")
            self._circles.append(circle)
            prog_lay.addWidget(circle)
            if i < 7:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFixedHeight(4)
                line.setStyleSheet(_LINE_PENDING)
                self._lines.append(line)
                prog_lay.addWidget(line, 1)

        root.addWidget(prog_card)

        # ── 메인 스플리터 ─────────────────────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter { background: transparent; border: none; }")

        # 로그 패널 (좌)
        log_card = QFrame()
        log_card.setStyleSheet(_CARD)
        log_lay = QVBoxLayout(log_card)
        log_lay.setContentsMargins(12, 12, 12, 12)
        log_lay.setSpacing(6)

        # 로그 헤더 + 상세 로그 토글 버튼
        log_hdr_row = QHBoxLayout()
        log_hdr_row.setContentsMargins(0, 0, 0, 0)
        log_hdr = QLabel("실행 로그")
        log_hdr.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 15px; font-weight: 700; color: #1e293b;"
            " padding-bottom: 6px; border-bottom: 1px solid #f1f5f9; }"
        )
        log_hdr_row.addWidget(log_hdr)
        log_hdr_row.addStretch()

        # 로그 검색 입력
        self._log_search = QLineEdit()
        self._log_search.setPlaceholderText("🔍  로그 검색…")
        self._log_search.setFixedHeight(24)
        self._log_search.setFixedWidth(180)
        self._log_search.setStyleSheet(
            "QLineEdit { background: #ffffff; border: 1px solid #cbd5e1;"
            " border-radius: 4px; padding: 2px 8px; font-size: 11px; }"
            "QLineEdit:focus { border: 1px solid #3b82f6; padding: 1px 7px; }"
        )
        self._log_search.returnPressed.connect(self._log_find_next)
        self._log_search.textChanged.connect(self._log_search_changed)
        log_hdr_row.addWidget(self._log_search)

        self._log_prev_btn = QPushButton("↑")
        self._log_prev_btn.setFixedSize(24, 24)
        self._log_prev_btn.setToolTip("이전 결과 (Shift+Enter)")
        self._log_prev_btn.clicked.connect(self._log_find_prev)
        self._log_next_btn = QPushButton("↓")
        self._log_next_btn.setFixedSize(24, 24)
        self._log_next_btn.setToolTip("다음 결과 (Enter)")
        self._log_next_btn.clicked.connect(self._log_find_next)
        _find_btn_css = (
            "QPushButton { background: #ffffff; color: #475569;"
            " border: 1px solid #cbd5e1; border-radius: 4px;"
            " font-size: 12px; min-height: 0px; padding: 0; }"
            "QPushButton:hover { background: #f1f5f9; }"
        )
        self._log_prev_btn.setStyleSheet(_find_btn_css)
        self._log_next_btn.setStyleSheet(_find_btn_css)
        log_hdr_row.addWidget(self._log_prev_btn)
        log_hdr_row.addWidget(self._log_next_btn)

        self._toggle_raw_btn = QPushButton("📋  상세 로그")
        self._toggle_raw_btn.setCheckable(True)
        self._toggle_raw_btn.setFixedHeight(24)
        self._toggle_raw_btn.setStyleSheet(
            "QPushButton {"
            " background: #ffffff; color: #475569;"
            " border: 1px solid #cbd5e1; border-radius: 4px;"
            " padding: 0 10px; font-size: 11px; min-height: 0px; }"
            "QPushButton:hover { background: #f1f5f9; }"
            "QPushButton:checked {"
            " background: #eff6ff; color: #1d4ed8; border-color: #93c5fd; }"
        )
        self._toggle_raw_btn.setToolTip(
            "원본(raw) 로그 표시 — humanize 단계 이전, 내부 디버그 메시지 포함"
        )
        self._toggle_raw_btn.toggled.connect(self._toggle_raw_log)
        log_hdr_row.addWidget(self._toggle_raw_btn)
        log_lay.addLayout(log_hdr_row)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setStyleSheet(
            "QPlainTextEdit {"
            " background-color: #ffffff; color: #334155;"
            " border: none; border-radius: 4px; padding: 4px;"
            "}"
        )
        log_lay.addWidget(self._log)

        # 상세(raw) 로그 패널 — 기본 숨김, 토글로 표시
        self._raw_log = QPlainTextEdit()
        self._raw_log.setReadOnly(True)
        self._raw_log.setFont(QFont("Consolas", 8))
        self._raw_log.setStyleSheet(
            "QPlainTextEdit {"
            " background-color: #0f172a; color: #cbd5e1;"
            " border: none; border-radius: 4px; padding: 4px;"
            " selection-background-color: #1e40af; }"
        )
        self._raw_log.setVisible(False)
        log_lay.addWidget(self._raw_log)

        splitter.addWidget(log_card)

        # TC 테이블 패널 (우)
        tc_card = QFrame()
        tc_card.setStyleSheet(_CARD)
        tc_lay = QVBoxLayout(tc_card)
        tc_lay.setContentsMargins(12, 12, 12, 12)
        tc_lay.setSpacing(6)

        tc_hdr_row = QHBoxLayout()
        tc_title = QLabel("TC 목록")
        tc_title.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 15px; font-weight: 700; color: #1e293b; }"
        )
        tc_hdr_row.addWidget(tc_title)

        # 스냅샷 출처 라벨 — 과거 스냅샷 표시 중일 때 노란색 강조
        self._snapshot_lbl = QLabel("")
        self._snapshot_lbl.setStyleSheet(
            "QLabel { font-size: 11px; color: #64748b; padding: 0 6px;"
            " background: transparent; border: none; }"
        )
        tc_hdr_row.addWidget(self._snapshot_lbl)

        # "최신 상태로" 버튼 (스냅샷 보고 있을 때만 표시)
        self._latest_btn = QPushButton("↺  최신 상태")
        self._latest_btn.setFixedHeight(24)
        self._latest_btn.setVisible(False)
        self._latest_btn.setStyleSheet(
            "QPushButton { background: #fef3c7; color: #92400e;"
            " border: 1px solid #fcd34d; border-radius: 4px;"
            " padding: 0 10px; font-size: 11px; min-height: 0px; }"
            "QPushButton:hover { background: #fde68a; }"
        )
        self._latest_btn.setToolTip(
            "현재 진행 단계의 최신 TC 상태로 돌아갑니다"
        )
        self._latest_btn.clicked.connect(self._show_latest)
        tc_hdr_row.addWidget(self._latest_btn)

        tc_hdr_row.addStretch()

        # TC 목록 Excel 다운로드
        self._tc_xlsx_btn = QPushButton("⬇ Excel")
        self._tc_xlsx_btn.setFixedHeight(24)
        self._tc_xlsx_btn.setStyleSheet(
            "QPushButton { background:#0f766e; color:#ffffff; border:none;"
            " border-radius:4px; padding:0 10px; font-size:11px; font-weight:600;"
            " min-height:0px; }"
            "QPushButton:hover { background:#0d9488; }"
        )
        self._tc_xlsx_btn.setToolTip("현재 TC 목록을 Excel(.xlsx)로 저장")
        self._tc_xlsx_btn.clicked.connect(self._export_tcs_excel)
        tc_hdr_row.addWidget(self._tc_xlsx_btn)

        dbl_hint = QLabel("더블클릭 → 상세")
        dbl_hint.setStyleSheet(
            "QLabel { font-size: 10px; color: #94a3b8;"
            " background: transparent; border: none; padding: 0 4px; }"
        )
        tc_hdr_row.addWidget(dbl_hint)
        self._tc_count_lbl = QLabel("총 0건")
        self._tc_count_lbl.setStyleSheet(
            "QLabel { font-size: 11px; color: #64748b;"
            " background-color: #f8fafc; border: 1px solid #e2e8f0;"
            " border-radius: 4px; padding: 2px 8px; }"
        )
        tc_hdr_row.addWidget(self._tc_count_lbl)
        tc_lay.addLayout(tc_hdr_row)

        # 스냅샷 상태 추적: None=현재(최신), 그 외=과거 stage 번호
        self._viewing_snapshot: int | None = None
        # 최신 상태 backup (스냅샷 보기로 전환 전의 TC)
        self._latest_tcs_backup: list[dict] | None = None

        self._tc_table = QTableWidget(0, 10)
        self._tc_table.setHorizontalHeaderLabels(
            ["대분류", "중분류", "소분류", "TC ID", "시나리오",
             "입력값", "예상값", "기법", "상태", "결과"]
        )
        hdr = self._tc_table.horizontalHeader()
        # 모든 열을 사용자가 드래그로 자유롭게 조절 (Interactive) + 합리적 초기 너비
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        hdr.setStretchLastSection(False)
        for col, width in enumerate([100, 110, 140, 100, 280, 140, 160, 90, 70, 70]):
            self._tc_table.setColumnWidth(col, width)
        # 행 높이 일정하게 (긴 텍스트는 잘림, 더블클릭으로 상세 확인)
        self._tc_table.setWordWrap(False)
        self._tc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._tc_table.setStyleSheet(
            "QTableWidget { border: none; background: #ffffff; }"
            "QHeaderView::section { background-color: #f8fafc; color: #64748b;"
            " font-size: 12px; font-weight: 600; padding: 6px 8px;"
            " border: none; border-bottom: 1px solid #e2e8f0; }"
            "QTableWidget::item { border-bottom: 1px solid #f1f5f9; padding: 4px 8px; }"
        )
        # 더블클릭 → TC 통합 상세 다이얼로그
        self._tc_table.cellDoubleClicked.connect(self._on_tc_double_clicked)
        self._tc_table.setToolTip("행을 더블클릭하면 통합 상세 정보를 볼 수 있습니다")

        # 열려있는 상세 다이얼로그 추적 (비모달이라 여러 개 동시 가능)
        self._open_detail_dialogs: list = []

        tc_lay.addWidget(self._tc_table)
        splitter.addWidget(tc_card)

        splitter.setSizes([360, 720])
        root.addWidget(splitter, 1)

        # ── 하단 바 ───────────────────────────────────────────────────────────
        bot_card = QFrame()
        bot_card.setStyleSheet(_CARD)
        bot_card.setFixedHeight(52)
        bot_lay = QHBoxLayout(bot_card)
        bot_lay.setContentsMargins(16, 0, 16, 0)
        bot_lay.setSpacing(12)

        # 왼쪽: 상태 인디케이터 (점 + 텍스트) + 회전 스피너 + 경과시간
        self._dot = QLabel()
        self._dot.setFixedSize(8, 8)
        self._dot.setStyleSheet(
            "QLabel { border-radius: 4px; border: none; background: #cbd5e1; }"
        )
        self._status_lbl = QLabel("대기 중")
        self._status_lbl.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 13px; font-weight: 600; color: #334155; }"
        )
        # 회전 스피너 (실행 중에만 표시) — 유니코드 ⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏ 회전
        self._spinner_lbl = QLabel("")
        self._spinner_lbl.setFixedWidth(18)
        self._spinner_lbl.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 14px; color: #3b82f6; font-weight: 700; }"
        )
        # 경과시간 라벨
        self._elapsed_lbl = QLabel("")
        self._elapsed_lbl.setStyleSheet(
            "QLabel { background: transparent; border: none;"
            " font-size: 12px; color: #64748b; font-family: Consolas, monospace; }"
        )
        bot_lay.addWidget(self._dot)
        bot_lay.addWidget(self._status_lbl)
        bot_lay.addWidget(self._spinner_lbl)
        bot_lay.addWidget(self._elapsed_lbl)
        bot_lay.addStretch()

        # 스피너·경과시간 타이머 (실행 중에만 활성)
        from PySide6.QtCore import QTimer
        self._spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_idx    = 0
        self._spinner_timer  = QTimer(self)
        self._spinner_timer.setInterval(120)
        self._spinner_timer.timeout.connect(self._tick_spinner)
        self._elapsed_start: float | None = None

        # ── 자동 실행 옵션 (Stage 5 실행 직전까지 자유롭게 변경 가능) ──────────
        # 마법사 Step 3에서 정한 기본값을 여기서 덮어쓸 수 있음.
        # 브라우저 특성상 헤드리스/헤드풀은 실행 시작 시점에 고정되므로
        # "Stage 5~7 실행"을 누르기 직전까지 변경 가능 (실행 도중 변경은 불가).
        self._headless_cb = QCheckBox("브라우저 표시")
        self._headless_cb.setChecked(not self._config.headless_exec)
        self._headless_cb.setVisible(False)
        self._headless_cb.setToolTip(
            "체크: Stage 5 실행 시 별도 Chromium 창에서 동작이 보임 (사용자 마우스/키보드와 분리)\n"
            "해제: 백그라운드 헤드리스 — 빠름\n"
            "※ 실행 시작 직전까지 변경 가능 (실행 도중에는 변경되지 않음)"
        )
        self._headless_cb.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #475569; }"
        )
        self._headless_cb.toggled.connect(self._on_headless_toggled)
        bot_lay.addWidget(self._headless_cb)

        # Stage 5~7 대기/실행 버튼 (Stage 3 완료 후 표시)
        self._exec_btn = QPushButton("Stage 5~7 대기")
        self._exec_btn.setEnabled(False)
        self._exec_btn.setVisible(False)
        self._exec_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #ffffff; color: #3b82f6;"
            " border: 1px solid #3b82f6; border-radius: 6px;"
            " padding: 6px 16px; font-size: 13px; font-weight: 600; }"
            "QPushButton:enabled {"
            " background-color: #3b82f6; color: #ffffff; }"
            "QPushButton:enabled:hover { background-color: #2563eb; }"
        )
        self._exec_btn.clicked.connect(self._start_post_gate)
        bot_lay.addWidget(self._exec_btn)

        # ── 일시정지·중단 버튼 (Stage 5 실행 중에만 표시) ───────────────────
        self._pause_btn = QPushButton("⏸  일시정지")
        self._pause_btn.setCheckable(True)
        self._pause_btn.setVisible(False)
        self._pause_btn.setStyleSheet(
            "QPushButton {"
            " background: #fef9c3; color: #854d0e;"
            " border: 1px solid #fde047; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #fef08a; }"
            "QPushButton:checked {"
            " background: #16a34a; color: #ffffff; border-color: #16a34a; }"
        )
        self._pause_btn.setToolTip(
            "다음 TC 실행 전 일시정지합니다 (현재 TC는 완료 후 정지)"
        )
        self._pause_btn.toggled.connect(self._toggle_pause)
        bot_lay.addWidget(self._pause_btn)

        self._stop_btn = QPushButton("⏹  중단")
        self._stop_btn.setVisible(False)
        self._stop_btn.setStyleSheet(
            "QPushButton {"
            " background: #ffffff; color: #dc2626;"
            " border: 1px solid #fca5a5; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #fee2e2; }"
        )
        self._stop_btn.setToolTip(
            "다음 TC 실행을 건너뛰고 즉시 종료합니다 (현재 TC 완료 후 정지)"
        )
        self._stop_btn.clicked.connect(self._request_stop)
        bot_lay.addWidget(self._stop_btn)

        # Stage 1~3 실행 버튼 (초기 상태)
        self._run_btn = QPushButton("Stage 1~3 실행")
        self._run_btn.setStyleSheet(
            pill_btn(bg="#1a7a3c", bg_hover="#15803d", bg_pressed="#0f6030",
                     bg_disabled="#86efac", fg_disabled="#ffffff")
        )
        self._run_btn.clicked.connect(self._start_pre_gate)
        bot_lay.addWidget(self._run_btn)

        # 실행 정보 (설정·수집 요소 조회/수정)
        self._info_btn = QPushButton("📋 실행 정보")
        self._info_btn.setToolTip("이 실행의 설정값과 수집한 페이지 요소를 조회/수정합니다.")
        self._info_btn.setStyleSheet(
            "QPushButton { background-color:#475569; color:#ffffff; border:none;"
            " border-radius:6px; padding:6px 14px; font-size:12px; font-weight:600; }"
            "QPushButton:hover { background-color:#334155; }"
        )
        self._info_btn.clicked.connect(self._open_run_info)
        bot_lay.addWidget(self._info_btn)

        # 기능목록 Excel 다운로드 버튼 (Stage 0 실행 후 Stage 3 완료 시 표시)
        self._feature_dl_btn = QPushButton("⬇ 기능목록 Excel")
        self._feature_dl_btn.setVisible(False)
        self._feature_dl_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #0f766e; color: #ffffff;"
            " border: none; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #0d9488; }"
        )
        self._feature_dl_btn.clicked.connect(self._export_features)
        bot_lay.addWidget(self._feature_dl_btn)

        # 기능목록 CSV 다운로드 (자체 추출 — 대/중/소 분류)
        self._feature_csv_btn = QPushButton("⬇ 기능목록 CSV")
        self._feature_csv_btn.setVisible(False)
        self._feature_csv_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #14b8a6; color: #ffffff;"
            " border: none; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #0d9488; }"
        )
        self._feature_csv_btn.setToolTip(
            "프로그램이 자체적으로 추출한 기능 리스트(대/중/소 분류) CSV 다운로드"
        )
        self._feature_csv_btn.clicked.connect(self._export_features_csv)
        bot_lay.addWidget(self._feature_csv_btn)

        # 완료 후 결과 열기 버튼들 (Stage 7 완료 시 표시)
        self._open_report_btn = QPushButton("📊 보고서 열기")
        self._open_report_btn.setVisible(False)
        self._open_report_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #16a34a; color: #ffffff;"
            " border: none; border-radius: 6px;"
            " padding: 6px 14px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #15803d; }"
        )
        self._open_report_btn.setToolTip("tc_final.xlsx 보고서를 엽니다")
        self._open_report_btn.clicked.connect(self._open_final_report)
        bot_lay.addWidget(self._open_report_btn)

        self._open_folder_btn = QPushButton("📁 결과 폴더")
        self._open_folder_btn.setVisible(False)
        self._open_folder_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #ffffff; color: #475569;"
            " border: 1px solid #cbd5e1; border-radius: 6px;"
            " padding: 6px 12px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #f1f5f9; color: #1e293b; }"
        )
        self._open_folder_btn.setToolTip("실행 결과 폴더를 탐색기로 엽니다")
        self._open_folder_btn.clicked.connect(self._open_run_folder)
        bot_lay.addWidget(self._open_folder_btn)

        # 스크린샷 폴더 열기 버튼
        self._screenshot_dir_btn = QPushButton("📂 스크린샷 폴더")
        self._screenshot_dir_btn.setVisible(False)
        self._screenshot_dir_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #ffffff; color: #475569;"
            " border: 1px solid #cbd5e1; border-radius: 6px;"
            " padding: 6px 12px; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background-color: #f1f5f9; color: #1e293b; }"
        )
        self._screenshot_dir_btn.setToolTip(
            "Stage 0 DOM 스캔 시 자동 저장된 페이지 스크린샷 폴더를 엽니다"
        )
        self._screenshot_dir_btn.clicked.connect(self._open_screenshot_dir)
        bot_lay.addWidget(self._screenshot_dir_btn)

        # Stage 4 Reviewer Gate 버튼 (Stage 3 완료 후 표시)
        self._gate_btn = QPushButton("Stage 4: Reviewer Gate 실행")
        self._gate_btn.setEnabled(False)
        self._gate_btn.setVisible(False)
        self._gate_btn.setStyleSheet(
            "QPushButton {"
            " background-color: #3b82f6; color: #ffffff;"
            " border: 1px solid #3b82f6; border-radius: 6px;"
            " padding: 6px 16px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background-color: #2563eb; }"
            "QPushButton:disabled { background-color: #93c5fd; border-color: #93c5fd; }"
        )
        self._gate_btn.clicked.connect(self._open_gate)
        bot_lay.addWidget(self._gate_btn)

        root.addWidget(bot_card)
        self.setStatusBar(QStatusBar())
        self.statusBar().hide()

    # ── Stage 진행 표시기 ─────────────────────────────────────────────────────
    def _update_circles(self, progress: int, badge: str = "") -> None:
        """progress = 현재 활성 stage 번호(1~7). 1..progress-1=완료, progress=활성, 이후=대기."""
        # 진행한 최대 stage 번호 기록 (클릭 이동 시 허용 범위 결정에 사용)
        if progress > self._max_progress:
            self._max_progress = progress
        for i, circle in enumerate(self._circles):
            n = i + 1
            if n < progress:
                circle.setStyleSheet(_CIRCLE_DONE)
            elif n == progress:
                circle.setStyleSheet(_CIRCLE_CURRENT)
            else:
                circle.setStyleSheet(_CIRCLE_FUTURE)
            # 진행한 단계는 손가락 커서, 미래는 기본 커서
            circle.setCursor(Qt.PointingHandCursor if n <= self._max_progress else Qt.ArrowCursor)
        for i, line in enumerate(self._lines):
            line.setStyleSheet(_LINE_DONE if (i + 1) < progress else _LINE_PENDING)
        if badge:
            self._stage_badge.setText(badge)

    # ── Stage 원 클릭 — 과거 / 현재 단계로 이동 ─────────────────────────────
    def _on_stage_circle_clicked(self, stage_num: int) -> None:
        """클릭한 stage의 TC 스냅샷을 테이블에 표시. 진행 안 한 단계는 무시."""
        if stage_num > self._max_progress:
            self._append_log(f"Stage {stage_num}은 아직 진행되지 않았습니다.")
            return

        # 현재 진행 단계를 클릭한 경우 → 최신 상태로 복귀
        if stage_num == self._max_progress and self._viewing_snapshot is not None:
            self._show_latest()
            return

        # stage → JSON 파일 매핑
        snapshot_map = {
            2: ("tc_raw.json",      "Stage 2 (TC 설계 직후)"),
            3: ("tc_verified.json", "Stage 3 (V1~V5 검증 완료)"),
            4: ("tc_gated.json",    "Stage 4 (Reviewer Gate 반영)"),
            5: ("tc_executed.json", "Stage 5 (자동 실행 완료)"),
            6: ("tc_executed.json", "Stage 6 (실패 원인 분석)"),
            7: ("tc_executed.json", "Stage 7 (최종 Excel)"),
        }
        if stage_num == 1:
            self._append_log("Stage 1은 파일 파싱 단계라 TC 스냅샷이 없습니다.")
            return

        fname, label = snapshot_map.get(stage_num, (None, ""))
        path = self._orch.run_dir / fname if fname else None
        if not path or not path.exists():
            self._append_log(f"⚠ {label} 스냅샷 파일 없음 — 표시할 데이터가 없습니다.")
            return

        try:
            import json as _json
            tcs = _json.loads(path.read_text(encoding="utf-8"))

            # 최신 상태가 아직 백업되지 않았으면 백업
            if self._viewing_snapshot is None:
                self._latest_tcs_backup = list(self._tcs)

            self._tcs = tcs
            self._viewing_snapshot = stage_num
            self._refresh_tc_table()
            self._update_snapshot_indicator(stage_num, label, fname)
            self._append_log(f"📂 {label} 스냅샷 표시 — TC {len(tcs)}개 ({fname})")
        except Exception as e:
            self._append_log(f"⚠ 스냅샷 로드 실패: {e}")

    def _show_latest(self) -> None:
        """과거 스냅샷 → 최신 진행 상태로 복귀."""
        if self._viewing_snapshot is None:
            return
        if self._latest_tcs_backup is not None:
            self._tcs = self._latest_tcs_backup
            self._latest_tcs_backup = None
        self._viewing_snapshot = None
        self._refresh_tc_table()
        self._update_snapshot_indicator(None, "", "")
        self._append_log("↺  최신 상태로 복귀")

    def _update_snapshot_indicator(
        self, stage_num: int | None, label: str, fname: str
    ) -> None:
        """스냅샷 라벨·테이블 배경·버튼 가시성 갱신."""
        if stage_num is None:
            self._snapshot_lbl.setText("")
            self._snapshot_lbl.setStyleSheet(
                "QLabel { font-size: 11px; color: #64748b; padding: 0 6px;"
                " background: transparent; border: none; }"
            )
            self._latest_btn.setVisible(False)
            self._tc_table.setStyleSheet(
                self._tc_table.styleSheet().replace(
                    "background: #fffbeb;", "background: #ffffff;"
                )
            )
        else:
            self._snapshot_lbl.setText(f"📂  {label} 보는 중 ({fname})")
            self._snapshot_lbl.setStyleSheet(
                "QLabel { font-size: 11px; color: #92400e;"
                " background: #fef3c7; border: 1px solid #fcd34d;"
                " border-radius: 4px; padding: 2px 8px; font-weight: 600; }"
            )
            self._latest_btn.setVisible(True)

    def _set_status(self, text: str, active: bool = False, running: bool | None = None) -> None:
        """상태 표시 갱신.

        active : True면 점이 녹색(완료/실행중), False면 회색(대기)
        running: True/None  → 실행 중(스피너 + 경과시간 ON)
                 False      → 정지/완료(스피너 OFF, 경과시간 멈춤)
        """
        color = "#22c55e" if active else "#cbd5e1"
        self._dot.setStyleSheet(
            f"QLabel {{ border-radius: 4px; border: none; background: {color}; }}"
        )
        self._status_lbl.setText(text)

        # 윈도우 타이틀에도 상태 반영 → 작업표시줄에서 진행 상태 보임
        run_id = self._config.run_id
        self.setWindowTitle(f"AWT — {run_id}  ·  {text}")

        # running 추론: 텍스트에 "중" 포함 또는 명시적 True
        if running is None:
            running = ("중" in text) and not ("완료" in text)
        if running:
            self._start_spinner()
        else:
            self._stop_spinner()

    # ── 스피너 / 경과시간 ─────────────────────────────────────────────────────
    def _start_spinner(self) -> None:
        import time as _t
        if self._elapsed_start is None:
            self._elapsed_start = _t.time()
        if not self._spinner_timer.isActive():
            self._spinner_timer.start()

    def _stop_spinner(self) -> None:
        if self._spinner_timer.isActive():
            self._spinner_timer.stop()
        self._spinner_lbl.setText("")
        # 경과시간은 마지막 값으로 고정 (지우지 않음)
        if self._elapsed_start is not None:
            self._update_elapsed_text()
        self._elapsed_start = None

    def _tick_spinner(self) -> None:
        import time as _t
        # 스피너 프레임
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
        self._spinner_lbl.setText(self._spinner_frames[self._spinner_idx])
        # 경과시간
        if self._elapsed_start is not None:
            self._update_elapsed_text()

    def _update_elapsed_text(self) -> None:
        import time as _t
        if self._elapsed_start is None:
            return
        secs = int(_t.time() - self._elapsed_start)
        h, rem = divmod(secs, 3600)
        m, s   = divmod(rem, 60)
        if h > 0:
            self._elapsed_lbl.setText(f"⏱  {h}:{m:02d}:{s:02d}")
        else:
            self._elapsed_lbl.setText(f"⏱  {m:02d}:{s:02d}")

    # ── Stage 1~3 (Pre-Gate) ─────────────────────────────────────────────────
    def _start_pre_gate(self) -> None:
        # ── 페이지 선택 다이얼로그 (Stage 0 BFS 수행 + URL 선택) ──────────
        # Stage 0 DOM 스캔 건너뜀 옵션이 켜져 있으면 다이얼로그 생략 (파일만 사용)
        from app.ui.page_picker import PagePickerDialog

        skip_stage0 = (
            not self._config.target_url
            or self._config.target_url.lower().startswith("file://")
        )

        # ── 원클릭 자동 진행 (auto_pages): 페이지 선택·재사용 프롬프트 생략 ────
        # 새 BFS 스캔으로 바로 진행 → D51 전역dedup·D52 한글 생성 적용.
        reuse_stage0 = False
        auto_pages = bool(getattr(self._config, "auto_pages", True))
        if auto_pages and not skip_stage0:
            self._config.selected_urls = None     # BFS 전체 자동
            self._config.cached_features = None   # 캐시 미사용 — 새로 스캔(한글·dedup 적용)
            self._config.selected_url_groups = {}
            self._append_log(
                f"페이지 자동 수집(BFS, 최대 {self._config.max_pages or 30}개) — 새로 스캔합니다."
            )
            self._begin_pre_worker(reuse_stage0=False)
            return

        # ── (수동 모드) 기존 Stage 0 분석 결과가 있으면 재사용 여부 확인 ──────
        # (이력에서 다시 연 run 등 — 페이지 재수집·재스캔 없이 바로 Stage 1~3)
        if not skip_stage0 and self._orch.has_stage0_draft():
            res = QMessageBox.question(
                self, "기존 분석 결과 발견",
                "이 실행에는 이미 완료된 웹사이트 분석 결과(Stage 0)가 있습니다.\n\n"
                "  • [Yes] 기존 결과 재사용 — 페이지 재수집·재분석 없이 바로 Stage 1~3 진행 (빠름)\n"
                "  • [No]  새로 분석 — 페이지를 다시 수집·선택 (사이트가 변경된 경우)\n",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if res == QMessageBox.Yes:
                reuse_stage0 = True
                skip_stage0 = True   # picker 생략
                self._append_log("♻ 기존 Stage 0 분석 결과를 재사용합니다 (페이지 재수집 생략).")

        if not skip_stage0:
            picker = PagePickerDialog(
                start_url=self._config.target_url,
                auth_sequence=self._config.auth_sequence or None,
                exclude_run_id=self._config.run_id,
                default_max_pages=self._config.max_pages or 30,
                parent=self,
            )
            if picker.exec() != QDialog.Accepted:
                # 사용자가 취소 → 실행 안 함
                self._append_log("페이지 선택이 취소되었습니다. 실행을 시작하지 않습니다.")
                return
            # 선택 결과를 config에 반영
            self._config.selected_urls      = picker.selected_urls
            self._config.cached_features    = picker.selected_cache
            self._config.selected_url_groups = picker.selected_groups

            n_sel   = len(picker.selected_urls)
            n_cache = len(picker.selected_cache)
            n_llm   = n_sel - n_cache
            n_merged = sum(len(v) for v in picker.selected_groups.values())
            msg = (
                f"페이지 선택 완료 — 분석할 페이지 {n_sel}개 "
                f"(♻ 캐시 재사용 {n_cache}개 + 🆕 LLM 분석 {n_llm}개)"
            )
            if n_merged > 0:
                msg += f"\n      🧹 동형 페이지 {n_merged}개는 대표로 묶여 제외됨 (추적성: meta.json 기록)"
            self._append_log(msg)

        self._begin_pre_worker(reuse_stage0=reuse_stage0)

    def _begin_pre_worker(self, reuse_stage0: bool = False) -> None:
        """Stage 1~3 워커 시작 (자동/수동 공통 진입점)."""
        self._run_btn.setEnabled(False)
        # (페이지 선택 진행 로그를 보존하기 위해 self._log.clear() 호출하지 않음)
        self._update_circles(1, "Stage 1~3 실행 중")
        self._set_status("Stage 1~3 실행 중")
        self._append_log("Stage 1~3 시작...")

        # Stage 1~3 중단 버튼 노출 + 플래그 리셋
        self._orch.set_stopped(False)
        self._stop_btn.setText("⏹  중단")
        self._stop_btn.setEnabled(True)
        self._stop_btn.setVisible(True)

        gate_on = bool(getattr(self._config, "feature_gate", False))
        self._pre_worker = _PreGateWorker(
            orch=self._orch,
            has_files=bool(self._config.input_files),
            reuse_stage0=reuse_stage0,
            stop_after_ingest=gate_on,   # D53 — 게이트 켜면 Stage 1 후 정지
        )
        self._pre_worker.stage_done.connect(self._on_pre_stage_done)
        self._pre_worker.finished.connect(self._on_pre_gate_done)
        self._pre_worker.stopped.connect(self._on_pre_gate_stopped)
        self._pre_worker.error.connect(self._on_error)
        if gate_on:
            self._pre_worker.ingest_ready.connect(self._on_ingest_ready)
        self._pre_worker.start()

    # ── D53 기능 확정 게이트 ──────────────────────────────────────────────────
    def _on_ingest_ready(self, leaves: list) -> None:
        """Stage 1 완료 → 기능 확정 게이트 표시 → Stage 2~3 재개."""
        from app.ui.feature_gate import FeatureGate
        n_before = len(leaves)
        excluded = 0
        if leaves:
            dlg = FeatureGate(leaves, parent=self)
            if dlg.exec() == QDialog.Accepted:
                # 확정된 leaf만 Stage 2 대상으로 반영
                if self._orch.ingest_result is not None:
                    self._orch.ingest_result["leaves"] = dlg.kept_leaves
                excluded = dlg.excluded_count
                # 추적성 기록
                self._orch.ingest_result.setdefault("feature_gate", {})
                self._orch.ingest_result["feature_gate"] = {
                    "shown": True,
                    "leaves_before": n_before,
                    "leaves_after": len(dlg.kept_leaves),
                    "excluded": excluded,
                    "domain_budgets": dlg.domain_budgets,   # 도메인 예산 적용 결과
                }
                if dlg.domain_budgets:
                    trimmed = sum(r["checked"] - r["kept"]
                                  for r in dlg.domain_budgets.values())
                    self._append_log(
                        f"📊 도메인 예산 적용 — {len(dlg.domain_budgets)}개 도메인에서 "
                        f"{trimmed}개 기능을 대표 우선으로 제한."
                    )
            else:
                self._append_log("기능 확정 게이트 취소 — 전체 기능으로 진행합니다.")
        if excluded:
            self._append_log(
                f"기능 확정 — {n_before}개 중 {excluded}개 제외, "
                f"{n_before - excluded}개로 TC 설계 진행."
            )
        else:
            self._append_log(f"기능 확정 — 전체 {n_before}개 기능으로 TC 설계 진행.")

        # Stage 2~3 재개 (새 worker) — resume 모드라 stage0/1·reuse_stage0 무관
        self._pre_worker = _PreGateWorker(
            orch=self._orch,
            has_files=bool(self._config.input_files),
            resume_from_stage2=True,
        )
        self._pre_worker.stage_done.connect(self._on_pre_stage_done)
        self._pre_worker.finished.connect(self._on_pre_gate_done)
        self._pre_worker.stopped.connect(self._on_pre_gate_stopped)
        self._pre_worker.error.connect(self._on_error)
        self._pre_worker.start()

    def _on_pre_gate_stopped(self, partial_tcs: list) -> None:
        """Stage 1~3 사용자 중단 — 부분 TC가 있으면 보존하고 Gate 진행 가능."""
        self._stop_btn.setVisible(False)
        self._pause_btn.setVisible(False)
        self._set_status("Stage 1~3 중단됨", active=False, running=False)
        if partial_tcs:
            self._tcs = partial_tcs
            self._orch.tcs = partial_tcs
            self._refresh_tc_table()
            self._append_log(
                f"⏹ 중단됨 — 지금까지 설계된 TC {len(partial_tcs)}개를 보존했습니다. "
                f"Reviewer Gate로 진행하거나 다시 실행할 수 있습니다."
            )
            self._run_btn.setVisible(False)
            self._gate_btn.setVisible(True)
            self._gate_btn.setEnabled(True)
            self._exec_btn.setVisible(True)
            self._exec_btn.setEnabled(False)
        else:
            self._append_log("⏹ 중단됨 — 설계된 TC가 없습니다. 다시 실행하세요.")
            self._run_btn.setVisible(True)
            self._run_btn.setEnabled(True)

    def _on_pre_stage_done(self, n: int) -> None:
        """stage_done emit: n = 현재 진입한 단계 (1~4)."""
        badges = {1: "Stage 2 실행 중", 2: "Stage 3 실행 중",
                  3: "Stage 3 검증 중", 4: "Stage 4 실행 중"}
        self._update_circles(n, badges.get(n, f"Stage {n} 진행 중"))

    def _on_pre_gate_done(self, tcs: list) -> None:
        self._tcs = tcs
        # Stage 1~3 정상 완료 → 중단 버튼 숨김
        self._stop_btn.setVisible(False)
        # 진행이 갱신됐으므로 스냅샷 상태 초기화
        self._viewing_snapshot = None
        self._latest_tcs_backup = None
        self._update_snapshot_indicator(None, "", "")
        self._refresh_tc_table()
        # 버튼 전환: 실행 버튼 숨기고 Gate + 5~7대기 표시
        self._run_btn.setVisible(False)
        self._exec_btn.setVisible(True)
        self._exec_btn.setEnabled(False)
        self._headless_cb.setVisible(True)   # 자동 실행 옵션 노출
        self._gate_btn.setVisible(True)
        self._gate_btn.setEnabled(True)
        # Stage 0 스캔 결과 있으면 기능목록(Excel/CSV) + 스크린샷 폴더 버튼 표시
        feature_draft   = self._orch.run_dir / "dom-scan" / "feature-spec-draft.json"
        screenshots_dir = self._orch.run_dir / "dom-scan" / "screenshots"
        has_draft = feature_draft.exists()
        self._feature_dl_btn.setVisible(has_draft)
        self._feature_csv_btn.setVisible(has_draft)
        self._screenshot_dir_btn.setVisible(screenshots_dir.exists())
        self._write_meta("stage3_done")
        self._set_status(f"Stage 3 완료  |  TC {len(tcs)}개", active=True)
        self._append_log(f"Stage 3 완료 - TC {len(tcs)}개. Reviewer Gate를 진행하세요.")
        # 시험 커버리지 요약 표시
        cov = self._compute_coverage()
        if cov:
            self._append_log(
                f"📊 시험 커버리지 — 고유 기능 {cov['total_unique_features']}개 중 "
                f"{cov['designed_features']}개 설계 ({cov['coverage_pct']}%) · TC {cov['total_tcs']}개"
            )
        # 사용자 검토 대기 — 알림으로 인지
        self._notify(
            "AWT — 검토가 필요합니다",
            f"TC {len(tcs)}개 설계 완료. Reviewer Gate를 진행하세요.",
        )

    # ── Stage 4 Gate ─────────────────────────────────────────────────────────
    def _open_gate(self) -> None:
        self.gate_review_requested.emit(self._tcs)

    def apply_gate(self, decisions: dict) -> None:
        """ReviewerGate 결정 완료 시 main.py에서 호출."""
        self._tcs = self._orch.apply_gate_decisions(decisions)
        self._refresh_tc_table()
        self._gate_btn.setVisible(False)
        self._exec_btn.setEnabled(True)
        self._exec_btn.setText("Stage 5~7 실행")
        self._update_circles(5, "Stage 5 대기 중")
        self._set_status(f"Stage 4 완료  |  TC {len(self._tcs)}개", active=True)
        self._write_meta("stage4_done")
        self._append_log("Gate 결정 반영 완료. Stage 5~7을 실행하세요.")

    # ── Stage 5~7 (Post-Gate) ─────────────────────────────────────────────────
    def _start_post_gate(self) -> None:
        self._exec_btn.setEnabled(False)
        # 실행이 시작되면 브라우저 모드는 더 이상 못 바꿈 → 체크박스 잠금
        self._headless_cb.setEnabled(False)
        mode = "브라우저 표시(헤드풀)" if not self._config.headless_exec else "백그라운드(헤드리스)"
        self._update_circles(5, "Stage 5~7 실행 중")
        self._set_status("Stage 5~7 실행 중")
        self._append_log(f"Stage 5~7 시작... (자동 실행 모드: {mode})")

        # 일시정지/중단 버튼 노출 + 플래그 리셋
        self._orch.set_paused(False)
        self._orch.set_stopped(False)
        self._pause_btn.setChecked(False)
        self._pause_btn.setText("⏸  일시정지")
        self._pause_btn.setVisible(True)
        self._stop_btn.setVisible(True)

        self._post_worker = _PostGateWorker(orch=self._orch)
        self._post_worker.stage_done.connect(self._on_post_stage_done)
        self._post_worker.finished.connect(self._on_post_gate_done)
        self._post_worker.error.connect(self._on_error)
        self._post_worker.defects_found.connect(self._on_defects_found)
        self._post_worker.start()

    # ── 자동 실행 옵션 토글 ───────────────────────────────────────────────
    def _on_headless_toggled(self, show_browser: bool) -> None:
        """브라우저 표시 체크박스 → config.headless_exec 갱신 (Stage 5 시작 시 반영)."""
        self._config.headless_exec = not show_browser
        mode = "브라우저 표시(헤드풀)" if show_browser else "백그라운드(헤드리스)"
        self._append_log(f"⚙ 자동 실행 모드 변경: {mode} (다음 Stage 5 실행부터 적용)")

    # ── 일시정지 / 중단 ───────────────────────────────────────────────────
    def _toggle_pause(self, paused: bool) -> None:
        self._orch.set_paused(paused)
        if paused:
            self._pause_btn.setText("▶  재개")
            self._append_log("⏸  일시정지 요청 — 현재 TC 완료 후 정지")
        else:
            self._pause_btn.setText("⏸  일시정지")
            self._append_log("▶  재개 요청 — 다음 TC부터 진행")

    def _request_stop(self) -> None:
        from PySide6.QtWidgets import QMessageBox as _MB
        # 현재 실행 중인 단계 판별 (pre-gate=Stage 1~3, post-gate=Stage 5~7)
        pre_running  = self._pre_worker is not None and self._pre_worker.isRunning()
        unit = "현재 항목(페이지/기능) 완료 후 Stage 1~3" if pre_running else "현재 TC 완료 후 Stage 5"
        res = _MB.question(
            self, "중단 확인",
            f"{unit} 실행을 중단합니다.\n"
            "지금까지 처리된 결과는 보존됩니다. 계속하시겠습니까?",
            _MB.Yes | _MB.No, _MB.No,
        )
        if res != _MB.Yes:
            return
        self._orch.set_stopped(True)
        # 일시정지 상태였으면 풀어서 즉시 중단되도록
        if self._orch.is_paused():
            self._orch.set_paused(False)
        self._pause_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._append_log("⏹  중단 요청 — 현재 항목 완료 후 종료합니다")

    def _on_post_stage_done(self, n: int) -> None:
        """stage_done emit: n = 방금 완료된 단계(5~7). n+1이 다음 활성."""
        badges = {5: "Stage 6 실행 중", 6: "Stage 7 실행 중", 7: "모든 단계 완료"}
        self._update_circles(n + 1, badges.get(n, ""))
        # Stage 5 완료 후에는 일시정지/중단/자동실행옵션 더 이상 의미 없음 → 숨김
        if n >= 5:
            self._pause_btn.setVisible(False)
            self._stop_btn.setVisible(False)
            self._headless_cb.setVisible(False)

    def _on_defects_found(self, count: int) -> None:
        """Stage 6B 완료 — 결함 카탈로그 신규 항목 알림."""
        if count == 0:
            return
        self._append_log(
            f"📋 결함 카탈로그 {count}건 추가 (data/assets/defect-catalog/)"
            " — 패턴 승인은 검수자가 직접 확인 필요"
        )
        if self._tray and self._tray.isSystemTrayAvailable():
            self._tray.showMessage(
                "AWT — 결함 카탈로그",
                f"신규 결함 {count}건이 카탈로그에 추가됐습니다.\n패턴 후보를 검토해주세요.",
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _on_post_gate_done(self, out: Path) -> None:
        self._tcs = self._orch.tcs
        self._refresh_tc_table()
        self._write_meta("done")
        self._append_log(f"완료 → {out}")
        self._final_report_path = out

        passed = sum(1 for tc in self._tcs if tc.get("result") == "pass")
        failed = sum(1 for tc in self._tcs if tc.get("result") == "fail")
        total  = len(self._tcs)
        self._set_status(
            f"완료  |  통과 {passed}  실패 {failed}  /  총 {total}개", active=True
        )

        # 완료 후 결과 버튼 표시
        self._open_report_btn.setVisible(True)
        self._open_folder_btn.setVisible(True)

        # 시스템 트레이 알림
        self._notify(
            "AWT 실행 완료",
            f"총 {total}개  ·  통과 {passed} / 실패 {failed}",
            icon_type="warning" if failed > 0 else "info",
        )

        # 완료 팝업 — 보고서 바로 열기 버튼 포함
        run_dir = self._orch.run_dir
        screenshots_dir = run_dir / "dom-scan" / "screenshots"
        screenshot_info = (
            f"\n📷 스크린샷 : {screenshots_dir}" if screenshots_dir.exists() else ""
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("실행 완료")
        msg.setIcon(QMessageBox.Information)
        msg.setText(
            f"<b>모든 단계가 완료되었습니다.</b><br><br>"
            f"총 {total}개 &nbsp;·&nbsp; "
            f"<span style='color:#16a34a'>PASS {passed}</span> &nbsp;/&nbsp; "
            f"<span style='color:#dc2626'>FAIL {failed}</span>"
        )
        msg.setInformativeText(
            f"📊 보고서 : {out}"
            f"\n📁 결과 폴더 : {run_dir}"
            f"{screenshot_info}"
        )
        open_btn  = msg.addButton("📊 보고서 열기", QMessageBox.AcceptRole)
        folder_btn = msg.addButton("📁 폴더 열기",  QMessageBox.ActionRole)
        msg.addButton("닫기", QMessageBox.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == open_btn:
            self._open_final_report()
        elif clicked == folder_btn:
            self._open_run_folder()

    # ── 완료 후 결과 열기 ─────────────────────────────────────────────────────
    def _open_final_report(self) -> None:
        """tc_final.xlsx를 기본 프로그램으로 엽니다."""
        import subprocess
        path = getattr(self, "_final_report_path", None) or (
            self._orch.run_dir / "tc_final.xlsx"
        )
        if not path.exists():
            QMessageBox.warning(self, "파일 없음", f"보고서 파일을 찾을 수 없습니다:\n{path}")
            return
        subprocess.Popen(["explorer", str(path)])

    def _open_run_folder(self) -> None:
        """실행 결과 폴더를 탐색기로 엽니다."""
        import subprocess
        folder = self._orch.run_dir
        if not folder.exists():
            QMessageBox.warning(self, "폴더 없음", f"결과 폴더를 찾을 수 없습니다:\n{folder}")
            return
        subprocess.Popen(["explorer", str(folder)])

    # ── 기능목록 CSV 다운로드 ─────────────────────────────────────────────────
    def _export_features_csv(self) -> None:
        """Stage 0 자체 추출 기능 목록을 CSV(대/중/소 분류)로 저장."""
        draft_path = self._orch.run_dir / "dom-scan" / "feature-spec-draft.json"
        if not draft_path.exists():
            QMessageBox.warning(self, "알림", "Stage 0 DOM 스캔 결과가 없습니다.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "기능 목록 CSV 저장",
            f"feature_list_{self._config.run_id}.csv",
            "CSV 파일 (*.csv);;모든 파일 (*.*)",
        )
        if not save_path:
            return

        try:
            import csv as _csv
            draft = json.loads(draft_path.read_text(encoding="utf-8"))
            features = draft.get("features", [])
            if not features:
                QMessageBox.information(self, "알림", "추출된 기능이 없습니다.")
                return
            # utf-8-sig: Excel에서 한글 깨지지 않도록 BOM 포함
            with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = _csv.writer(f)
                writer.writerow([
                    "대분류", "중분류", "소분류",
                    "요구사항 ID", "신뢰도", "출처 URL", "스크린샷",
                ])
                for ft in features:
                    writer.writerow([
                        ft.get("category_major", ""),
                        ft.get("category_mid", ""),
                        ft.get("category_leaf", ""),
                        ft.get("requirement_id", ""),
                        ft.get("confidence", ""),
                        ft.get("source_url", ""),
                        ft.get("screenshot_file", ""),
                    ])
            QMessageBox.information(
                self, "저장 완료",
                f"기능 목록 {len(features)}개를 CSV로 저장했습니다:\n{save_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ── 스크린샷 폴더 열기 ────────────────────────────────────────────────────
    def _open_screenshot_dir(self) -> None:
        """Stage 0 스크린샷 폴더를 OS 파일 탐색기로 연다."""
        path = self._orch.run_dir / "dom-scan" / "screenshots"
        if not path.exists():
            QMessageBox.warning(
                self, "알림",
                "스크린샷 폴더가 아직 생성되지 않았습니다.\n(Stage 0 DOM 스캔이 필요합니다.)"
            )
            return
        try:
            import os as _os, sys as _sys, subprocess as _sp
            abspath = str(path.resolve())
            if _sys.platform == "win32":
                _os.startfile(abspath)
            elif _sys.platform == "darwin":
                _sp.run(["open", abspath])
            else:
                _sp.run(["xdg-open", abspath])
        except Exception as e:
            QMessageBox.critical(self, "폴더 열기 실패", str(e))

    # ── 기능목록 Excel 다운로드 ───────────────────────────────────────────────
    def _export_features(self) -> None:
        """Stage 0 기능 목록(feature-spec-draft.json)을 Excel로 저장."""
        draft_path = self._orch.run_dir / "dom-scan" / "feature-spec-draft.json"
        if not draft_path.exists():
            QMessageBox.warning(self, "알림", "Stage 0 DOM 스캔 결과가 없습니다.")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "기능 목록 저장",
            f"feature_list_{self._config.run_id}.xlsx",
            "Excel 파일 (*.xlsx);;모든 파일 (*.*)",
        )
        if not save_path:
            return

        try:
            import json
            from app.tools.excel_builder import build_features
            draft    = json.loads(draft_path.read_text(encoding="utf-8"))
            features = draft.get("features", [])
            if not features:
                QMessageBox.information(self, "알림", "추출된 기능이 없습니다 (features: 0개).")
                return
            build_features(features, save_path)
            QMessageBox.information(
                self, "저장 완료",
                f"기능 목록 {len(features)}개를 저장했습니다:\n{save_path}\n\n"
                f"스크린샷 파일은:\n{self._orch.run_dir / 'dom-scan' / 'screenshots'}",
            )
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ── 오류 처리 ─────────────────────────────────────────────────────────────
    def _on_error(self, msg: str) -> None:
        # 어느 단계에서 실패했든 실행 버튼 복원 + 중단 버튼 숨김
        self._run_btn.setEnabled(True)
        if not self._run_btn.isVisible():
            self._exec_btn.setEnabled(True)
        self._stop_btn.setVisible(False)
        self._pause_btn.setVisible(False)
        self._set_status("오류 발생", active=False, running=False)
        self._append_log(f"[오류]\n{msg}")
        # 시스템 트레이 알림 (백그라운드 실행 중에도 인지 가능)
        first_line = msg.splitlines()[0][:120] if msg else ""
        self._notify("AWT — 오류 발생", first_line or "실행이 중단되었습니다", "critical")
        # 오류 종류별 다이얼로그
        if "모델을 찾을 수 없습니다" in msg:
            QMessageBox.critical(self, "모델 오류", msg[:600])
        elif "API 키가 올바르지 않습니다" in msg:
            QMessageBox.critical(self, "API 키 오류", msg[:600])
        else:
            QMessageBox.critical(self, "오류", msg[:800])

    # ── 시스템 트레이 알림 ────────────────────────────────────────────────
    def _notify(
        self,
        title: str,
        message: str,
        icon_type: str = "info",   # info / warning / critical
    ) -> None:
        """OS 알림 표시 + 창이 비활성/최소화 상태면 작업표시줄 깜빡임."""
        if self._tray is not None:
            icon_map = {
                "info":     QSystemTrayIcon.Information,
                "warning":  QSystemTrayIcon.Warning,
                "critical": QSystemTrayIcon.Critical,
            }
            try:
                self._tray.showMessage(
                    title, message,
                    icon_map.get(icon_type, QSystemTrayIcon.Information),
                    7000,
                )
            except Exception:
                pass
        # 백그라운드 창 알림 (작업표시줄 깜빡임)
        try:
            QApplication.alert(self, 0)
        except Exception:
            pass

    # ── TC 더블클릭 → 통합 상세 다이얼로그 ────────────────────────────────
    def _on_tc_double_clicked(self, row: int, _col: int) -> None:
        if row < 0 or row >= len(self._tcs):
            return
        from app.ui.failure_detail import FailureDetailDialog
        dlg = FailureDetailDialog(
            tcs=self._tcs,        # 전체 목록 전달 → 전/후 이동 가능
            index=row,
            run_dir=self._orch.run_dir,
            parent=self,
        )
        # 비모달이라 destroyed 시그널로 추적 정리
        dlg.destroyed.connect(lambda *_: self._open_detail_dialogs.remove(dlg)
                              if dlg in self._open_detail_dialogs else None)
        self._open_detail_dialogs.append(dlg)
        dlg.show()
        dlg.raise_()

    # ── TC 목록 Excel 다운로드 ────────────────────────────────────────────────
    def _export_tcs_excel(self) -> None:
        """현재 표시 중인 TC 목록을 Excel(.xlsx)로 저장."""
        if not self._tcs:
            QMessageBox.information(self, "알림", "저장할 TC가 없습니다.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "TC 목록 저장",
            f"tc_list_{self._config.run_id}.xlsx",
            "Excel 파일 (*.xlsx);;모든 파일 (*.*)",
        )
        if not save_path:
            return
        try:
            from app.tools.excel_builder import build
            # meta.json 있으면 제한사항·커버리지 시트도 포함
            import json
            meta = None
            mp = self._orch.run_dir / "meta.json"
            if mp.exists():
                try:
                    meta = json.loads(mp.read_text(encoding="utf-8"))
                except Exception:
                    meta = None
            build(self._tcs, save_path, meta=meta)
            QMessageBox.information(
                self, "저장 완료",
                f"TC {len(self._tcs)}개를 저장했습니다:\n{save_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ── 실행 정보 (설정·수집 요소 조회/수정) ──────────────────────────────────
    def _open_run_info(self) -> None:
        try:
            from app.ui.run_info import RunInfoDialog
            dlg = RunInfoDialog(self._orch.run_dir, parent=self)
            dlg.clone_requested.connect(self.clone_requested.emit)  # main.py가 마법사 prefill
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "실행 정보 오류", str(e))

    # ── 로그 검색 ───────────────────────────────────────────────────────────
    def _active_log(self) -> QPlainTextEdit:
        """현재 표시 중인 로그 패널(raw 또는 일반)을 반환."""
        return self._raw_log if self._toggle_raw_btn.isChecked() else self._log

    def _log_search_changed(self, text: str) -> None:
        """검색어 변경 시 첫 일치 위치로 이동."""
        if not text:
            return
        # 첫 위치로 검색
        from PySide6.QtGui import QTextCursor
        widget = self._active_log()
        cursor = widget.document().find(text)
        if not cursor.isNull():
            widget.setTextCursor(cursor)
            widget.ensureCursorVisible()

    def _log_find_next(self) -> None:
        from PySide6.QtGui import QTextCursor
        text = self._log_search.text()
        if not text:
            return
        widget = self._active_log()
        cursor = widget.document().find(text, widget.textCursor())
        if cursor.isNull():
            # 끝까지 갔으면 처음부터
            cursor = widget.document().find(text)
        if not cursor.isNull():
            widget.setTextCursor(cursor)
            widget.ensureCursorVisible()

    def _log_find_prev(self) -> None:
        from PySide6.QtGui import QTextCursor, QTextDocument
        text = self._log_search.text()
        if not text:
            return
        widget = self._active_log()
        cursor = widget.document().find(text, widget.textCursor(),
                                         QTextDocument.FindBackward)
        if cursor.isNull():
            # 처음까지 갔으면 끝부터
            end_cursor = QTextCursor(widget.document())
            end_cursor.movePosition(QTextCursor.End)
            cursor = widget.document().find(text, end_cursor,
                                             QTextDocument.FindBackward)
        if not cursor.isNull():
            widget.setTextCursor(cursor)
            widget.ensureCursorVisible()

    # ── 상세(raw) 로그 ───────────────────────────────────────────────────────
    def _append_raw_log(self, msg: str) -> None:
        """원본 로그 패널에 라인 추가. 상세 로그가 숨겨져 있어도 메모리에는 축적."""
        ts   = datetime.now().strftime("%H:%M:%S.%f")[:-3]   # ms 단위
        line = f"[{ts}] {msg}"
        self._raw_log.appendPlainText(line)
        sb = self._raw_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _toggle_raw_log(self, checked: bool) -> None:
        """상세 로그 패널 표시/숨김 토글."""
        self._raw_log.setVisible(checked)
        if checked:
            # 토글한 순간 자동으로 최하단으로
            sb = self._raw_log.verticalScrollBar()
            sb.setValue(sb.maximum())

    # ── UI 갱신 ───────────────────────────────────────────────────────────────
    def _append_log(self, msg: str) -> None:
        """로그 한 줄 추가. word-wrap된 후속 줄도 시간 영역만큼 자동 들여쓰기."""
        ts     = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{ts}] "
        text   = prefix + (msg or "")

        # 시간 영역 픽셀 너비 계산 → hanging indent
        fm      = QFontMetrics(self._log.font())
        indent  = fm.horizontalAdvance(prefix)

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 첫 줄이 아니면 새 블록(=새 줄) 시작
        if not self._log.document().isEmpty():
            cursor.insertBlock()

        # hanging indent: 좌측 여백 = indent, 첫 줄만 indent만큼 끌어옴
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(indent)
        fmt.setTextIndent(-indent)
        cursor.setBlockFormat(fmt)

        # \n으로 분리된 경우 각 줄을 같은 블록 안에 줄바꿈 문자로 넣음 → 동일 들여쓰기 적용
        cursor.insertText(text.replace("\r\n", "\n").replace("\r", "\n"))

        self._log.setTextCursor(cursor)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_tc_table(self) -> None:
        self._tc_table.setRowCount(0)
        self._tc_count_lbl.setText(f"총 {len(self._tcs)}건")

        status_colors = {
            "approved": QColor("#d1fae5"),
            "edited":   QColor("#dbeafe"),
            "rejected": QColor("#fee2e2"),
            "pending":  QColor("#f1f5f9"),
        }
        result_colors = {
            "pass":         QColor("#d1fae5"),
            "fail":         QColor("#fee2e2"),
            "blocked":      QColor("#ffe4e6"),
            "not_executed": QColor("#e2e8f0"),
        }

        for tc in self._tcs:
            r = self._tc_table.rowCount()
            self._tc_table.insertRow(r)

            technique_en = tc.get("design_technique", "")
            status       = tc.get("review_status", "pending")
            result       = tc.get("result", "not_executed")

            bg     = status_colors.get(status, QColor("white"))
            res_bg = result_colors.get(result, QColor("white"))

            cells = [
                (0, tc.get("대분류", ""),             bg),
                (1, tc.get("중분류", ""),             bg),
                (2, tc.get("소분류", ""),             bg),
                (3, tc.get("tc_id", ""),             bg),
                (4, tc.get("scenario", ""),           bg),
                (5, tc.get("precondition", "")[:80],  bg),
                (6, tc.get("expected", "")[:80],      bg),
                (7, _TECHNIQUE_KO.get(technique_en, technique_en), bg),
                (8, _STATUS_KO.get(status, status),   bg),
                (9, _RESULT_KO.get(result, result),   res_bg),
            ]
            for col, text, color in cells:
                item = QTableWidgetItem(text)
                item.setBackground(color)
                self._tc_table.setItem(r, col, item)

    # ── 커버리지 계산 ─────────────────────────────────────────────────────────
    def _compute_coverage(self) -> dict:
        """시험 커버리지 산출: 고유 기능 중 실제 TC가 설계된 비율.

        분모 = 정제된 고유 기능 수(refine final), 없으면 leaf 수.
        분자 = TC가 1개 이상 설계된 고유 leaf(소분류) 수.
        """
        try:
            ing = self._orch.ingest_result or {}
            # 통합(consolidate) 후 leaf 수가 최종 고유 기능 수
            total = len(ing.get("leaves", []))
            if not total:
                refine = ing.get("refine_report", {})
                total = refine.get("final", 0)
            # TC가 설계된 소분류 집합
            designed_leaves = {
                tc.get("소분류", "") for tc in (self._tcs or []) if tc.get("소분류")
            }
            designed = len(designed_leaves)
            pct = round(designed / total * 100, 1) if total else 0.0
            return {
                "total_unique_features": total,
                "designed_features":     designed,
                "coverage_pct":          pct,
                "total_tcs":             len(self._tcs or []),
            }
        except Exception:
            return {}

    # ── 메타 저장 ─────────────────────────────────────────────────────────────
    def _write_meta(self, stage: str) -> None:
        """run의 진행 상태와 시험 환경을 meta.json에 기록.

        박정훈(시험 인증)의 권고대로 재현·추적성에 필요한 정보를 모두 기록:
          - 시험 환경 (headless / model / prompt 등)
          - 사용된 캐시 정보 (URL → 출처 run)
          - 분석에서 제외/실패한 leaf 정보
          - 시간 정보 (시작/현재)
        """
        try:
            cfg = self._config
            # 기존 meta 유지하면서 갱신 (started 시 created_at 같은 필드 보존)
            meta_path = self._orch.run_dir / "meta.json"
            prev: dict = {}
            if meta_path.exists():
                try:
                    prev = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    prev = {}

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            meta = {
                **prev,
                "run_id":         cfg.run_id,
                "target_url":     cfg.target_url,
                # 비웹 대상 재현 — 다시 열기 시 대상 유형/설정 복원에 필수 (D59)
                "target_kind":    getattr(cfg, "target_kind", "web") or "web",
                "target_config":  getattr(cfg, "target_config", {}) or {},
                "stage":          stage,
                "updated_at":     now_str,
                # ── 시험 환경 (재현용) ─────────────────────────────────────
                "model_override": cfg.model_override,
                "model_overrides": cfg.model_overrides or {},
                "headless_exec":  cfg.headless_exec,
                "slow_mo_ms":     cfg.slow_mo_ms,
                "max_leaves":     cfg.max_leaves,
                "max_pages":      cfg.max_pages,
                "inferred_threshold": cfg.inferred_threshold,
                # ── 캐시 사용 (URL 목록만 기록) ─────────────────────────────
                "dom_cache_used": list((cfg.cached_features or {}).keys()),
                # ── 선택된 페이지 ───────────────────────────────────────────
                "selected_urls":  cfg.selected_urls or [],
                # ── 중복 정리 추적성: 대표 URL → 묶인 동형 URL 목록 ──────────
                "selected_url_groups": cfg.selected_url_groups or {},
                # ── 입력 파일 (이름만) ──────────────────────────────────────
                "input_files":    [str(p) for p in (cfg.input_files or [])],
                # ── 인증 시퀀스 (복제 시 Step 2 재현용) ─────────────────────
                # ⚠ 로컬 시험 도구 — auth 값(비밀번호 포함)이 평문 저장됨.
                #    data/runs/ 는 gitignore 대상.
                "auth_sequence":  cfg.auth_sequence or [],
                # ── 박정훈 추적성 권고: Stage 2에서 누락된 leaf 정보 ──────
                "stage2_failed_leaves":   getattr(self._orch, "stage2_failed_leaves",   []),
                "stage2_excluded_leaves": getattr(self._orch, "stage2_excluded_leaves", []),
                # ── 커버리지: 기능 정제/통합 리포트 + 시험 커버리지 % ────────
                "refine_report":      (self._orch.ingest_result or {}).get("refine_report", {}),
                "consolidate_report": (self._orch.ingest_result or {}).get("consolidate_report", {}),
                "feature_gate":       (self._orch.ingest_result or {}).get("feature_gate", {}),
                "coverage":           self._compute_coverage(),
            }
            if "created_at" not in meta:
                meta["created_at"] = now_str

            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

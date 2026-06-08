"""Stage 4 Reviewer Gate — TC별 A/E/R/P 결정 UI (D45: PySide6)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QTextEdit, QSplitter, QWidget, QMessageBox, QFileDialog,
    QFrame,
)

_STATUS_OPTIONS = ["pending", "approved", "edited", "rejected"]
_STATUS_KO = {
    "pending":  "검토 전",
    "approved": "승인",
    "edited":   "수정",
    "rejected": "거부",
}
_STATUS_COLORS = {
    "approved": QColor("#d1fae5"),
    "edited":   QColor("#dbeafe"),
    "rejected": QColor("#fee2e2"),
    "pending":  QColor("#fef9c3"),
}

# ── D57: 리스크 기반 검토 triage ────────────────────────────────────────────
# 위험점수(risk_score) = 생성 신뢰도(주축) + 근거 출처/기법/민감도 보정.
# source(참고문서)에만 의존하지 않으므로 DOM-only(전부 INFERRED) 시험에서도 동작.
_RISK_RED  = 0.45   # 미만 → 집중 검토
_RISK_GREEN = 0.75  # 이상 → 안전(일괄승인 후보)
_BUCKET_KO = {"red": "🔴 집중 검토", "yellow": "🟡 빠른 확인", "green": "🟢 안전"}


def _tc_source_kind(tc: dict) -> str:
    s = str(tc.get("source_quote", "") or "").upper()
    for p in ("MANUAL", "INVARIANT", "INFERRED"):
        if s.startswith(p):
            return p
    return "INFERRED"


def _risk_score(tc: dict) -> float:
    try:
        score = float(tc.get("gen_confidence", "") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    kind = _tc_source_kind(tc)
    if kind == "MANUAL":
        score += 0.15
    elif kind == "INVARIANT":
        score += 0.10
    tech = (tc.get("design_technique", "") or "")
    if tech == "happy_path":
        score += 0.10
    elif tech in ("negative_deep", "cross_feature"):
        score -= 0.05
    if (tc.get("negative_category", "") or "") in ("injection_or_security", "permission_denied"):
        score -= 0.05
    return score


def _risk_bucket(tc: dict) -> str:
    s = _risk_score(tc)
    if s < _RISK_RED:
        return "red"
    if s >= _RISK_GREEN:
        return "green"
    return "yellow"


def _risk_reason(tc: dict) -> str:
    """이 TC를 왜 (얼마나) 검토해야 하는지 한 줄 설명 — #4 막연함 해소."""
    bucket = _risk_bucket(tc)
    kind = _tc_source_kind(tc)
    try:
        conf = float(tc.get("gen_confidence", "") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    src_ko = {"MANUAL": "매뉴얼 근거", "INVARIANT": "규칙 근거", "INFERRED": "AI 추론(근거 없음)"}[kind]
    if bucket == "red":
        return f"집중 검토 권장 — {src_ko} · 신뢰도 {conf:.2f}. 거짓 가능성 점검 필요."
    if bucket == "green":
        return f"안전 — {src_ko} · 신뢰도 {conf:.2f}. 일괄 승인 후보."
    return f"빠른 확인 — {src_ko} · 신뢰도 {conf:.2f}."

# 상세 팝업에 표시할 TC 필드
_TC_FIELDS: list[tuple[str, str]] = [
    ("tc_id",            "TC ID"),
    ("대분류",            "대분류"),
    ("중분류",            "중분류"),
    ("소분류",            "소분류"),
    ("scenario",         "시나리오"),
    ("precondition",     "사전조건"),
    ("expected",         "기대출력"),
    ("design_technique", "설계기법"),
    ("requirement_id",   "요구사항 ID"),
    ("source_quote",     "근거 문구"),
    ("gen_confidence",   "생성 신뢰도"),
]

_CARD = (
    "QFrame { background-color: #ffffff; border-radius: 8px;"
    " border: 1px solid #e2e8f0; }"
)
_SUBHDR = (
    "QFrame { background-color: #f8fafc;"
    " border-top-left-radius: 8px; border-top-right-radius: 8px;"
    " border-bottom: 1px solid #e2e8f0; border-left: none;"
    " border-right: none; border-top: none; }"
)


# ── TC 상세 팝업 ────────────────────────────────────────────────────────────
class _TcDetailDialog(QDialog):
    """더블클릭 시 표시되는 TC 전체 내용 팝업."""

    def __init__(self, tc: dict, parent=None):
        super().__init__(parent)
        tc_id = tc.get("tc_id", "?")
        self.setWindowTitle(f"TC 상세 — {tc_id}")
        self.resize(680, 540)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet("QDialog { background-color: #f1f5f9; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 제목
        hdr_lbl = QLabel(
            f"<span style='font-size:15px; font-weight:700; color:#1e293b;'>{tc_id}</span>"
        )
        root.addWidget(hdr_lbl)

        # 내용 카드
        card = QFrame()
        card.setStyleSheet(_CARD)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 0, 0, 0)

        # 서브헤더
        sub = QFrame()
        sub.setFixedHeight(36)
        sub.setStyleSheet(_SUBHDR)
        sub_lay = QHBoxLayout(sub)
        sub_lay.setContentsMargins(14, 0, 14, 0)
        sub_lay.addWidget(QLabel("<b style='color:#64748b; font-size:12px;'>전체 내용</b>"))
        card_lay.addWidget(sub)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Segoe UI", 10))
        txt.setStyleSheet(
            "QTextEdit { background-color: #ffffff; border: none;"
            " color: #1e293b; padding: 12px; }"
        )

        # HTML 렌더링으로 줄바꿈 포함 전체 내용 표시
        html_parts: list[str] = []
        for key, label in _TC_FIELDS:
            val = tc.get(key, "")
            if val is None:
                val = ""
            val = str(val)
            if val.strip():
                escaped = val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_parts.append(
                    f"<p style='margin:0 0 2px 0;'>"
                    f"<span style='color:#64748b; font-size:11px; font-weight:600;'>{label}</span>"
                    f"</p>"
                    f"<p style='margin:0 0 12px 0; color:#1e293b;'>{escaped}</p>"
                )
        txt.setHtml("".join(html_parts))
        card_lay.addWidget(txt)
        root.addWidget(card)

        close_btn = QPushButton("닫기")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: #ffffff; border-radius: 6px;"
            " font-size: 13px; font-weight: 600; border: none; padding: 0 20px; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignRight)


# ── Reviewer Gate 메인 다이얼로그 ────────────────────────────────────────────
class _RegenerateWorker(QThread):
    """rejected TC 재생성 백그라운드 worker."""
    progress = Signal(str)
    finished_ok = Signal(list, int, int)   # (new_tcs, replaced, failed_leaf_count)
    error    = Signal(str)

    def __init__(self, tcs, llm_client, manual_text, parent=None):
        super().__init__(parent)
        self._tcs = tcs
        self._llm = llm_client
        self._manual = manual_text

    def run(self) -> None:
        try:
            from app.core.regenerate_rejected import regenerate_rejected
            new_tcs, replaced, failed = regenerate_rejected(
                self._tcs, self._llm, self._manual,
                progress_cb=self.progress.emit,
            )
            self.finished_ok.emit(new_tcs, replaced, failed)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


class ReviewerGate(QDialog):
    """TC 목록에 대해 A/E/R/P 결정. decisions_ready(dict) 시그널로 결과 전달."""

    decisions_ready = Signal(dict)  # {tc_id: {status, note}}
    tcs_regenerated = Signal(list)  # 재생성 후 새 TC 리스트 (호출자가 갱신용)

    def __init__(
        self,
        tcs: list[dict],
        reviewer_id: str,
        parent=None,
        llm_client=None,             # 재생성에 사용 (None이면 재생성 기능 비활성)
        manual_text: str = "",       # 재생성 컨텍스트
        run_dir=None,                # D58 — 스크린샷 조회용 run 디렉토리
    ):
        super().__init__(parent)
        self.setWindowTitle("Stage 4 — Reviewer Gate")
        self.resize(1200, 720)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet("QDialog { background-color: #f1f5f9; }")

        self._tcs = tcs
        self._reviewer_id = reviewer_id
        self._llm = llm_client
        self._manual_text = manual_text
        self._run_dir = run_dir
        self._regen_worker: _RegenerateWorker | None = None
        self._bucket_filter: str | None = None      # D57 — None=전체, 'red'/'yellow'/'green'
        self._row_to_idx: list[int] = []             # 표 행 → self._tcs 인덱스 매핑(필터 대응)
        self._decisions: dict[str, dict] = {
            tc.get("tc_id", f"__unknown_{i}__"): {
                "status": tc.get("review_status", "pending"),
                "note":   tc.get("reviewer_note", ""),
                "reviewer_id": reviewer_id,
            }
            for i, tc in enumerate(tcs)
        }
        self._build_ui()
        self._load_tcs()

    # ── UI 구성 ──────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ── 상단 요약 바 ──────────────────────────────────────────────────
        top_card = QFrame()
        top_card.setStyleSheet(_CARD)
        top_lay = QHBoxLayout(top_card)
        top_lay.setContentsMargins(16, 10, 16, 10)
        top_lay.setSpacing(10)

        top_lay.addWidget(
            QLabel("<b style='font-size:15px; color:#1e293b;'>Stage 4 — Reviewer Gate</b>")
        )

        self._summary_lbl = QLabel()
        self._summary_lbl.setStyleSheet("color: #64748b; font-size: 13px;")
        top_lay.addWidget(self._summary_lbl)

        # D57 — 버킷 필터 칩 (클릭 시 해당 버킷만 표시)
        self._bucket_chips: dict[str, QPushButton] = {}
        for key, label in [("all", "전체"), ("red", "🔴 집중"),
                           ("yellow", "🟡 확인"), ("green", "🟢 안전")]:
            chip = QPushButton(label)
            chip.setCheckable(True)
            chip.setFixedHeight(26)
            chip.setStyleSheet(
                "QPushButton { background:#ffffff; color:#475569; border:1px solid #e2e8f0;"
                " border-radius:13px; padding:0 12px; font-size:11px; }"
                "QPushButton:checked { background:#1e293b; color:#ffffff; border-color:#1e293b; }"
            )
            chip.clicked.connect(lambda _=False, k=key: self._set_bucket_filter(k))
            top_lay.addWidget(chip)
            self._bucket_chips[key] = chip
        self._bucket_chips["all"].setChecked(True)

        top_lay.addStretch()

        # 일괄 처리 버튼
        # D57 — 🟢 안전 일괄 승인 (검토 부담 직접 해소)
        approve_green = QPushButton("🟢 안전 일괄 승인")
        approve_green.setFixedHeight(32)
        approve_green.setStyleSheet(
            "QPushButton { background: #059669; color: #ffffff; border-radius: 6px;"
            " padding: 0 14px; font-size: 12px; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #047857; }"
        )
        approve_green.setToolTip("🟢 안전 버킷(고신뢰·근거확실) TC를 일괄 승인합니다.")
        approve_green.clicked.connect(lambda: self._approve_bucket("green"))
        top_lay.addWidget(approve_green)

        approve_all = QPushButton("전체 승인")
        approve_all.setFixedHeight(32)
        approve_all.setStyleSheet(
            "QPushButton { background: #16a34a; color: #ffffff; border-radius: 6px;"
            " padding: 0 14px; font-size: 12px; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #15803d; }"
        )
        approve_all.clicked.connect(lambda: self._set_all("approved"))
        top_lay.addWidget(approve_all)

        reject_all = QPushButton("전체 거부")
        reject_all.setFixedHeight(32)
        reject_all.setStyleSheet(
            "QPushButton { background: #dc2626; color: #ffffff; border-radius: 6px;"
            " padding: 0 14px; font-size: 12px; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #b91c1c; }"
        )
        reject_all.clicked.connect(lambda: self._set_all("rejected"))
        top_lay.addWidget(reject_all)

        # Excel 다운로드 버튼
        excel_btn = QPushButton("⬇ Excel 다운로드")
        excel_btn.setFixedHeight(32)
        excel_btn.setStyleSheet(
            "QPushButton { background: #0f766e; color: #ffffff; border-radius: 6px;"
            " padding: 0 14px; font-size: 12px; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #0d9488; }"
        )
        excel_btn.clicked.connect(self._export_excel)
        top_lay.addWidget(excel_btn)

        # 거부된 TC 재생성 버튼 (llm_client 있을 때만)
        if self._llm is not None:
            self._regen_btn = QPushButton("🔄  거부 TC 재생성")
            self._regen_btn.setFixedHeight(32)
            self._regen_btn.setStyleSheet(
                "QPushButton { background: #7c3aed; color: #ffffff; border-radius: 6px;"
                " padding: 0 14px; font-size: 12px; font-weight: 600; border: none; }"
                "QPushButton:hover { background: #6d28d9; }"
                "QPushButton:disabled { background: #c4b5fd; }"
            )
            self._regen_btn.setToolTip(
                "거부 상태인 TC들의 사유를 AI에 전달하여 새로운 TC로 재생성합니다.\n"
                "(승인/수정 TC는 보존됩니다. 재생성된 TC는 pending 상태로 다시 검토 필요)"
            )
            self._regen_btn.clicked.connect(self._regenerate_rejected)
            top_lay.addWidget(self._regen_btn)

        root.addWidget(top_card)

        # ── 스플리터: TC 테이블 | 상세 패널 ─────────────────────────────
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(6)

        # ── 왼쪽: TC 테이블 카드 ──────────────────────────────────────────
        table_card = QFrame()
        table_card.setStyleSheet(_CARD)
        table_card_lay = QVBoxLayout(table_card)
        table_card_lay.setContentsMargins(0, 0, 0, 0)
        table_card_lay.setSpacing(0)

        # 테이블 헤더 행
        t_hdr = QFrame()
        t_hdr.setFixedHeight(36)
        t_hdr.setStyleSheet(_SUBHDR)
        t_hdr_lay = QHBoxLayout(t_hdr)
        t_hdr_lay.setContentsMargins(14, 0, 14, 0)
        t_hdr_lay.addWidget(QLabel("<b style='color:#1e293b;'>TC 목록</b>"))
        t_hdr_lay.addWidget(
            QLabel("<span style='color:#94a3b8; font-size:11px;'>"
                   "더블클릭 → 스크린샷·상세  |  키보드: A 승인 · E 수정 · R 거부 · ↑↓ 이동</span>")
        )
        t_hdr_lay.addStretch()
        table_card_lay.addWidget(t_hdr)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(["위험", "TC ID", "대분류", "시나리오", "기법", "상태"])

        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Interactive)   # 드래그로 너비 조절 가능
        hh.setStretchLastSection(False)
        # 초기 컬럼 너비
        self._table.setColumnWidth(0, 90)    # 위험(버킷)
        self._table.setColumnWidth(1, 100)   # TC ID
        self._table.setColumnWidth(2, 110)   # 대분류
        self._table.setColumnWidth(3, 320)   # 시나리오 (가장 넓게)
        self._table.setColumnWidth(4, 120)   # 기법
        self._table.setColumnWidth(5, 75)    # 상태

        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet(
            "QTableWidget { border: none; background-color: #ffffff;"
            " gridline-color: #f1f5f9; outline: none; }"
            "QHeaderView::section { background-color: #f8fafc; color: #64748b;"
            " font-weight: 600; font-size: 12px; border: none;"
            " border-bottom: 1px solid #e2e8f0; padding: 6px 8px; }"
            "QTableWidget::item { padding: 4px 8px; color: #1e293b; }"
            "QTableWidget::item:selected { background-color: #eff6ff; color: #1e293b; }"
        )

        # ← 핵심 수정: currentRowChanged 대신 currentCellChanged 사용
        self._table.currentCellChanged.connect(
            lambda cur_row, _cur_col, _prev_row, _prev_col:
                self._on_row_changed(cur_row)
        )
        # 더블클릭 → 전체 내용 팝업
        self._table.cellDoubleClicked.connect(self._on_double_click)

        table_card_lay.addWidget(self._table)
        splitter.addWidget(table_card)

        # ── 오른쪽: 상세 / 결정 카드 ────────────────────────────────────
        detail_card = QFrame()
        detail_card.setStyleSheet(_CARD)
        detail_card_lay = QVBoxLayout(detail_card)
        detail_card_lay.setContentsMargins(0, 0, 0, 0)
        detail_card_lay.setSpacing(0)

        d_hdr = QFrame()
        d_hdr.setFixedHeight(36)
        d_hdr.setStyleSheet(_SUBHDR)
        d_hdr_lay = QHBoxLayout(d_hdr)
        d_hdr_lay.setContentsMargins(14, 0, 14, 0)
        d_hdr_lay.addWidget(QLabel("<b style='color:#1e293b;'>TC 상세 / 결정</b>"))
        detail_card_lay.addWidget(d_hdr)

        # 상세 본문 영역
        detail_body = QWidget()
        detail_body.setStyleSheet("QWidget { background: transparent; border: none; }")
        body_lay = QVBoxLayout(detail_body)
        body_lay.setContentsMargins(14, 12, 14, 14)
        body_lay.setSpacing(8)

        # 요약 텍스트 (선택 행 정보)
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setFont(QFont("Segoe UI", 10))
        self._detail_text.setStyleSheet(
            "QTextEdit { background-color: #f8fafc; border: 1px solid #e2e8f0;"
            " border-radius: 6px; color: #1e293b; padding: 8px; }"
        )
        body_lay.addWidget(self._detail_text, stretch=3)

        # 결정 콤보
        body_lay.addWidget(
            QLabel("<span style='color:#64748b; font-size:11px; font-weight:600;'>결정</span>")
        )
        self._status_combo = QComboBox()
        self._status_combo.addItems([_STATUS_KO[s] for s in _STATUS_OPTIONS])
        self._status_combo.setFixedHeight(34)
        self._status_combo.setStyleSheet(
            "QComboBox { border: 1px solid #e2e8f0; border-radius: 6px;"
            " background: #ffffff; padding: 4px 10px; color: #1e293b; font-size: 13px; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { border: 1px solid #e2e8f0; background: #ffffff; }"
        )
        self._status_combo.currentIndexChanged.connect(self._on_status_changed)
        body_lay.addWidget(self._status_combo)

        # 검토 노트
        body_lay.addWidget(
            QLabel("<span style='color:#64748b; font-size:11px; font-weight:600;'>검토 노트</span>")
        )
        self._note_edit = QTextEdit()
        self._note_edit.setFixedHeight(80)
        self._note_edit.setStyleSheet(
            "QTextEdit { border: 1px solid #e2e8f0; border-radius: 6px;"
            " background: #ffffff; color: #1e293b; padding: 4px 8px; font-size: 13px; }"
        )
        self._note_edit.textChanged.connect(self._on_note_changed)
        body_lay.addWidget(self._note_edit)

        apply_btn = QPushButton("✔ 결정 적용 (상태·노트 → 테이블 반영)")
        apply_btn.setFixedHeight(36)
        apply_btn.setToolTip(
            "현재 상태와 검토 노트를 왼쪽 테이블에 시각적으로 반영합니다.\n"
            "※ 상태·노트는 입력하는 즉시 자동 저장됩니다.\n"
            "최종 확정은 하단 '결정 완료 → Stage 5 진행' 버튼을 누르세요."
        )
        apply_btn.setStyleSheet(
            "QPushButton { background: #3b82f6; color: #ffffff; border-radius: 6px;"
            " font-size: 13px; font-weight: 600; border: none; }"
            "QPushButton:hover { background: #2563eb; }"
        )
        apply_btn.clicked.connect(self._apply_current)
        body_lay.addWidget(apply_btn)

        auto_save_label = QLabel("💾 상태·노트는 입력 즉시 자동 저장됩니다.")
        auto_save_label.setStyleSheet(
            "QLabel { color: #94a3b8; font-size: 11px; padding: 2px 0; }"
        )
        body_lay.addWidget(auto_save_label)
        body_lay.addStretch()

        detail_card_lay.addWidget(detail_body, stretch=1)
        splitter.addWidget(detail_card)

        splitter.setSizes([760, 420])
        root.addWidget(splitter, stretch=1)

        # ── 하단 버튼 바 ──────────────────────────────────────────────────
        bot_card = QFrame()
        bot_card.setStyleSheet(_CARD)
        bot_lay = QHBoxLayout(bot_card)
        bot_lay.setContentsMargins(16, 10, 16, 10)

        cancel_btn = QPushButton("취소")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(
            "QPushButton { background: #ffffff; color: #64748b;"
            " border: 1px solid #e2e8f0; border-radius: 6px;"
            " font-size: 13px; padding: 0 18px; }"
            "QPushButton:hover { background: #f8fafc; }"
        )
        cancel_btn.clicked.connect(self.reject)

        self._submit_btn = QPushButton("결정 완료 → Stage 5 진행")
        self._submit_btn.setFixedHeight(36)
        self._submit_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; color: #ffffff; border-radius: 6px;"
            " font-size: 13px; font-weight: 600; border: none; padding: 0 20px; }"
            "QPushButton:hover { background: #6d28d9; }"
        )
        self._submit_btn.clicked.connect(self._submit)

        bot_lay.addWidget(cancel_btn)
        bot_lay.addStretch()
        bot_lay.addWidget(self._submit_btn)
        root.addWidget(bot_card)

    # ── 데이터 로딩 ──────────────────────────────────────────────────────
    def _load_tcs(self) -> None:
        self._table.setRowCount(0)
        self._row_to_idx = []
        bucket_short = {"red": "🔴", "yellow": "🟡", "green": "🟢"}
        for i, tc in enumerate(self._tcs):
            bucket = _risk_bucket(tc)
            # D57 — 버킷 필터: 선택된 버킷만 표시(None=전체)
            if self._bucket_filter and bucket != self._bucket_filter:
                continue
            r = self._table.rowCount()
            self._table.insertRow(r)
            self._row_to_idx.append(i)
            tc_id = tc.get("tc_id", f"__unknown_{i}__")
            status = self._decisions.get(tc_id, {}).get("status", "pending")
            items = [
                QTableWidgetItem(bucket_short.get(bucket, "")),
                QTableWidgetItem(tc_id),
                QTableWidgetItem(tc.get("대분류", "")),
                QTableWidgetItem(tc.get("scenario", "")),     # 잘림 없이 전체 저장
                QTableWidgetItem(tc.get("design_technique", "")),
                QTableWidgetItem(_STATUS_KO.get(status, status)),
            ]
            bg = _STATUS_COLORS.get(status, QColor("#ffffff"))
            for item in items:
                item.setBackground(bg)
            for col, item in enumerate(items):
                self._table.setItem(r, col, item)
        self._update_summary()

    def _tc_at(self, row: int) -> dict | None:
        """표 행 → 실제 TC(필터/매핑 반영)."""
        if 0 <= row < len(self._row_to_idx):
            return self._tcs[self._row_to_idx[row]]
        return None

    # ── 이벤트 핸들러 ────────────────────────────────────────────────────
    def _on_row_changed(self, row: int) -> None:
        """테이블 선택 행 변경 시 상세 패널 갱신."""
        tc = self._tc_at(row)
        if tc is None:
            return
        tc_id = tc.get("tc_id", f"__unknown_{row}__")
        dec = self._decisions.get(tc_id, {"status": "pending", "note": ""})

        # D57 — "왜 검토하나" 한 줄(막연함 해소) + 필드 상세
        lines = [f"[검토 안내] {_risk_reason(tc)}", ""]
        for key, label in _TC_FIELDS:
            val = tc.get(key, "")
            if val:
                lines.append(f"[{label}]\n{val}")
        self._detail_text.setPlainText("\n".join(lines))

        # 콤보 인덱스 설정 (blockSignals로 _on_status_changed 억제)
        status = dec.get("status", "pending")
        idx = _STATUS_OPTIONS.index(status) if status in _STATUS_OPTIONS else 0
        self._status_combo.blockSignals(True)
        self._status_combo.setCurrentIndex(idx)
        self._status_combo.blockSignals(False)

        self._note_edit.blockSignals(True)
        self._note_edit.setPlainText(dec.get("note", ""))
        self._note_edit.blockSignals(False)

    def _on_double_click(self, row: int, _col: int) -> None:
        """더블클릭 → TC 상세(스크린샷·전후이동·키보드, D58: failure_detail 재사용)."""
        if not (0 <= row < len(self._row_to_idx)):
            return
        idx = self._row_to_idx[row]
        try:
            from app.ui.failure_detail import FailureDetailDialog
            dlg = FailureDetailDialog(
                tcs=self._tcs, index=idx, run_dir=self._run_dir, parent=self
            )
            dlg.exec()
        except Exception:
            # 폴백: 기존 단순 팝업
            dlg = _TcDetailDialog(self._tcs[idx], parent=self)
            dlg.exec()

    def _on_status_changed(self, index: int) -> None:
        row = self._table.currentRow()
        tc = self._tc_at(row)
        if tc is None or index < 0 or index >= len(_STATUS_OPTIONS):
            return
        tc_id = tc.get("tc_id", f"__unknown_{row}__")
        if tc_id in self._decisions:
            self._decisions[tc_id]["status"] = _STATUS_OPTIONS[index]

    def _on_note_changed(self) -> None:
        row = self._table.currentRow()
        tc = self._tc_at(row)
        if tc is None:
            return
        tc_id = tc.get("tc_id", f"__unknown_{row}__")
        if tc_id in self._decisions:
            self._decisions[tc_id]["note"] = self._note_edit.toPlainText()

    def _apply_current(self) -> None:
        """상세 패널의 결정을 테이블 행에 반영."""
        row = self._table.currentRow()
        tc = self._tc_at(row)
        if tc is None:
            return
        tc_id = tc.get("tc_id", f"__unknown_{row}__")
        dec = self._decisions.get(tc_id, {"status": "pending"})
        status = dec["status"]
        bg = _STATUS_COLORS.get(status, QColor("#ffffff"))
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item:
                item.setBackground(bg)
        status_item = self._table.item(row, 5)
        if status_item:
            status_item.setText(_STATUS_KO.get(status, status))
        self._update_summary()

    def _set_all(self, status: str) -> None:
        """모든 TC 상태 일괄 변경."""
        for tc_id in self._decisions:
            self._decisions[tc_id]["status"] = status
        self._load_tcs()   # 표 다시 그려 상태/색 일괄 반영(필터 유지)

    # ── D58: 키보드 단축키 (A/E/R 결정 + ←/→ 행 이동) ────────────────────────
    def keyPressEvent(self, event) -> None:
        key = event.key()
        # 노트 편집 중에는 단축키 비활성(텍스트 입력 우선)
        if self._note_edit.hasFocus():
            super().keyPressEvent(event)
            return
        key_map = {Qt.Key_A: "approved", Qt.Key_E: "edited", Qt.Key_R: "rejected"}
        if key in key_map:
            self._set_current_status(key_map[key])
        elif key in (Qt.Key_Right, Qt.Key_Down):
            self._move_row(+1)
        elif key in (Qt.Key_Left, Qt.Key_Up):
            self._move_row(-1)
        else:
            super().keyPressEvent(event)

    def _set_current_status(self, status: str) -> None:
        """현재 선택 행에 결정 적용 후 다음 행으로 이동(빠른 검토 동선)."""
        row = self._table.currentRow()
        tc = self._tc_at(row)
        if tc is None:
            return
        tc_id = tc.get("tc_id", "")
        if tc_id in self._decisions:
            self._decisions[tc_id]["status"] = status
        self._apply_current()
        self._move_row(+1)

    def _move_row(self, delta: int) -> None:
        row = self._table.currentRow()
        new = max(0, min(self._table.rowCount() - 1, row + delta))
        if new != row:
            self._table.setCurrentCell(new, self._table.currentColumn() if self._table.currentColumn() >= 0 else 0)

    # ── D57: 버킷 필터 + 버킷 일괄 승인 ──────────────────────────────────────
    def _set_bucket_filter(self, key: str) -> None:
        self._bucket_filter = None if key == "all" else key
        for k, chip in self._bucket_chips.items():
            chip.setChecked(k == key)
        self._load_tcs()

    def _approve_bucket(self, bucket: str) -> None:
        """특정 버킷(예: green)의 TC를 일괄 승인."""
        n = 0
        for i, tc in enumerate(self._tcs):
            if _risk_bucket(tc) == bucket:
                tc_id = tc.get("tc_id", f"__unknown_{i}__")
                if tc_id in self._decisions:
                    self._decisions[tc_id]["status"] = "approved"
                    n += 1
        QMessageBox.information(
            self, "일괄 승인",
            f"{_BUCKET_KO.get(bucket, bucket)} 버킷 {n}개 TC를 승인했습니다."
        )
        self._load_tcs()

    def _update_summary(self) -> None:
        counts: dict[str, int] = {"approved": 0, "edited": 0, "rejected": 0, "pending": 0}
        for d in self._decisions.values():
            s = d.get("status", "pending")
            counts[s] = counts.get(s, 0) + 1

        # D57 — 버킷 분포 + 위험군(🔴) 검토 진행률(끝이 보이는 효과)
        bucket_n = {"red": 0, "yellow": 0, "green": 0}
        red_done = 0
        for i, tc in enumerate(self._tcs):
            b = _risk_bucket(tc)
            bucket_n[b] = bucket_n.get(b, 0) + 1
            if b == "red":
                st = self._decisions.get(tc.get("tc_id", f"__unknown_{i}__"), {}).get("status", "pending")
                if st != "pending":
                    red_done += 1
        # 칩 라벨에 건수 반영
        self._bucket_chips["red"].setText(f"🔴 집중 {bucket_n['red']}")
        self._bucket_chips["yellow"].setText(f"🟡 확인 {bucket_n['yellow']}")
        self._bucket_chips["green"].setText(f"🟢 안전 {bucket_n['green']}")

        self._summary_lbl.setText(
            f"총 {len(self._tcs)}건  |  🔴 집중검토 {red_done}/{bucket_n['red']} 완료  |  "
            f"승인 {counts['approved']}  수정 {counts['edited']}  "
            f"거부 {counts['rejected']}  검토 전 {counts['pending']}"
        )

    # ── 거부된 TC 재생성 ─────────────────────────────────────────────────
    def _regenerate_rejected(self) -> None:
        """rejected TC의 사유를 LLM에 전달해 새 TC로 교체."""
        if self._llm is None:
            return

        # 거부 TC 개수 확인
        rejected_count = sum(
            1 for d in self._decisions.values()
            if (d.get("status") or "").lower() == "rejected"
        )
        if rejected_count == 0:
            QMessageBox.information(
                self, "재생성 불가",
                "거부(rejected) 상태인 TC가 없습니다.\n"
                "재생성하려면 먼저 거부할 TC를 표시하고 사유를 입력하세요."
            )
            return

        # 사유 미입력 TC 개수 검사 + 확인
        no_note = sum(
            1 for tc in self._tcs
            if (self._decisions.get(tc.get("tc_id", ""), {}).get("status") == "rejected"
                and not (self._decisions.get(tc.get("tc_id", ""), {}).get("note") or "").strip())
        )
        warn_msg = (
            f"거부된 TC {rejected_count}개를 AI로 재생성합니다.\n\n"
        )
        if no_note > 0:
            warn_msg += (
                f"⚠ {no_note}개 TC는 거부 사유가 비어 있습니다.\n"
                "사유가 있으면 더 정확한 재생성이 가능합니다.\n\n"
            )
        warn_msg += "계속하시겠습니까? (LLM 호출이 발생합니다)"
        res = QMessageBox.question(
            self, "거부 TC 재생성",
            warn_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if res != QMessageBox.Yes:
            return

        # 현재 결정 상태를 TC에 반영해 worker에 넘김
        tcs_with_decisions = []
        for tc in self._tcs:
            tc_id = tc.get("tc_id", "")
            dec = self._decisions.get(tc_id, {})
            tcs_with_decisions.append({
                **tc,
                "review_status": dec.get("status", "pending"),
                "reviewer_note": dec.get("note", ""),
                "reviewer_id":   dec.get("reviewer_id", ""),
            })

        # UI 잠금
        self._regen_btn.setEnabled(False)
        self._regen_btn.setText("🔄  재생성 중…")
        self._submit_btn.setEnabled(False)

        self._regen_worker = _RegenerateWorker(
            tcs=tcs_with_decisions,
            llm_client=self._llm,
            manual_text=self._manual_text,
            parent=self,
        )
        self._regen_worker.progress.connect(self._on_regen_progress)
        self._regen_worker.finished_ok.connect(self._on_regen_done)
        self._regen_worker.error.connect(self._on_regen_error)
        self._regen_worker.start()

    def _on_regen_progress(self, msg: str) -> None:
        # 진행 메시지를 요약 라벨에 잠깐 표시
        self._summary_lbl.setText(msg[:100])

    def _on_regen_done(self, new_tcs: list, replaced: int, failed: int) -> None:
        self._regen_btn.setEnabled(True)
        self._regen_btn.setText("🔄  거부 TC 재생성")
        self._submit_btn.setEnabled(True)

        # 내부 상태 갱신: 새 TC + decisions 재구축
        self._tcs = new_tcs
        self._decisions = {
            tc.get("tc_id", f"__unknown_{i}__"): {
                "status": tc.get("review_status", "pending"),
                "note":   tc.get("reviewer_note", ""),
                "reviewer_id": self._reviewer_id,
            }
            for i, tc in enumerate(new_tcs)
        }
        self._load_tcs()

        # 호출자(PipelineView)에게도 새 TC 알림
        self.tcs_regenerated.emit(new_tcs)

        QMessageBox.information(
            self, "재생성 완료",
            f"✅ TC {replaced}개 교체/생성 완료\n"
            f"실패한 leaf: {failed}개\n\n"
            "재생성된 TC는 'pending'(검토 전) 상태로 표시됩니다.\n"
            "다시 검토 후 승인/거부/수정 결정해 주세요."
        )

    def _on_regen_error(self, err: str) -> None:
        self._regen_btn.setEnabled(True)
        self._regen_btn.setText("🔄  거부 TC 재생성")
        self._submit_btn.setEnabled(True)
        QMessageBox.critical(self, "재생성 오류", err[:1200])

    def _export_excel(self) -> None:
        """현재 TC 목록(결정 반영)을 Excel 파일로 저장."""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "TC 목록 저장",
            "tc_review.xlsx",
            "Excel 파일 (*.xlsx);;모든 파일 (*.*)",
        )
        if not save_path:
            return
        try:
            from app.tools.excel_builder import build_review
            tcs_with_decisions = []
            for tc in self._tcs:
                tc_id = tc.get("tc_id", "")
                dec = self._decisions.get(tc_id, {})
                tcs_with_decisions.append({
                    **tc,
                    "review_status": dec.get("status", "pending"),
                    "reviewer_note": dec.get("note", ""),
                    "reviewer_id":   dec.get("reviewer_id", ""),
                })
            build_review(tcs_with_decisions, save_path)
            QMessageBox.information(self, "저장 완료", f"저장되었습니다:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    def _submit(self) -> None:
        pending = sum(1 for d in self._decisions.values() if d["status"] == "pending")
        if pending > 0:
            res = QMessageBox.question(
                self, "확인",
                f"{pending}개 TC가 아직 '검토 전' 상태입니다. 그대로 완료하시겠습니까?\n"
                "(검토 전 TC는 Stage 5 자동 실행에서 제외됩니다.)",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res == QMessageBox.No:
                return
        self.decisions_ready.emit(self._decisions)
        self.accept()

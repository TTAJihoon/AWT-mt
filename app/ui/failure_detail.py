"""TC 통합 상세 패널 — 스크린샷·시나리오·실제 결과·실패 분석을 한 화면에.

이지수 UX 우선순위 #2: 결함 분석 시간 5분 → 1분.
"""
from __future__ import annotations
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QWidget, QPlainTextEdit,
    QSizePolicy,
)


_RESULT_STYLES = {
    "pass":         ("✅ 통과",  "#16a34a", "#dcfce7"),
    "fail":         ("❌ 실패",  "#dc2626", "#fee2e2"),
    "blocked":      ("⛔ 차단",  "#ea580c", "#ffedd5"),
    "not_executed": ("⏸ 미실행", "#64748b", "#f1f5f9"),
}

_REVIEW_KO = {
    "approved": "✅ 승인", "edited": "✏️ 수정",
    "rejected": "❌ 거부", "pending": "⏸ 검토 전",
}

_FAILURE_CAT_KO = {
    "selector_broken":   "선택자 깨짐 — 페이지 구조 변경",
    "scenario_error":    "시나리오 오류 — TC 설계 단계 오류",
    "expected_mismatch": "기대값 불일치 — 동작은 정상이지만 결과가 다름",
    "fictional_positive": "허구 긍정 — 실제로는 실패해야 할 케이스가 통과",
    "real_defect":       "실제 결함 — 시스템 버그",
}


class FailureDetailDialog(QDialog):
    """실패한 TC의 모든 컨텍스트를 한 화면에 모아 표시 (pass/blocked도 동일 UI)."""

    def __init__(self, tcs, index: int = 0, run_dir: Path = None, parent=None):
        """
        Args:
            tcs:   TC 목록 (전/후 이동용). 단일 dict도 허용(자동 래핑).
            index: 처음 표시할 TC 인덱스.
            run_dir: 스크린샷 탐색 기준 run 디렉터리.
        """
        super().__init__(parent)
        # 단일 dict 하위호환
        if isinstance(tcs, dict):
            tcs = [tcs]
        self._tcs     = tcs or []
        self._index   = max(0, min(index, len(self._tcs) - 1)) if self._tcs else 0
        self._run_dir = Path(run_dir) if run_dir else None
        self._tc      = self._tcs[self._index] if self._tcs else {}

        self.resize(1100, 740)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setModal(False)   # 비모달 → 여러 창 동시 가능
        self._build_ui()
        self._rebuild()

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # 콘텐츠 영역 — 전/후 이동 시 이 안만 교체
        self._content = QWidget()
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content_lay.setSpacing(10)
        root.addWidget(self._content, 1)

        # 하단: ◀ 이전 / N/M / 다음 ▶ / 닫기
        bottom = QHBoxLayout()
        self._prev_btn = QPushButton("◀  이전 TC")
        self._prev_btn.setFixedHeight(34)
        self._prev_btn.clicked.connect(self._go_prev)
        self._next_btn = QPushButton("다음 TC  ▶")
        self._next_btn.setFixedHeight(34)
        self._next_btn.clicked.connect(self._go_next)
        _nav_css = (
            "QPushButton { background:#ffffff; color:#1e293b;"
            " border:1px solid #cbd5e1; border-radius:6px;"
            " padding: 0 16px; font-size:13px; font-weight:600; }"
            "QPushButton:hover:enabled { background:#eff6ff; border-color:#93c5fd; }"
            "QPushButton:disabled { color:#cbd5e1; }"
        )
        self._prev_btn.setStyleSheet(_nav_css)
        self._next_btn.setStyleSheet(_nav_css)
        self._pos_lbl = QLabel("")
        self._pos_lbl.setStyleSheet(
            "QLabel { color:#475569; font-size:12px; font-weight:600;"
            " padding: 0 10px; }"
        )
        bottom.addWidget(self._prev_btn)
        bottom.addWidget(self._pos_lbl)
        bottom.addWidget(self._next_btn)
        bottom.addStretch()
        close_btn = QPushButton("닫기")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(
            "QPushButton { background:#ffffff; color:#475569;"
            " border:1px solid #cbd5e1; border-radius:6px;"
            " padding: 0 18px; font-size:13px; }"
            "QPushButton:hover { background:#f1f5f9; }"
        )
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn)
        root.addLayout(bottom)

    def _rebuild(self) -> None:
        """현재 인덱스의 TC로 콘텐츠 영역을 다시 채운다."""
        self._tc = self._tcs[self._index] if self._tcs else {}
        # 기존 콘텐츠 위젯 제거
        while self._content_lay.count():
            item = self._content_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        # 헤더 + 좌우 패널
        self._content_lay.addWidget(self._build_header())
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(6)
        split.addWidget(self._build_left_panel())
        split.addWidget(self._build_right_panel())
        split.setSizes([440, 620])
        self._content_lay.addWidget(split, 1)
        # 타이틀·네비 상태
        tc_id = self._tc.get("tc_id", "?")
        self.setWindowTitle(f"TC 상세 — {tc_id}")
        n = len(self._tcs)
        self._pos_lbl.setText(f"{self._index + 1} / {n}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < n - 1)

    def _go_prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._rebuild()

    def _go_next(self) -> None:
        if self._index < len(self._tcs) - 1:
            self._index += 1
            self._rebuild()

    def keyPressEvent(self, event) -> None:
        # ←/→ 키로도 이동
        from PySide6.QtCore import Qt as _Qt
        if event.key() == _Qt.Key_Left:
            self._go_prev(); return
        if event.key() == _Qt.Key_Right:
            self._go_next(); return
        super().keyPressEvent(event)

    # ── 헤더 ─────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        tc = self._tc
        tc_id = tc.get("tc_id", "?")
        result = (tc.get("result") or "not_executed").lower()
        label, fg, bg = _RESULT_STYLES.get(result, _RESULT_STYLES["not_executed"])

        w = QFrame()
        w.setStyleSheet(
            f"QFrame {{ background:{bg}; border:1px solid {fg}; border-radius:8px; }}"
        )
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # 결과 배지
        badge = QLabel(label)
        badge.setStyleSheet(
            f"QLabel {{ background:{fg}; color:#ffffff;"
            f" border-radius:4px; padding:4px 12px;"
            f" font-size:13px; font-weight:700; border: none; }}"
        )
        lay.addWidget(badge)

        # TC ID + 분류
        path_parts = [
            tc.get("대분류", "") or "",
            tc.get("중분류", "") or "",
            tc.get("소분류", "") or "",
        ]
        path_str = "  >  ".join(p for p in path_parts if p)
        info = QLabel(
            f"<span style='font-size:15px; font-weight:700; color:#1e293b;'>{tc_id}</span>"
            + (f"<br><span style='font-size:12px; color:#64748b;'>{path_str}</span>"
               if path_str else "")
        )
        info.setStyleSheet("QLabel { background: transparent; border: none; }")
        lay.addWidget(info)

        lay.addStretch()

        # 신뢰도(있으면)
        ec = tc.get("exec_confidence", 0.0) or 0.0
        if ec > 0:
            ec_lbl = QLabel(f"신뢰도  {ec * 100:.0f}%")
            ec_lbl.setStyleSheet(
                "QLabel { background:#ffffff; color:#475569;"
                " border:1px solid #cbd5e1; border-radius:4px;"
                " padding:4px 10px; font-size:11px; font-weight:600; }"
            )
            lay.addWidget(ec_lbl)

        # 리뷰 상태(있으면)
        rs = (tc.get("review_status") or "").lower()
        if rs in _REVIEW_KO:
            rs_lbl = QLabel(_REVIEW_KO[rs])
            rs_lbl.setStyleSheet(
                "QLabel { background:#ffffff; color:#475569;"
                " border:1px solid #cbd5e1; border-radius:4px;"
                " padding:4px 10px; font-size:11px; font-weight:600; }"
            )
            lay.addWidget(rs_lbl)

        return w

    # ── 좌측: 스크린샷 + 메타 ────────────────────────────────────────────
    def _build_left_panel(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background:#ffffff; border:1px solid #e2e8f0;"
            " border-radius:8px; }"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # 섹션 제목
        lay.addWidget(self._section_title("📸 페이지 스크린샷 (Stage 0)"))

        # 스크린샷 로드
        ss_widget = self._load_screenshot_widget()
        lay.addWidget(ss_widget, 1)

        # 메타 정보 (구분선)
        lay.addWidget(self._hsep())
        lay.addWidget(self._section_title("ℹ️ 메타 정보"))

        meta_w = QWidget()
        meta_lay = QVBoxLayout(meta_w)
        meta_lay.setContentsMargins(4, 0, 4, 0)
        meta_lay.setSpacing(4)
        for label, val in [
            ("요구사항 ID",  self._tc.get("requirement_id", "")),
            ("설계 기법",     self._tc.get("design_technique", "")),
            ("negative 분류", self._tc.get("negative_category", "") or "—"),
            ("결과 분류",     self._tc.get("failure_category", "") or "—"),
            ("분류 출처",     self._tc.get("failure_category_source", "") or "—"),
            ("리뷰어",        self._tc.get("reviewer_id", "") or "—"),
        ]:
            if val:
                meta_lay.addWidget(self._kv_widget(label, str(val)))
        lay.addWidget(meta_w)

        return card

    def _resolve_screenshot(self, ss_name: str) -> Path | None:
        """스크린샷 파일 경로 해석. 현재 run에 없으면 다른 run에서도 탐색.

        (DOM 캐시 재사용·기능 통합 시 screenshot_file이 다른 run의 것일 수 있음)
        """
        if not ss_name:
            return None
        # 1) 현재 run
        if self._run_dir:
            p = self._run_dir / "dom-scan" / "screenshots" / ss_name
            if p.exists():
                return p
        # 2) 모든 run의 screenshots 폴더에서 동일 파일명 탐색 (최근 우선)
        try:
            runs_dir = Path("data/runs")
            if runs_dir.exists():
                cands = sorted(
                    runs_dir.glob(f"*/dom-scan/screenshots/{ss_name}"),
                    key=lambda p: p.stat().st_mtime, reverse=True,
                )
                if cands:
                    return cands[0]
        except Exception:
            pass
        return None

    def _load_screenshot_widget(self) -> QWidget:
        ss_name = self._tc.get("screenshot_file", "")
        if not ss_name:
            return self._no_screenshot_placeholder("스크린샷 없음")
        ss_path = self._resolve_screenshot(ss_name)
        if ss_path is None:
            return self._no_screenshot_placeholder(
                f"파일을 찾을 수 없음:\n{ss_name}\n(어느 run에도 없음)"
            )

        pix = QPixmap(str(ss_path))
        if pix.isNull():
            return self._no_screenshot_placeholder("이미지 로드 실패")

        # 스크롤 가능 라벨 — 큰 스크린샷도 표시 가능
        img_lbl = QLabel()
        img_lbl.setPixmap(pix.scaledToWidth(420, Qt.SmoothTransformation))
        img_lbl.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        img_lbl.setStyleSheet("QLabel { background:#f8fafc; border:1px solid #e2e8f0; }")

        scroll = QScrollArea()
        scroll.setWidget(img_lbl)
        scroll.setWidgetResizable(False)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        scroll.setMinimumHeight(280)
        return scroll

    def _no_screenshot_placeholder(self, msg: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            "QFrame { background:#f1f5f9; border:1px dashed #cbd5e1;"
            " border-radius:6px; }"
        )
        w.setMinimumHeight(180)
        lay = QVBoxLayout(w)
        lay.addStretch()
        icon = QLabel("📷")
        icon.setStyleSheet(
            "QLabel { font-size:32px; color:#94a3b8; background:transparent; border:none; }"
        )
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        txt = QLabel(msg)
        txt.setStyleSheet(
            "QLabel { color:#64748b; font-size:11px; background:transparent; border:none; }"
        )
        txt.setAlignment(Qt.AlignCenter)
        txt.setWordWrap(True)
        lay.addWidget(txt)
        lay.addStretch()
        return w

    # ── 우측: 시나리오·실제·실패 분석·원본 ─────────────────────────────
    def _build_right_panel(self) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background:#ffffff; border:1px solid #e2e8f0;"
            " border-radius:8px; }"
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        body = QWidget()
        body.setStyleSheet("QWidget { background:transparent; }")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        tc = self._tc

        # ── 시나리오 ──────────────────────────────────────────────────
        lay.addWidget(self._section_title("📝 시나리오"))
        lay.addWidget(self._text_block(tc.get("scenario", "") or "(없음)"))

        if tc.get("precondition"):
            lay.addWidget(self._section_title("📋 사전 조건"))
            lay.addWidget(self._text_block(tc.get("precondition")))

        # ── 예상 / 실제 비교 ─────────────────────────────────────────
        lay.addWidget(self._section_title("🎯 예상 vs 실제 결과"))
        compare = QHBoxLayout()
        compare.setSpacing(8)
        compare.addWidget(self._compare_box(
            "예상", tc.get("expected", "") or "(없음)",
            "#16a34a", "#f0fdf4"
        ))
        compare.addWidget(self._compare_box(
            "실제", tc.get("actual", "") or "(아직 실행되지 않음)",
            "#dc2626" if (tc.get("result") == "fail") else "#475569",
            "#fef2f2" if (tc.get("result") == "fail") else "#f8fafc"
        ))
        compare_w = QWidget()
        compare_w.setLayout(compare)
        lay.addWidget(compare_w)

        # ── 실패 분석 (failure_reason / category) ─────────────────────
        if tc.get("result") == "fail":
            lay.addWidget(self._section_title("🔬 실패 원인 분석 (Stage 6)"))

            reason = tc.get("failure_reason", "") or "(분석 결과 없음)"
            lay.addWidget(self._highlight_block(reason, "#fef2f2", "#dc2626"))

            # 카테고리 설명
            cat = (tc.get("failure_category", "") or "").strip()
            if cat:
                desc = _FAILURE_CAT_KO.get(cat, cat)
                src  = tc.get("failure_category_source", "") or "—"
                lay.addWidget(self._kv_widget(
                    "실패 분류",
                    f"<b>{cat}</b> &nbsp; <span style='color:#64748b'>({desc})</span>",
                    html=True,
                ))
                lay.addWidget(self._kv_widget("분류 출처", src))
        elif tc.get("result") == "blocked":
            lay.addWidget(self._section_title("⛔ 차단 사유"))
            lay.addWidget(self._highlight_block(
                tc.get("failure_reason", "") or "(차단 사유 없음)",
                "#fff7ed", "#ea580c",
            ))

        # ── 리뷰어 노트 ──────────────────────────────────────────────
        if tc.get("reviewer_note"):
            lay.addWidget(self._section_title("✏️ 리뷰어 노트"))
            lay.addWidget(self._highlight_block(
                tc.get("reviewer_note"), "#eff6ff", "#3b82f6"
            ))

        # ── 원본 JSON (접혀 있음 — 클릭 시 펼침) ────────────────────
        lay.addWidget(self._section_title("🗂 원본 데이터 (JSON)"))
        raw_btn = QPushButton("▶  원본 JSON 보기")
        raw_btn.setCheckable(True)
        raw_btn.setStyleSheet(
            "QPushButton { background:#f8fafc; color:#475569;"
            " border:1px solid #cbd5e1; border-radius:4px;"
            " padding:4px 10px; font-size:11px; text-align:left; }"
            "QPushButton:checked { background:#eff6ff; color:#1d4ed8; }"
        )
        raw_view = QPlainTextEdit()
        raw_view.setReadOnly(True)
        raw_view.setFont(QFont("Consolas", 9))
        raw_view.setPlainText(json.dumps(tc, ensure_ascii=False, indent=2))
        raw_view.setStyleSheet(
            "QPlainTextEdit { background:#0f172a; color:#e2e8f0;"
            " border:1px solid #1e293b; border-radius:4px; padding:6px; }"
        )
        raw_view.setMinimumHeight(200)
        raw_view.setVisible(False)
        def _toggle_raw(checked: bool):
            raw_view.setVisible(checked)
            raw_btn.setText("▼  원본 JSON 숨김" if checked else "▶  원본 JSON 보기")
        raw_btn.toggled.connect(_toggle_raw)
        lay.addWidget(raw_btn)
        lay.addWidget(raw_view)

        lay.addStretch()

        scroll.setWidget(body)
        outer.addWidget(scroll)
        return card

    # ── 헬퍼 ─────────────────────────────────────────────────────────────
    def _section_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "QLabel { color:#1e293b; font-size:13px; font-weight:700;"
            " background:transparent; border:none;"
            " padding: 4px 0 2px 0; }"
        )
        return lbl

    def _text_block(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "QLabel { color:#334155; font-size:12px;"
            " background:#f8fafc; border:1px solid #e2e8f0;"
            " border-radius:4px; padding:8px 10px; }"
        )
        return lbl

    def _compare_box(self, title: str, content: str, fg: str, bg: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            f"QFrame {{ background:{bg}; border:1px solid {fg}; border-radius:4px; }}"
        )
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        head = QLabel(title)
        head.setStyleSheet(
            f"QLabel {{ color:{fg}; font-size:11px; font-weight:700;"
            f" background:transparent; border:none; }}"
        )
        lay.addWidget(head)
        body = QLabel(content)
        body.setWordWrap(True)
        body.setStyleSheet(
            "QLabel { color:#334155; font-size:12px;"
            " background:transparent; border:none; }"
        )
        lay.addWidget(body)
        return w

    def _highlight_block(self, text: str, bg: str, fg: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"QLabel {{ color:#1e293b; font-size:12px;"
            f" background:{bg}; border-left:3px solid {fg};"
            f" border-radius:3px; padding:8px 12px; }}"
        )
        return lbl

    def _kv_row(self, key: str, val: str, html: bool = False) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        k = QLabel(key)
        k.setFixedWidth(80)
        k.setStyleSheet(
            "QLabel { color:#64748b; font-size:11px; font-weight:600;"
            " background:transparent; border:none; }"
        )
        v = QLabel(val)
        v.setWordWrap(True)
        if html:
            v.setTextFormat(Qt.RichText)
        v.setStyleSheet(
            "QLabel { color:#334155; font-size:12px;"
            " background:transparent; border:none; }"
        )
        row.addWidget(k)
        row.addWidget(v, 1)
        return row

    def _kv_widget(self, key: str, val: str, html: bool = False) -> QWidget:
        """_kv_row를 QWidget으로 wrap (addWidget 가능하게)."""
        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        w.setLayout(self._kv_row(key, val, html=html))
        return w

    def _hsep(self) -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet("QFrame { background:#e2e8f0; border:none; }")
        return f

"""페이지 선택 다이얼로그 — Stage 1~3 실행 전에 URL 수집·선택·캐시 표시.

흐름:
    1. 다이얼로그 오픈 → 백그라운드 thread로 BFS URL 수집
    2. 수집 완료 시 테이블 채움
    3. 캐시 검색 (같은 target_url의 최근 run) → 캐시 있는 행 자동 체크 + ♻ 표시
    4. 사용자 체크 조정 후 "DOM 분석 시작" 클릭
    5. 반환: (selected_urls, cached_features_for_those)
"""
from __future__ import annotations
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QProgressBar, QFrame, QCheckBox, QApplication,
)


# ── BFS 워커 ─────────────────────────────────────────────────────────────────
class _CollectWorker(QThread):
    """백그라운드 BFS — UI 블로킹 방지."""

    progress = Signal(str)
    finished_ok = Signal(list)        # list[dict] {url, title, depth}
    error    = Signal(str)

    def __init__(
        self,
        start_url: str,
        max_pages: int,
        max_depth: int,
        auth_sequence: list[dict] | None,
        parent=None,
    ):
        super().__init__(parent)
        self._start_url     = start_url
        self._max_pages     = max_pages
        self._max_depth     = max_depth
        self._auth_sequence = auth_sequence
        self._user_stop     = False     # UI 스레드에서 set, BFS가 read

    def request_stop(self) -> None:
        """협력적 중단 요청 (BFS 다음 페이지 시작 전 체크됨)."""
        self._user_stop = True

    def run(self) -> None:
        try:
            from app.core.stage0_url_collect import collect_urls
            urls = collect_urls(
                start_url=self._start_url,
                max_pages=self._max_pages,
                max_depth=self._max_depth,
                auth_sequence=self._auth_sequence,
                progress_cb=self.progress.emit,
                should_stop=lambda: self._user_stop,
            )
            self.finished_ok.emit(urls)
        except Exception as e:
            import traceback
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")


# ── 메인 다이얼로그 ─────────────────────────────────────────────────────────
class PagePickerDialog(QDialog):
    """선택된 URL과 캐시 features를 반환."""

    def __init__(
        self,
        start_url: str,
        auth_sequence: list[dict] | None = None,
        exclude_run_id: str | None = None,
        default_max_pages: int = 30,
        default_max_depth: int = 3,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("페이지 선택 — 분석할 페이지를 고르세요")
        self.resize(900, 640)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self._start_url     = start_url
        self._auth_sequence = auth_sequence or []
        self._exclude_run_id = exclude_run_id

        # 결과
        self._urls: list[dict] = []
        self._cached_features: dict[str, list[dict]] = {}
        self._cache_run_dir: Path | None = None

        # 노출용 결과
        self.selected_urls: list[str] = []
        self.selected_cache: dict[str, list[dict]] = {}
        self.selected_groups: dict[str, list[str]] = {}   # 대표URL → 동형 멤버 (L4)

        self._worker: _CollectWorker | None = None
        self._build_ui(default_max_pages, default_max_depth)

    # ── UI ───────────────────────────────────────────────────────────────
    def _build_ui(self, max_pages: int, max_depth: int) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # 상단 안내
        hdr = QLabel(
            f"<b style='font-size:14px; color:#1e293b;'>대상 URL :</b> "
            f"<span style='color:#475569;'>{self._start_url}</span>"
        )
        root.addWidget(hdr)

        hint = QLabel(
            "🔍  설정을 확인하고 <b>'URL 수집 시작'</b>을 누르면 시작 URL에서 같은 사이트 내의 페이지를 자동으로 찾습니다.  "
            "수집 후 분석할 페이지를 체크하세요. ♻ 표시는 과거 분석 결과를 재사용하여 시간을 절약합니다."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "QLabel { background:#e8f4fd; color:#0066cc; padding:8px;"
            " border-radius:4px; font-size:12px; }"
        )
        hint.setTextFormat(Qt.RichText)
        root.addWidget(hint)

        # 옵션 행 (탐색 깊이 + 시작/중단)
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)

        depth_lbl = QLabel("탐색 깊이:")
        _depth_tip = (
            "링크를 따라가는 'BFS 확산 단계'입니다.\n"
            "  ※ 사용자가 클릭하는 횟수가 아닙니다 — 각 페이지의 '모든 링크'를\n"
            "     동시에 펼칩니다. 대부분의 사이트는 모든 페이지에 같은 메뉴(헤더/\n"
            "     푸터)가 있어, 사용자가 4~5번 클릭해 가는 페이지도 보통 1~2단계로 잡힙니다.\n\n"
            "  0 = 시작 페이지만\n"
            "  1 = 시작 페이지 + 메뉴 등 직접 링크된 페이지\n"
            "  2 = 위 + 그 페이지들의 링크\n"
            "  3 = 메뉴에 없는 깊은 계층까지 (기본·권장)\n"
            "  4~5 = 매우 큰 사이트 — 수집 시간 증가\n\n"
            "주의: 결제 단계처럼 '버튼/폼 제출'로만 이동하는 페이지는\n"
            "      깊이를 올려도 못 찾습니다(BFS는 <a> 링크만 따라감).\n"
            "참고: 페이지 수 제한 없음 (자연 종료, 안전 상한 500)."
        )
        depth_lbl.setToolTip(_depth_tip)
        opt_row.addWidget(depth_lbl)
        self._max_depth_spin = QSpinBox()
        self._max_depth_spin.setRange(0, 5)
        self._max_depth_spin.setValue(max_depth)
        self._max_depth_spin.setFixedWidth(60)
        self._max_depth_spin.setToolTip(_depth_tip)
        opt_row.addWidget(self._max_depth_spin)

        depth_inline = QLabel(
            "  (클릭 횟수 아님 · 메뉴 경유라 보통 충분 · 3=권장)"
        )
        depth_inline.setStyleSheet("QLabel { color:#94a3b8; font-size:11px; }")
        depth_inline.setToolTip(_depth_tip)
        opt_row.addWidget(depth_inline)

        opt_row.addStretch()

        self._collect_btn = QPushButton("URL 수집 시작")
        self._collect_btn.setMinimumWidth(120)
        self._collect_btn.setStyleSheet(
            "QPushButton { background:#3b82f6; color:#ffffff;"
            " border:none; border-radius:6px;"
            " padding:6px 16px; font-size:13px; font-weight:600; }"
            "QPushButton:hover { background:#2563eb; }"
            "QPushButton:disabled { background:#cbd5e1; }"
        )
        self._collect_btn.clicked.connect(self._start_collect)
        opt_row.addWidget(self._collect_btn)

        self._stop_btn = QPushButton("⏹  중단")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(
            "QPushButton { background:#ffffff; color:#dc2626;"
            " border:1px solid #fca5a5; border-radius:6px;"
            " padding:6px 14px; font-size:12px; font-weight:600; }"
            "QPushButton:hover:enabled { background:#fee2e2; }"
            "QPushButton:disabled { color:#cbd5e1; border-color:#e2e8f0; }"
        )
        self._stop_btn.clicked.connect(self._stop_collect)
        opt_row.addWidget(self._stop_btn)

        root.addLayout(opt_row)

        # 진행률
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        root.addWidget(self._progress)

        # 진행 메시지 라벨
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("QLabel { color:#64748b; font-size:11px; }")
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        # 일괄 선택 버튼들
        bulk_row = QHBoxLayout()
        bulk_row.setSpacing(6)
        for label, handler in [
            ("전체 선택",    self._select_all),
            ("선택 해제",    self._deselect_all),
            ("캐시만 선택",   self._select_cached_only),
            ("미캐시만 선택", self._select_uncached_only),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.clicked.connect(handler)
            bulk_row.addWidget(b)
        # 동형(중복) 페이지 숨기기 토글
        self._hide_dup_cb = QCheckBox("동형 페이지 숨기기 (대표만 표시)")
        self._hide_dup_cb.setChecked(True)   # 기본: 대표만 보여 깔끔하게
        self._hide_dup_cb.setToolTip(
            "체크: 구조가 같은 동형 페이지는 대표 1개만 표시 (권장)\n"
            "해제: 묶인 동형 페이지도 모두 표시 (개별 선택 가능)"
        )
        self._hide_dup_cb.toggled.connect(self._populate_table)
        bulk_row.addWidget(self._hide_dup_cb)

        bulk_row.addStretch()

        self._count_lbl = QLabel("선택: 0 / 0")
        self._count_lbl.setStyleSheet(
            "QLabel { background:#f1f5f9; color:#1e293b;"
            " border:1px solid #e2e8f0; border-radius:4px;"
            " padding:4px 10px; font-weight:600; font-size:12px; }"
        )
        bulk_row.addWidget(self._count_lbl)
        root.addLayout(bulk_row)

        # 테이블 (동형 열 추가 → 6열)
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["선택", "URL", "제목", "깊이", "동형", "캐시"]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 48)
        self._table.setColumnWidth(2, 220)
        self._table.setColumnWidth(3, 50)
        self._table.setColumnWidth(4, 90)
        self._table.setColumnWidth(5, 80)
        self._table.itemChanged.connect(self._on_item_changed)

        # shift+click 체크박스 범위 선택용 — 마지막 클릭 row 추적
        self._last_check_row: int = -1
        root.addWidget(self._table, 1)

        # 하단 버튼
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("✅  DOM 분석 시작")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self._on_accept)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._ok_btn)
        root.addLayout(btn_row)

        # 초기 안내 — 자동 시작하지 않고 사용자 클릭 대기
        self._status_lbl.setText(
            "위 '탐색 깊이'를 설정한 뒤 'URL 수집 시작' 버튼을 누르세요."
        )

    # ── BFS 워커 시작/중단 ────────────────────────────────────────────────
    def _start_collect(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._collect_btn.setEnabled(False)
        self._max_depth_spin.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._progress.setVisible(True)
        self._table.setRowCount(0)
        self._urls = []
        self._cached_features = {}
        self._cache_run_dir = None
        self._refresh_count()
        self._ok_btn.setEnabled(False)

        self._worker = _CollectWorker(
            start_url=self._start_url,
            max_pages=500,                              # 안전 상한 — 사용자 노출 X
            max_depth=self._max_depth_spin.value(),
            auth_sequence=self._auth_sequence,
            parent=self,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_collect_done)
        self._worker.error.connect(self._on_collect_error)
        self._worker.start()

    def _stop_collect(self) -> None:
        """협력적 중단 — BFS 워커가 다음 페이지 시작 전 체크해서 종료."""
        if self._worker and self._worker.isRunning():
            self._status_lbl.setText("중단 요청됨 — 현재 페이지 완료 후 종료됩니다…")
            self._worker.request_stop()
        # 사용자가 한 번만 누르면 되도록 비활성
        self._stop_btn.setEnabled(False)

    def _on_progress(self, msg: str) -> None:
        self._status_lbl.setText(msg)

    def _on_collect_done(self, urls: list[dict]) -> None:
        self._urls = urls or []
        self._collect_btn.setEnabled(True)
        self._collect_btn.setText("URL 다시 수집")
        self._max_depth_spin.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)

        # 캐시 검색
        from app.core.dom_cache import cache_status_for_urls
        cache_map, cache_run = cache_status_for_urls(
            target_url=self._start_url,
            page_urls=[u["url"] for u in self._urls],
            exclude_run_id=self._exclude_run_id,
        )
        self._cached_features = cache_map
        self._cache_run_dir    = cache_run

        self._populate_table()

        # 그룹(고유 기능) 수 = 대표 페이지 수
        n_total  = len(self._urls)
        n_groups = sum(1 for u in self._urls if u.get("is_representative", True))
        n_dup    = n_total - n_groups
        msg = f"URL 수집 완료 — {n_total}개 발견"
        if n_dup > 0:
            msg += f"  →  고유 기능 {n_groups}개 (동형/변형 {n_dup}개 묶음)"
        if cache_run:
            msg += f"  |  ♻ 캐시 {len(cache_map)}개 (소스: {cache_run.name})"
        self._status_lbl.setText(msg)
        self._ok_btn.setEnabled(bool(self._urls))

    def _on_collect_error(self, err: str) -> None:
        self._collect_btn.setEnabled(True)
        self._max_depth_spin.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_lbl.setText("URL 수집 실패")
        QMessageBox.critical(self, "URL 수집 오류", err[:1000])

    # ── 테이블 ──────────────────────────────────────────────────────────
    def _populate_table(self) -> None:
        hide_dup = self._hide_dup_cb.isChecked()
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for entry in self._urls:
                is_rep      = entry.get("is_representative", True)
                group_size  = entry.get("group_size", 1)
                # 동형 숨기기 모드: 대표만 표시 (그룹 크기 1인 단독 페이지는 항상 표시)
                if hide_dup and not is_rep:
                    continue

                url   = entry["url"]
                title = entry["title"]
                depth = entry["depth"]
                has_cache = url in self._cached_features

                r = self._table.rowCount()
                self._table.insertRow(r)

                # 0: 체크박스 — 대표는 자동 체크, 동형(비대표)은 해제
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                chk.setCheckState(Qt.Checked if is_rep else Qt.Unchecked)
                chk.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(r, 0, chk)

                # 1: URL
                url_item = QTableWidgetItem(url)
                if not is_rep:
                    url_item.setForeground(Qt.gray)
                self._table.setItem(r, 1, url_item)
                # 2: 제목
                self._table.setItem(r, 2, QTableWidgetItem(title))
                # 3: 깊이
                d_item = QTableWidgetItem(str(depth))
                d_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(r, 3, d_item)
                # 4: 동형 — 대표면 "대표 +N", 비대표면 "↳ 동형"
                if group_size > 1 and is_rep:
                    grp_item = QTableWidgetItem(f"대표 +{group_size - 1}")
                    grp_item.setForeground(Qt.blue)
                    grp_item.setToolTip(
                        f"구조가 같은 동형 페이지 {group_size}개를 대표합니다.\n"
                        "이 1개만 분석하면 동형 페이지 전체에 TC가 적용됩니다."
                    )
                elif not is_rep:
                    grp_item = QTableWidgetItem("↳ 동형")
                    grp_item.setForeground(Qt.gray)
                    grp_item.setToolTip(f"대표: {entry.get('group_rep_url','')}")
                else:
                    grp_item = QTableWidgetItem("—")
                    grp_item.setForeground(Qt.gray)
                grp_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(r, 4, grp_item)
                # 5: 캐시
                if has_cache:
                    n_feats = len(self._cached_features[url])
                    cache_item = QTableWidgetItem(f"♻ {n_feats}개")
                    cache_item.setForeground(Qt.darkGreen)
                else:
                    cache_item = QTableWidgetItem("—")
                    cache_item.setForeground(Qt.gray)
                cache_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(r, 5, cache_item)
        finally:
            self._table.blockSignals(False)
        self._refresh_count()

    def _on_item_changed(self, item) -> None:
        """체크박스 변경 핸들러 — shift 누르고 클릭 시 범위 다중 선택."""
        if item is None or item.column() != 0:
            self._refresh_count()
            return

        row = item.row()
        target_state = item.checkState()

        # Shift 키 + 이전 클릭이 있으면 범위 선택 (이전 다른 체크는 유지)
        mods = QApplication.keyboardModifiers()
        if (
            (mods & Qt.ShiftModifier)
            and self._last_check_row >= 0
            and self._last_check_row != row
        ):
            lo, hi = sorted([self._last_check_row, row])
            self._table.blockSignals(True)
            try:
                for r in range(lo, hi + 1):
                    if r == row:
                        continue   # 이미 변경됨
                    chk = self._table.item(r, 0)
                    if chk is not None:
                        chk.setCheckState(target_state)
            finally:
                self._table.blockSignals(False)

        self._last_check_row = row
        self._refresh_count()

    def _refresh_count(self) -> None:
        total = self._table.rowCount()
        sel = sum(
            1 for r in range(total)
            if self._table.item(r, 0) and self._table.item(r, 0).checkState() == Qt.Checked
        )
        n_cache = sum(
            1 for r in range(total)
            if self._table.item(r, 0)
            and self._table.item(r, 0).checkState() == Qt.Checked
            and self._table.item(r, 1)
            and self._table.item(r, 1).text() in self._cached_features
        )
        n_llm = sel - n_cache
        self._count_lbl.setText(
            f"선택: {sel} / {total}  |  ♻ 캐시 {n_cache}  +  🆕 LLM {n_llm}"
        )

    # ── 일괄 선택 ────────────────────────────────────────────────────────
    def _set_all_checks(self, predicate) -> None:
        self._table.blockSignals(True)
        try:
            for r in range(self._table.rowCount()):
                url_item = self._table.item(r, 1)
                if not url_item:
                    continue
                state = Qt.Checked if predicate(url_item.text()) else Qt.Unchecked
                self._table.item(r, 0).setCheckState(state)
        finally:
            self._table.blockSignals(False)
        self._refresh_count()

    def _select_all(self) -> None:
        self._set_all_checks(lambda u: True)

    def _deselect_all(self) -> None:
        self._set_all_checks(lambda u: False)

    def _select_cached_only(self) -> None:
        self._set_all_checks(lambda u: u in self._cached_features)

    def _select_uncached_only(self) -> None:
        self._set_all_checks(lambda u: u not in self._cached_features)

    # ── 확인 ────────────────────────────────────────────────────────────
    def _on_accept(self) -> None:
        sel_urls: list[str] = []
        for r in range(self._table.rowCount()):
            chk = self._table.item(r, 0)
            url_item = self._table.item(r, 1)
            if chk and url_item and chk.checkState() == Qt.Checked:
                sel_urls.append(url_item.text())

        if not sel_urls:
            QMessageBox.warning(self, "선택 없음", "최소 1개 페이지를 선택하세요.")
            return

        self.selected_urls  = sel_urls
        self.selected_cache = {
            u: self._cached_features[u]
            for u in sel_urls if u in self._cached_features
        }
        # L4 추적성: 선택된 대표 URL → 묶인 동형 URL 목록 (meta.json 기록용)
        sel_set = set(sel_urls)
        groups: dict[str, list[str]] = {}
        for e in self._urls:
            rep = e.get("group_rep_url", e["url"])
            if rep in sel_set and e.get("group_size", 1) > 1:
                groups.setdefault(rep, [])
                if not e.get("is_representative", True):
                    groups[rep].append(e["url"])
        # 동형이 실제로 묶인 그룹만 (멤버 1개 이상)
        self.selected_groups = {k: v for k, v in groups.items() if v}
        self.accept()

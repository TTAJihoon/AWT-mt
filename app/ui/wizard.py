"""새 실행 마법사 (Step 1: URL·파일, Step 2: Auth, Step 3: 옵션) (D45: PySide6)."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QStackedWidget, QWidget, QCheckBox,
    QMessageBox, QGroupBox, QComboBox, QScrollArea,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEnginePage
    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

from app.config.settings import get_active_provider
from app.core.orchestrator import RunConfig


# ── JS 셀렉터 피커 (페이지 로드 후 주입) ──────────────────────────────────────
_PICKER_JS = r"""
(function() {
    if (window.__AWT_PICKER_ACTIVE__) return;
    window.__AWT_PICKER_ACTIVE__ = true;

    var _hl = null, _done = false;

    function _setHover(el, on) {
        if (on) {
            el.__awt_orig_outline = el.style.outline;
            el.__awt_orig_cursor  = el.style.cursor;
            el.style.outline = '3px solid #0066cc';
            el.style.cursor  = 'crosshair';
        } else {
            el.style.outline = el.__awt_orig_outline || '';
            el.style.cursor  = el.__awt_orig_cursor  || '';
        }
    }

    /* CSS 선택자 생성 (우선순위: id → name → placeholder → type → 경로) */
    function getSelector(el) {
        if (el.id) return '#' + el.id;
        var n = el.getAttribute('name');
        if (n) return '[name="' + n.replace(/\\/g,'\\\\').replace(/"/g,'\\"') + '"]';
        var ph = el.getAttribute('placeholder');
        if (ph) return '[placeholder="' + ph.replace(/\\/g,'\\\\').replace(/"/g,'\\"').slice(0,50) + '"]';
        var t = el.getAttribute('type');
        if (t && t !== 'text') return el.tagName.toLowerCase() + '[type="' + t + '"]';
        /* 경로 기반 */
        var path = [], cur = el;
        while (cur && cur !== document.body && cur.tagName) {
            var tag = cur.tagName.toLowerCase();
            var par = cur.parentElement;
            if (par) {
                var sibs = [].filter.call(par.children, function(c){ return c.tagName === cur.tagName; });
                if (sibs.length > 1)
                    path.unshift(tag + ':nth-of-type(' + ([].indexOf.call(sibs, cur) + 1) + ')');
                else
                    path.unshift(tag);
            } else { path.unshift(tag); }
            cur = par;
        }
        return path.join(' > ');
    }

    function getText(el) {
        return (el.getAttribute('placeholder') || el.getAttribute('aria-label') ||
                el.value || el.textContent || '').trim().slice(0, 60);
    }

    document.addEventListener('mouseover', function(e) {
        if (_done) return;
        if (_hl && _hl !== e.target) { _setHover(_hl, false); _hl = null; }
        _hl = e.target;
        _setHover(_hl, true);
    }, true);

    document.addEventListener('mouseout', function(e) {
        if (_done || _hl !== e.target) return;
        _setHover(_hl, false);
        _hl = null;
    }, true);

    document.addEventListener('click', function(e) {
        if (_done) return;
        e.preventDefault();
        e.stopPropagation();
        _done = true;
        var el = e.target;
        if (_hl) { _setHover(_hl, false); el.style.outline = '3px solid #00aa44'; }
        var sel = getSelector(el);
        var txt = getText(el);

        /* 확인 배너 */
        var b = document.createElement('div');
        b.style.cssText = 'position:fixed;top:0;left:0;right:0;background:#00aa44;color:#fff;' +
            'padding:10px 16px;font-size:13px;z-index:2147483647;font-family:sans-serif;';
        b.textContent = '✅ 선택됨: ' + sel;
        document.body.appendChild(b);

        console.log('__AWT_SEL__:' + sel + '|||' + txt);
    }, true);

    /* 하단 안내 배너 */
    var hint = document.createElement('div');
    hint.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);' +
        'background:rgba(0,102,204,0.92);color:#fff;padding:10px 24px;border-radius:24px;' +
        'font-size:13px;z-index:2147483647;font-family:sans-serif;pointer-events:none;' +
        'box-shadow:0 2px 10px rgba(0,0,0,0.3);';
    hint.textContent = '🎯  원하는 요소를 클릭하세요';
    document.body.appendChild(hint);
})();
"""

# ── WebEngine 의존 클래스 (QtWebEngine 설치 시에만 정의) ───────────────────────
if _HAS_WEBENGINE:

    class _SelectorPage(QWebEnginePage):
        """console.log 메시지를 가로채 CSS 선택자를 Python Signal로 전달."""

        selector_captured = Signal(str, str)   # (selector, display_text)

        def javaScriptConsoleMessage(
            self, level, message: str, line: int, source: str
        ) -> None:
            if message.startswith("__AWT_SEL__:"):
                payload = message[len("__AWT_SEL__:"):]
                parts   = payload.split("|||", 1)
                sel     = parts[0].strip()
                txt     = parts[1].strip() if len(parts) > 1 else ""
                self.selector_captured.emit(sel, txt)

    class SelectorPickerDialog(QDialog):
        """내장 브라우저로 URL을 열고, 사용자가 클릭한 요소의 CSS 선택자를 캡처."""

        def __init__(self, url: str, parent=None):
            super().__init__(parent)
            self.setWindowTitle("요소 선택 — 원하는 입력란을 클릭하세요")
            self.setMinimumSize(1100, 720)
            self.resize(1200, 760)
            self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
            self._selector: str = ""
            self._build_ui(url)

        def _build_ui(self, url: str) -> None:
            lay = QVBoxLayout(self)
            lay.setSpacing(8)

            # 안내
            hint_lbl = QLabel(
                "🎯  원하는 입력 칸 위에 마우스를 올리면 파란 테두리가 표시됩니다. "
                "클릭하면 선택자가 자동으로 입력됩니다."
            )
            hint_lbl.setWordWrap(True)
            hint_lbl.setStyleSheet(
                "background:#e8f4fd; color:#0066cc; padding:8px; "
                "border-radius:4px; font-size:12px;"
            )
            lay.addWidget(hint_lbl)

            # 선택된 선택자 표시줄
            sel_row = QHBoxLayout()
            sel_row.addWidget(QLabel("선택된 선택자:"))
            self._sel_edit = QLineEdit()
            self._sel_edit.setReadOnly(True)
            self._sel_edit.setPlaceholderText("아직 선택되지 않음")
            sel_row.addWidget(self._sel_edit, 1)
            lay.addLayout(sel_row)

            # 내장 브라우저
            self._page = _SelectorPage()
            self._page.selector_captured.connect(self._on_selector)
            self._view = QWebEngineView()
            self._view.setPage(self._page)
            self._view.loadFinished.connect(self._on_load_finished)
            self._view.load(QUrl(url))
            lay.addWidget(self._view, 1)

            # 버튼
            btn_row = QHBoxLayout()
            cancel_btn = QPushButton("취소")
            cancel_btn.clicked.connect(self.reject)
            self._ok_btn = QPushButton("✅  이 선택자로 사용")
            self._ok_btn.setEnabled(False)
            self._ok_btn.clicked.connect(self.accept)
            btn_row.addStretch()
            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(self._ok_btn)
            lay.addLayout(btn_row)

        def _on_load_finished(self, ok: bool) -> None:
            if ok:
                self._view.page().runJavaScript(_PICKER_JS)

        def _on_selector(self, selector: str, text: str) -> None:
            self._selector = selector
            display = f"{selector}  ← {text}" if text else selector
            self._sel_edit.setText(display)
            self._sel_edit.setStyleSheet(
                "background:#e8ffe8; color:#006600; font-family: monospace;"
            )
            self._ok_btn.setEnabled(True)

        def selected_selector(self) -> str:
            return self._selector


# ── 모델 목록 ─────────────────────────────────────────────────────────────────
_MODELS: dict[str, list[tuple[str, str]]] = {
    "google": [
        # ── 무료 티어 있음 ──────────────────────────────────────────────
        ("gemini-2.5-flash",      "[무료] Gemini 2.5 Flash  — $0.30/$2.50/M  (추천)"),
        ("gemini-2.5-flash-lite", "[무료] Gemini 2.5 Flash Lite  — $0.10/$0.40/M  (저비용)"),
        ("gemini-2.5-pro",        "[무료] Gemini 2.5 Pro  — $1.25/$10.00/M  (고성능)"),
        # ── 유료 전용 ───────────────────────────────────────────────────
        ("gemini-3.1-flash-lite",  "[유료] Gemini 3.1 Flash Lite  — $0.25/$1.50/M"),
        ("gemini-3.5-flash",       "[유료] Gemini 3.5 Flash  — $1.50/$9.00/M"),
        ("gemini-3.1-pro-preview", "[유료] Gemini 3.1 Pro Preview  — $2.00/$12.00/M"),
        # ── 테스트 / 오픈소스 ────────────────────────────────────────────
        ("gemma-4-26b-a4b-it",     "[테스트] Gemma 4 26B  (gemma-4-26b-a4b-it)"),
    ],
    "anthropic": [
        # ── 유료 전용 (무료 API 티어 없음) ─────────────────────────────
        ("claude-haiku-4-5",   "[유료] Claude Haiku 4.5  — $1/$5/M  (저비용)"),
        ("claude-sonnet-4-6",  "[유료] Claude Sonnet 4.6  — $3/$15/M  (추천)"),
        ("claude-opus-4-7",    "[유료] Claude Opus 4.7  — $5/$25/M  (고성능)"),
    ],
    "openai": [
        # ── GPT-5 계열 (유료 전용, 가격: Input/Output per 1M tokens) ──────
        ("gpt-5.5",      "[유료] GPT-5.5  — $5.00/$30.00/M  (최신·고성능, 추천)"),
        ("gpt-5.5-pro",  "[유료] GPT-5.5 Pro  — $30.00/$180.00/M  (최고성능)"),
        ("gpt-5.4",      "[유료] GPT-5.4  — $2.50/$15.00/M  (균형)"),
        ("gpt-5.4-mini", "[유료] GPT-5.4 Mini  — $0.75/$4.50/M  (저비용)"),
        ("gpt-5.4-nano", "[유료] GPT-5.4 Nano  — $0.20/$1.25/M  (최저비용)"),
        ("gpt-5.4-pro",  "[유료] GPT-5.4 Pro  — $30.00/$180.00/M  (고성능)"),
        # ── GPT-4 계열 (구형, 호환용) ───────────────────────────────────
        ("gpt-4.1-nano", "[유료] GPT-4.1 Nano  — $0.10/$0.40/M  (구형·저비용)"),
        ("gpt-4o-mini",  "[유료] GPT-4o Mini  — $0.15/$0.60/M  (구형·균형)"),
        ("gpt-4o",       "[유료] GPT-4o  — $2.50/$10.00/M  (구형·고성능)"),
    ],
}


class RunWizard(QDialog):
    """3단계 마법사. run_config_ready(RunConfig) 시그널로 설정 전달."""

    run_config_ready = Signal(object)  # RunConfig

    def __init__(self, api_key: str, prefill_url: str = "",
                 prefill_config: dict | None = None, parent=None):
        """
        Args:
            prefill_config: 복제 시 모든 스텝 값을 채우기 위한 설정 dict
                (meta.json 형식: target_url / input_files / auth_sequence /
                 model_override / inferred_threshold / max_leaves /
                 headless_exec / slow_mo_ms). None이면 빈 마법사.
        """
        super().__init__(parent)
        self.setWindowTitle("새 실행 — 설정 마법사")
        # 고정 크기는 내용이 넘칠 때 위젯이 겹친다 → 리사이즈 가능 + 충분한 기본 크기.
        self.setMinimumSize(720, 560)
        self.resize(760, 720)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self._api_key = api_key
        self._auth_rows: list[dict] = []
        self._build_ui()
        # 복제 시 URL 자동 입력
        if prefill_url:
            self._url_edit.setText(prefill_url)
        # 복제 시 전체 스텝 값 채우기
        if prefill_config:
            self._apply_prefill(prefill_config)

    # ── UI ────────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 단계 표시
        self._step_lbl = QLabel("Step 1 / 3")
        self._step_lbl.setStyleSheet(
            "font-weight:600; color:#0066cc; font-size:12px; letter-spacing:0.5px;"
        )
        root.addWidget(self._step_lbl)

        # 스택 — 각 페이지를 스크롤 영역으로 감싸 내용이 넘쳐도 겹치지 않게 함
        self._stack = QStackedWidget()
        self._stack.addWidget(self._scroll(self._page1()))
        self._stack.addWidget(self._scroll(self._page2()))
        self._stack.addWidget(self._scroll(self._page3()))
        root.addWidget(self._stack, 1)

        # 버튼
        btn_row = QHBoxLayout()
        self._back_btn = QPushButton("← 이전")
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._go_back)
        self._next_btn = QPushButton("다음 →")
        self._next_btn.clicked.connect(self._go_next)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._back_btn)
        btn_row.addWidget(self._next_btn)
        root.addLayout(btn_row)

    def _scroll(self, inner: QWidget) -> QScrollArea:
        """페이지를 스크롤 영역으로 감싼다 — 내용이 창보다 길어도 겹치지 않고 스크롤."""
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        sa.setWidget(inner)
        return sa

    def _page1(self) -> QWidget:
        """대상 유형 선택 + 유형별 입력 + 요구사항 파일 (D59·D67)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        lay.addWidget(QLabel("<b>Step 1: 시험 대상 선택 및 입력</b>"))

        # ── 대상 유형 선택 (D59) ──────────────────────────────────────────
        kind_box = QGroupBox("시험 대상 유형")
        kind_lay = QVBoxLayout(kind_box)
        self._target_kind_combo = QComboBox()
        self._target_kind_combo.addItem("웹 (DOM/Playwright)", "web")
        self._target_kind_combo.addItem("REST API (OpenAPI)", "api_rest")
        self._target_kind_combo.addItem("로컬 코드 라이브러리", "api_code")
        self._target_kind_combo.addItem("Windows 실행프로그램 (UIA)", "gui")
        self._target_kind_combo.currentIndexChanged.connect(self._on_target_kind_changed)
        kind_lay.addWidget(self._target_kind_combo)
        lay.addWidget(kind_box)

        # ── 유형별 입력 스택 ──────────────────────────────────────────────
        self._target_stack = self._build_target_pages()
        lay.addWidget(self._target_stack)

        # ── 웹 URL (web 전용 — 다른 유형이면 숨김) ─────────────────────────
        self._url_box = QGroupBox("대상 웹 URL")
        self._url_box.setToolTip(
            "AI가 자동으로 분석할 웹사이트의 시작 URL입니다.\n"
            "  • 같은 origin(스킴+호스트)의 페이지를 BFS로 따라가며 분석\n"
            "  • 로그인 후 접근 가능한 페이지가 있으면 Step 2에서 인증 설정\n\n"
            "예: http://localhost:8080  ·  https://demo.example.com/app"
        )
        url_lay = QVBoxLayout(self._url_box)
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://example.com")
        self._url_edit.setToolTip(self._url_box.toolTip())
        url_lay.addWidget(self._url_edit)
        lay.addWidget(self._url_box)

        file_box = QGroupBox("요구사항 파일/매뉴얼/스펙 (PDF / DOCX / XLSX / MD, 복수 선택 가능)")
        file_lay = QVBoxLayout(file_box)
        self._file_list = QListWidget()
        self._file_list.setFixedHeight(120)
        file_lay.addWidget(self._file_list)
        add_btn = QPushButton("파일 추가…")
        add_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton("선택 제거")
        remove_btn.clicked.connect(self._remove_file)
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        file_lay.addLayout(btn_row)
        lay.addWidget(file_box)

        self._skip_stage0_cb = QCheckBox("Stage 0 스캔 건너뜀 (파일/스펙만 사용)")
        lay.addWidget(self._skip_stage0_cb)
        lay.addStretch()
        return w

    # ── 유형별 입력 스택 (D59) ────────────────────────────────────────────
    def _build_target_pages(self) -> QStackedWidget:
        stack = QStackedWidget()

        # 0: web — 안내만 (실제 입력은 아래 URL/파일 박스)
        web = QWidget(); wl = QVBoxLayout(web)
        wl.addWidget(QLabel("아래 ‘대상 웹 URL’과 파일을 입력하세요."))
        wl.addStretch(); stack.addWidget(web)

        # 1: api_rest
        rest = QGroupBox("REST API (OpenAPI) 입력"); rl = QVBoxLayout(rest)
        self._rest_openapi = QLineEdit(); self._rest_openapi.setPlaceholderText(
            "OpenAPI 스펙 경로 또는 URL (openapi.json / .yaml)")
        self._rest_base = QLineEdit(); self._rest_base.setPlaceholderText(
            "base_url (예: https://api.example.com)  — 비우면 스펙 servers 사용")
        self._rest_token = QLineEdit(); self._rest_token.setPlaceholderText(
            "Bearer 토큰 (선택)")
        for lb, ed in (("OpenAPI 스펙", self._rest_openapi),
                       ("Base URL", self._rest_base),
                       ("인증 토큰(Bearer, 선택)", self._rest_token)):
            rl.addWidget(QLabel(lb)); rl.addWidget(ed)
        rl.addStretch(); stack.addWidget(rest)

        # 2: api_code
        code = QGroupBox("로컬 코드 라이브러리 입력"); cl = QVBoxLayout(code)
        self._code_lang = QComboBox()
        for label, data in (("Python", "python"), (".NET (C#)", "dotnet"),
                            ("Java", "java"), ("C/네이티브 DLL", "c")):
            self._code_lang.addItem(label, data)
        self._code_module = QLineEdit(); self._code_module.setPlaceholderText(
            "모듈 경로(.py) / DLL 경로 / classpath(.jar)")
        self._code_extra = QLineEdit(); self._code_extra.setPlaceholderText(
            "Java=클래스 FQN(콤마 구분) / C=시그니처 JSON 경로")
        cl.addWidget(QLabel("언어")); cl.addWidget(self._code_lang)
        cl.addWidget(QLabel("모듈/DLL/classpath 경로")); cl.addWidget(self._code_module)
        cl.addWidget(QLabel("추가(Java 클래스 / C 시그니처)")); cl.addWidget(self._code_extra)
        cl.addStretch(); stack.addWidget(code)

        # 3: gui
        gui = QGroupBox("Windows 실행프로그램 입력"); gl = QVBoxLayout(gui)
        self._gui_exe = QLineEdit(); self._gui_exe.setPlaceholderText("실행 파일 경로 (.exe)")
        self._gui_args = QLineEdit(); self._gui_args.setPlaceholderText("실행 인자 (공백 구분, 선택)")
        self._gui_window = QLineEdit(); self._gui_window.setPlaceholderText(
            "메인 윈도우 제목 정규식 (선택)")
        for lb, ed in (("실행 파일", self._gui_exe), ("실행 인자", self._gui_args),
                       ("윈도우 제목", self._gui_window)):
            gl.addWidget(QLabel(lb)); gl.addWidget(ed)
        gl.addStretch(); stack.addWidget(gui)

        stack.setCurrentIndex(0)
        return stack

    def _on_target_kind_changed(self, idx: int) -> None:
        self._target_stack.setCurrentIndex(idx)
        # web(0)만 URL 박스 노출
        if hasattr(self, "_url_box"):
            self._url_box.setVisible(idx == 0)

    def _build_target_config(self) -> dict:
        """현재 선택된 대상 유형의 입력을 target_config dict로."""
        kind = self._target_kind_combo.currentData()
        if kind == "api_rest":
            spec = self._rest_openapi.text().strip()
            cfg: dict = {}
            if spec.lower().startswith("http"):
                cfg["openapi_url"] = spec
            elif spec:
                cfg["openapi_path"] = spec
            base = self._rest_base.text().strip()
            if base:
                cfg["base_url"] = base
            tok = self._rest_token.text().strip()
            if tok:
                cfg["auth"] = {"type": "bearer", "token": tok}
            return cfg
        if kind == "api_code":
            lang = self._code_lang.currentData()
            mod = self._code_module.text().strip()
            extra = self._code_extra.text().strip()
            cfg = {"lang": lang}
            if lang == "python":
                cfg["module_path"] = mod
            elif lang == "dotnet":
                cfg["dll_path"] = mod
            elif lang == "java":
                cfg["classpath"] = mod
                if extra:
                    cfg["classes"] = [c.strip() for c in extra.split(",") if c.strip()]
            elif lang == "c":
                cfg["dll_path"] = mod
                if extra:
                    cfg["signatures_path"] = extra
            return cfg
        if kind == "gui":
            cfg = {"exe_path": self._gui_exe.text().strip()}
            args = self._gui_args.text().strip()
            if args:
                cfg["args"] = args.split()
            wt = self._gui_window.text().strip()
            if wt:
                cfg["window_title"] = wt
            return cfg
        return {}

    def _page2(self) -> QWidget:
        """인증 시퀀스 설정."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        lay.addWidget(QLabel("<b>Step 2: 인증 시퀀스 (선택)</b>"))

        # 액션 설명
        desc_lbl = QLabel(
            "로그인이 필요한 경우 아래에 단계를 추가하세요.\n"
            "  • goto — URL 이동    • fill — 값 입력    • click — 요소 클릭"
        )
        desc_lbl.setStyleSheet("color:#555; font-size:11px;")
        lay.addWidget(desc_lbl)

        # 셀렉터 피커 안내 (WebEngine 설치 시)
        if _HAS_WEBENGINE:
            picker_hint = QLabel(
                "🎯  selector 칸 오른쪽의 버튼을 누르면 브라우저 팝업이 열려 "
                "요소를 클릭하는 것만으로 선택자를 자동 입력할 수 있습니다."
            )
            picker_hint.setWordWrap(True)
            picker_hint.setStyleSheet(
                "background:#e8f4fd; color:#0055aa; padding:6px 8px; "
                "border-radius:4px; font-size:11px;"
            )
            lay.addWidget(picker_hint)

        # 인증 테이블 (4열: 동작 | selector/URL | value | 🎯)
        self._auth_table = QTableWidget(0, 4)
        self._auth_table.setObjectName("auth_table")
        self._auth_table.setHorizontalHeaderLabels(
            ["동작", "선택자 / URL", "값 (값 입력 전용)", ""]
        )
        # ① 너비를 먼저 지정한 뒤 ② Fixed 모드로 고정 (순서 중요)
        self._auth_table.setColumnWidth(0, 140)   # 한글 라벨이 들어가도록 충분히
        self._auth_table.setColumnWidth(2, 160)
        self._auth_table.setColumnWidth(3, 44)
        hh = self._auth_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        # resizeSection 으로 한 번 더 강제 (Fixed 고정 후에도 적용됨)
        hh.resizeSection(0, 140)
        hh.resizeSection(2, 160)
        hh.resizeSection(3, 44)
        vh = self._auth_table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(34)

        # ── APPLE_QSS 전역 스타일(pill 버튼, 큰 padding) 오버라이드 ────────────
        # 핵심: 테이블 내부에서만 적용되는 컴팩트 스타일
        self._auth_table.setStyleSheet(
            "QComboBox {"
            " min-height: 0px;"
            " padding: 2px 8px;"
            " border-radius: 4px;"
            " border: 1px solid #c5d4e8;"
            " background: #ffffff;"
            "}"
            "QComboBox::drop-down { width: 16px; border: none; }"
            "QPushButton {"
            " min-height: 0px;"
            " min-width: 0px;"
            " padding: 0px;"
            " border-radius: 4px;"
            " font-size: 14px;"
            "}"
            "QLineEdit {"
            " padding: 2px 6px;"
            " border-radius: 0px;"
            " border: 1px solid #3b82f6;"
            "}"
            "QTableWidget::item { padding: 2px 6px; }"
        )
        lay.addWidget(self._auth_table)

        row_btns = QHBoxLayout()
        add_row = QPushButton("행 추가")
        add_row.clicked.connect(self._add_auth_row)
        del_row = QPushButton("행 삭제")
        del_row.clicked.connect(self._del_auth_row)
        row_btns.addWidget(add_row)
        row_btns.addWidget(del_row)
        row_btns.addStretch()
        lay.addLayout(row_btns)
        lay.addStretch()
        return w

    def _page3(self) -> QWidget:
        """실행 옵션 (내용이 많아 스크롤 가능)."""
        from PySide6.QtWidgets import QScrollArea
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.addWidget(QLabel("<b>Step 3: 실행 옵션</b>"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        outer_lay.addWidget(scroll, 1)

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)
        scroll.setWidget(w)

        provider = get_active_provider()
        models = _MODELS.get(provider, [])

        # ── 모델 선택 (전역 기본) ────────────────────────────────────────
        model_box = QGroupBox("LLM 모델 (모든 단계 기본)")
        m_lay = QVBoxLayout(model_box)
        self._model_combo = QComboBox()
        for model_id, label in models:
            self._model_combo.addItem(label, userData=model_id)
        if not models:
            self._model_combo.addItem("(provider 미설정)", userData=None)
        m_lay.addWidget(self._model_combo)
        provider_hint = QLabel(f"현재 provider: {provider}")
        provider_hint.setStyleSheet("color:#888; font-size:11px;")
        m_lay.addWidget(provider_hint)
        lay.addWidget(model_box)

        # ── 단계별 모델 (선택) ───────────────────────────────────────────
        # 체크 시 단계마다 모델 따로 지정 — 대량 단계는 저가 모델, 품질 단계는 상위 모델
        self._stage_model_box = QGroupBox("단계별 모델 따로 지정 (선택 — 비용/품질 최적화)")
        self._stage_model_box.setCheckable(True)
        self._stage_model_box.setChecked(False)
        self._stage_model_box.setToolTip(
            "체크하면 파이프라인 단계마다 다른 모델을 쓸 수 있습니다.\n"
            "예) 대량 추출(DOM/통합)은 저가 nano, TC 설계는 상위 모델.\n"
            "각 항목 '(기본 모델)'은 위 전역 모델을 따릅니다."
        )
        sm_lay = QVBoxLayout(self._stage_model_box)
        # (contract_id, 표시명) — 비용 큰 순
        self._STAGE_CONTRACTS = [
            ("DOM_SPEC",            "① 웹 요소 분석 (Stage 0, 호출 多)"),
            ("FEATURE_CONSOLIDATE", "② 기능 통합 (Stage 1b, 호출 多)"),
            ("TC_DESIGN",           "③ TC 설계 (Stage 2, 품질 중요)"),
            ("TC_REGEN",            "④ TC 재작성 (Stage 3)"),
            ("FAILURE_ANALYSIS",    "⑤ 실패 원인 분석 (Stage 6)"),
            ("PATTERN_EXTRACT",     "⑥ 결함 패턴 추출 (Stage 6B)"),
        ]
        self._stage_model_combos: dict[str, QComboBox] = {}
        for cid, label in self._STAGE_CONTRACTS:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(260)
            lbl.setStyleSheet("font-size:11px; color:#374151;")
            row.addWidget(lbl)
            combo = QComboBox()
            combo.addItem("(기본 모델)", userData=None)
            for model_id, mlabel in models:
                # 콤보가 길어지지 않게 짧은 라벨 사용 (모델 ID 기준)
                combo.addItem(model_id, userData=model_id)
            combo.setStyleSheet("font-size:11px;")
            row.addWidget(combo, 1)
            sm_lay.addLayout(row)
            self._stage_model_combos[cid] = combo
        lay.addWidget(self._stage_model_box)

        # ── INFERRED 임계값 ──────────────────────────────────────────────
        thresh_box = QGroupBox("INFERRED 비율 임계값")
        thresh_box.setToolTip(
            "TC 근거(source_quote)가 'INFERRED'(LLM 추론)인 비율이\n"
            "이 값을 넘으면 Stage 3에서 재작성을 시도합니다.\n\n"
            "  • 0.30 (기본): 30% 이상이면 재작성 — 매뉴얼이 충분한 경우\n"
            "  • 0.80~: 거의 모든 추론 허용 — 매뉴얼이 적은 경우\n"
            "  • 매뉴얼 미첨부 시: 자동으로 1.00 (모두 허용)"
        )
        t_lay = QVBoxLayout(thresh_box)
        self._thresh_spin = QDoubleSpinBox()
        self._thresh_spin.setRange(0.10, 1.00)
        self._thresh_spin.setSingleStep(0.05)
        self._thresh_spin.setValue(0.30)
        self._thresh_spin.setDecimals(2)
        self._thresh_spin.setSuffix("  (30% 권장)")
        self._thresh_spin.setToolTip(thresh_box.toolTip())
        t_lay.addWidget(self._thresh_spin)
        self._thresh_hint = QLabel("")
        self._thresh_hint.setWordWrap(True)
        self._thresh_hint.setStyleSheet("color:#dc2626; font-size:11px;")
        self._thresh_hint.setVisible(False)
        t_lay.addWidget(self._thresh_hint)
        lay.addWidget(thresh_box)

        # ── 최대 기능 수 (max_leaves) ────────────────────────────────────
        leaves_box = QGroupBox("최대 분석 기능 수 (TC 설계)")
        leaves_box.setToolTip(
            "Stage 2에서 TC 설계할 기능(leaf) 개수의 상한입니다.\n\n"
            "  • 0 = 무제한 (단, 안전 가드로 100개 자동 제한)\n"
            "  • 무료 플랜은 일 20회 한도 → 50 이하 권장\n"
            "  • 신뢰도 HIGH → MID → INFERRED 순으로 우선 처리됨\n\n"
            "예: 분석된 기능 540개 중 max_leaves=50이면\n"
            "    가장 신뢰도 높은 50개만 TC로 설계됩니다."
        )
        l_lay = QVBoxLayout(leaves_box)
        self._max_leaves_spin = QSpinBox()
        self._max_leaves_spin.setRange(0, 9999)
        self._max_leaves_spin.setSingleStep(10)
        self._max_leaves_spin.setValue(50)
        self._max_leaves_spin.setSuffix("  개  (0 = 무제한)")
        self._max_leaves_spin.setToolTip(leaves_box.toolTip())
        l_lay.addWidget(self._max_leaves_spin)
        leaves_hint = QLabel(
            "무료 플랜(20회/일): 50개 이하 권장.  유료 플랜: 0으로 설정하면 전체 기능을 처리합니다."
        )
        leaves_hint.setWordWrap(True)
        leaves_hint.setStyleSheet("color:#888; font-size:11px;")
        l_lay.addWidget(leaves_hint)
        lay.addWidget(leaves_box)

        # ── 자동 실행 표시 옵션 (헤드풀 모드) ────────────────────────────
        exec_box = QGroupBox("자동 실행 옵션 (Stage 5)")
        exec_box.setToolTip(
            "Stage 5에서 TC를 자동 실행할 때 브라우저 동작을 볼지 결정합니다.\n\n"
            "  • 체크 해제(기본): 백그라운드 헤드리스 — 빠르고 조용함\n"
            "  • 체크: 별도 Chromium 창에서 자동화 동작이 보임\n"
            "    (사용자 마우스/키보드와 분리되므로 다른 작업 동시 가능)"
        )
        e_lay = QVBoxLayout(exec_box)
        self._headless_cb = QCheckBox(
            "테스트 실행 시 브라우저 표시 (별도 Chromium 창 — 동작을 직접 볼 수 있음)"
        )
        self._headless_cb.setChecked(False)   # 기본: 헤드리스(체크 안 됨)
        self._headless_cb.setToolTip(exec_box.toolTip())
        e_lay.addWidget(self._headless_cb)

        slow_row = QHBoxLayout()
        slow_row.addWidget(QLabel("느린 모드:"))
        self._slowmo_spin = QSpinBox()
        self._slowmo_spin.setRange(0, 2000)
        self._slowmo_spin.setSingleStep(50)
        self._slowmo_spin.setValue(0)
        self._slowmo_spin.setSuffix("  ms (액션 사이 지연)")
        self._slowmo_spin.setFixedWidth(180)
        self._slowmo_spin.setEnabled(False)
        slow_row.addWidget(self._slowmo_spin)
        slow_row.addStretch()
        e_lay.addLayout(slow_row)
        # 브라우저 표시 체크 시에만 slow mo 활성
        self._headless_cb.toggled.connect(self._slowmo_spin.setEnabled)

        headless_hint = QLabel(
            "체크 해제(기본): 백그라운드 헤드리스 실행 — 빠름.\n"
            "체크: 별도 Chromium 창에서 자동화 동작이 보임. 사용자 마우스/키보드와는 분리됨."
        )
        headless_hint.setWordWrap(True)
        headless_hint.setStyleSheet("color:#888; font-size:11px;")
        e_lay.addWidget(headless_hint)
        lay.addWidget(exec_box)

        # ── 페이지 선택 자동 진행 (원클릭 실행) ────────────────────────────────
        self._auto_pages_cb = QCheckBox(
            "페이지 선택 자동 진행 (수동 선택·재사용 프롬프트 생략, 새로 스캔)"
        )
        self._auto_pages_cb.setChecked(True)   # 기본: 원클릭 자동
        self._auto_pages_cb.setToolTip(
            "체크(기본): 실행 버튼을 누르면 페이지를 자동 수집(BFS)해 바로 진행합니다.\n"
            "  → 매번 새로 스캔하므로 전역 컴포넌트 중복 제거·한글 생성이 적용됩니다.\n"
            "체크 해제: 페이지를 직접 선택하거나 기존 분석 결과(캐시)를 재사용합니다(비용 절감)."
        )
        lay.addWidget(self._auto_pages_cb)

        # ── 기능 확정 게이트 (D53) ────────────────────────────────────────────
        self._feature_gate_cb = QCheckBox(
            "Stage 1 후 기능 확정 게이트 표시 (TC 설계 전 불필요한 기능 제외)"
        )
        self._feature_gate_cb.setChecked(False)   # 기본: 끄기(기존 동작)
        self._feature_gate_cb.setToolTip(
            "체크 시, 기능 통합 후 도메인별 집계를 보여주고 TC를 설계할 기능을 사용자가\n"
            "확정할 수 있습니다(불필요한 기능 제외 → TC 수·시간 절감). 체크 안 하면 전체 진행."
        )
        lay.addWidget(self._feature_gate_cb)

        lay.addStretch()
        summary_lbl = QLabel("설정을 확인하고 '실행 시작'을 클릭하면 파이프라인이 시작됩니다.")
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet("color:#555;")
        lay.addWidget(summary_lbl)
        return outer

    # ── 네비게이션 ────────────────────────────────────────────────────────
    def _go_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx == 0 and not self._validate_page1():
            return
        if idx == 1:
            self._collect_auth()
        if idx == 2:
            self._finish()
            return
        self._stack.setCurrentIndex(idx + 1)
        self._back_btn.setEnabled(True)
        if idx + 1 == 2:
            self._next_btn.setText("실행 시작")
            self._refresh_step3_state()      # 매뉴얼 첨부 여부에 따라 임계값 자동 조정
        self._step_lbl.setText(f"Step {idx + 2} / 3")

    def _refresh_step3_state(self) -> None:
        """Step 3 진입 시 매뉴얼 첨부 여부에 따라 INFERRED 임계값을 자동 조정.

        매뉴얼이 없으면 모든 leaf가 implicit_spec(DOM 추론)으로 들어가서
        INFERRED 비율이 100%가 되므로 임계값 검사는 의미가 없음.
        → 임계값을 1.0으로 강제하고 입력을 비활성화한다.
        """
        no_manual = self._file_list.count() == 0
        if no_manual:
            self._thresh_spin.setValue(1.00)
            self._thresh_spin.setEnabled(False)
            self._thresh_hint.setText(
                "⚠  매뉴얼 미첨부 → DOM 단독 추론 모드 — INFERRED 비율 100% 자동 적용 (임계값 검사 비활성)"
            )
            self._thresh_hint.setVisible(True)
        else:
            self._thresh_spin.setEnabled(True)
            if abs(self._thresh_spin.value() - 1.00) < 1e-6:
                # 이전에 자동 1.00이 적용된 흔적 — 기본값으로 복귀
                self._thresh_spin.setValue(0.30)
            self._thresh_hint.setVisible(False)

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        self._stack.setCurrentIndex(idx - 1)
        self._next_btn.setText("다음 →")
        self._back_btn.setEnabled(idx - 1 > 0)
        self._step_lbl.setText(f"Step {idx} / 3")

    def _validate_page1(self) -> bool:
        kind = self._target_kind_combo.currentData()
        if kind == "web":
            url = self._url_edit.text().strip()
            if not url.startswith(("http://", "https://")):
                QMessageBox.warning(self, "입력 오류", "유효한 URL을 입력하세요 (http:// 또는 https://).")
                return False
            if self._file_list.count() == 0 and not self._skip_stage0_cb.isChecked():
                res = QMessageBox.question(
                    self, "확인",
                    "입력 파일이 없습니다. Stage 0 DOM 스캔만으로 진행하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if res == QMessageBox.No:
                    return False
            return True
        if kind == "api_rest":
            if not (self._rest_openapi.text().strip()):
                QMessageBox.warning(self, "입력 필요", "OpenAPI 스펙 경로 또는 URL을 입력하세요.")
                return False
            return True
        if kind == "api_code":
            if not self._code_module.text().strip():
                QMessageBox.warning(self, "입력 필요", "모듈/DLL/classpath 경로를 입력하세요.")
                return False
            if self._code_lang.currentData() == "java" and not self._code_extra.text().strip():
                QMessageBox.warning(self, "입력 필요", "Java는 추가 칸에 클래스 FQN(콤마)을 입력하세요.")
                return False
            if self._code_lang.currentData() == "c" and not self._code_extra.text().strip():
                QMessageBox.warning(self, "입력 필요", "C는 추가 칸에 시그니처 JSON 경로를 입력하세요.")
                return False
            return True
        if kind == "gui":
            if not self._gui_exe.text().strip():
                QMessageBox.warning(self, "입력 필요", "실행 파일(.exe) 경로를 입력하세요.")
                return False
            return True
        return True

    def _collect_auth(self) -> None:
        self._auth_rows = []
        for r in range(self._auth_table.rowCount()):
            # action: QComboBox의 userData(영문 코드)에서 읽기 (없으면 텍스트 폴백)
            combo = self._auth_table.cellWidget(r, 0)
            if combo is not None:
                data = combo.currentData()
                if data:
                    action = str(data).strip()
                else:
                    # fallback: 텍스트에서 영문 코드 추출
                    txt = combo.currentText().strip()
                    if "(" in txt and ")" in txt:
                        action = txt[txt.rfind("(") + 1: txt.rfind(")")].strip()
                    else:
                        action = txt
            else:
                action = (self._auth_table.item(r, 0) or QTableWidgetItem("")).text().strip()

            selector = (self._auth_table.item(r, 1) or QTableWidgetItem("")).text().strip()
            value    = (self._auth_table.item(r, 2) or QTableWidgetItem("")).text().strip()

            # selector/URL이 비어 있는 행은 완성되지 않은 행으로 간주해 건너뜀
            if not action or not selector:
                continue

            entry: dict = {"action": action, "selector": selector}
            if action == "fill":
                entry["value"] = value
            elif action == "goto":
                entry["url"] = selector
            self._auth_rows.append(entry)

    def _finish(self) -> None:
        model_override = self._model_combo.currentData()
        # 단계별 모델 — 체크됐고 '(기본 모델)'이 아닌 항목만 수집
        model_overrides: dict[str, str] = {}
        if self._stage_model_box.isChecked():
            for cid, combo in self._stage_model_combos.items():
                m = combo.currentData()
                if m:
                    model_overrides[cid] = m
        config = RunConfig(
            api_key=self._api_key,
            target_url=self._url_edit.text().strip(),
            input_files=[
                self._file_list.item(i).text()
                for i in range(self._file_list.count())
            ],
            auth_sequence=self._auth_rows,
            inferred_threshold=self._thresh_spin.value(),
            max_leaves=self._max_leaves_spin.value(),
            model_override=model_override,
            model_overrides=model_overrides or None,
            headless_exec=not self._headless_cb.isChecked(),  # 체크 = 보이게 (headless=False)
            slow_mo_ms=self._slowmo_spin.value() if self._headless_cb.isChecked() else 0,
            feature_gate=self._feature_gate_cb.isChecked(),   # D53
            auto_pages=self._auto_pages_cb.isChecked(),       # 원클릭 자동 진행
            target_kind=self._target_kind_combo.currentData(),    # D59 — 대상 유형
            target_config=self._build_target_config(),            # 유형별 입력
        )
        self.run_config_ready.emit(config)
        self.accept()

    # ── 복제: 전체 스텝 값 채우기 ──────────────────────────────────────────
    def _apply_prefill(self, cfg: dict) -> None:
        """meta.json 형식의 dict로 Step 1~3 모든 입력을 채운다 (복제용)."""
        # Step 1: URL + 파일
        url = cfg.get("target_url", "")
        if url:
            self._url_edit.setText(url)
        for f in (cfg.get("input_files") or []):
            if f and not any(self._file_list.item(i).text() == f
                             for i in range(self._file_list.count())):
                self._file_list.addItem(f)

        # Step 2: 인증 시퀀스 — 행 추가 후 콤보·셀 채우기
        for entry in (cfg.get("auth_sequence") or []):
            action = entry.get("action", "fill")
            # goto는 url 또는 selector, 그 외는 selector
            sel = entry.get("url") if action == "goto" else entry.get("selector", "")
            sel = sel or entry.get("selector", "")
            val = entry.get("value", "")
            self._add_auth_row()
            r = self._auth_table.rowCount() - 1
            combo = self._auth_table.cellWidget(r, 0)
            if combo is not None:
                # userData(영문 코드)로 인덱스 찾기
                for i in range(combo.count()):
                    if combo.itemData(i) == action:
                        combo.setCurrentIndex(i)
                        break
            self._auth_table.setItem(r, 1, QTableWidgetItem(str(sel)))
            if val:
                self._auth_table.setItem(r, 2, QTableWidgetItem(str(val)))

        # Step 3: 모델 / 임계값 / max_leaves / 헤드풀
        model_id = cfg.get("model_override")
        if model_id:
            for i in range(self._model_combo.count()):
                if self._model_combo.itemData(i) == model_id:
                    self._model_combo.setCurrentIndex(i)
                    break
        # 단계별 모델 복원
        overrides = cfg.get("model_overrides") or {}
        if overrides:
            self._stage_model_box.setChecked(True)
            for cid, mid in overrides.items():
                combo = self._stage_model_combos.get(cid)
                if combo:
                    for i in range(combo.count()):
                        if combo.itemData(i) == mid:
                            combo.setCurrentIndex(i)
                            break
        if "inferred_threshold" in cfg and cfg["inferred_threshold"] is not None:
            try:
                self._thresh_spin.setValue(float(cfg["inferred_threshold"]))
            except (TypeError, ValueError):
                pass
        if "max_leaves" in cfg and cfg["max_leaves"] is not None:
            try:
                self._max_leaves_spin.setValue(int(cfg["max_leaves"]))
            except (TypeError, ValueError):
                pass
        # headless_exec=False → 브라우저 표시 체크
        show_browser = not cfg.get("headless_exec", True)
        self._headless_cb.setChecked(show_browser)
        if show_browser and cfg.get("slow_mo_ms"):
            try:
                self._slowmo_spin.setValue(int(cfg["slow_mo_ms"]))
            except (TypeError, ValueError):
                pass
        # D53 — meta의 feature_gate는 결과 dict({shown,...})일 수 있음 → 양쪽 안전 처리
        fg = cfg.get("feature_gate", False)
        self._feature_gate_cb.setChecked(
            bool(fg.get("shown")) if isinstance(fg, dict) else bool(fg)
        )
        self._auto_pages_cb.setChecked(bool(cfg.get("auto_pages", True)))

    # ── 파일 목록 ─────────────────────────────────────────────────────────
    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "요구사항 파일 선택", "",
            "지원 파일 (*.pdf *.docx *.xlsx *.md *.txt);;All files (*)",
        )
        for p in paths:
            if not any(self._file_list.item(i).text() == p
                       for i in range(self._file_list.count())):
                self._file_list.addItem(p)

    def _remove_file(self) -> None:
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    # ── 인증 테이블 ──────────────────────────────────────────────────────
    def _add_auth_row(self) -> None:
        r = self._auth_table.rowCount()
        self._auth_table.insertRow(r)
        self._auth_table.setRowHeight(r, 34)   # 컴팩트한 행 높이

        # 열 0: 동작 QComboBox (한글 표시, 내부 userData는 영문 코드)
        combo = QComboBox()
        combo.addItem("값 입력 (fill)",   userData="fill")
        combo.addItem("요소 클릭 (click)", userData="click")
        combo.addItem("URL 이동 (goto)",  userData="goto")
        # 팝업 너비를 항목 텍스트 길이에 맞춰 자동 확장 (콤보 셀이 작아도 옵션 잘 보이게)
        combo.view().setMinimumWidth(160)
        combo.currentIndexChanged.connect(self._on_action_changed_idx)
        self._auth_table.setCellWidget(r, 0, combo)

        # 열 3: 🎯 선택자 피커 버튼 (WebEngine 있을 때만)
        if _HAS_WEBENGINE:
            btn = QPushButton("🎯")
            btn.setFixedSize(36, 26)   # 너비·높이 모두 고정
            btn.setStyleSheet(
                "QPushButton {"
                " background: #f1f5f9; color: #1e293b;"
                " border: 1px solid #cbd5e1; border-radius: 4px;"
                " min-height: 0px; min-width: 0px; padding: 0px;"
                " font-size: 14px;"
                "}"
                "QPushButton:hover { background: #e2e8f0; }"
                "QPushButton:disabled { background: #f8fafc; color: #cbd5e1; }"
            )
            btn.setToolTip(
                "URL을 팝업 브라우저로 열어 요소를 클릭하면 선택자가 자동 입력됩니다."
            )
            btn.clicked.connect(self._on_picker_btn_clicked)
            self._auth_table.setCellWidget(r, 3, btn)

    def _del_auth_row(self) -> None:
        """선택된 모든 행 삭제 (인덱스 역순으로 제거해 시프트 방지)."""
        rows = sorted(
            {idx.row() for idx in self._auth_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self._auth_table.removeRow(row)

    # ── 액션 변경 시 피커 버튼 활성/비활성 ──────────────────────────────────
    def _on_action_changed_idx(self, _idx: int) -> None:
        """goto 행에서는 피커 버튼 비활성화 (URL 입력이므로 선택자 불필요)."""
        combo = self.sender()
        if combo is None:
            return
        action = combo.currentData()
        for r in range(self._auth_table.rowCount()):
            if self._auth_table.cellWidget(r, 0) is combo:
                btn = self._auth_table.cellWidget(r, 3)
                if btn is not None:
                    btn.setEnabled(action != "goto")
                break

    # ── 피커 버튼 클릭 → 어느 행인지 찾아 피커 호출 ───────────────────────
    def _on_picker_btn_clicked(self) -> None:
        btn = self.sender()
        for r in range(self._auth_table.rowCount()):
            if self._auth_table.cellWidget(r, 3) is btn:
                self._open_selector_picker(r)
                break

    def _open_selector_picker(self, row: int) -> None:
        """해당 행 위에서 가장 가까운 goto URL(또는 Step 1 URL)로 팝업 브라우저 오픈."""
        if not _HAS_WEBENGINE:
            QMessageBox.information(
                self, "기능 없음",
                "PySide6-WebEngine이 설치되어 있지 않습니다.\n"
                "pip install PySide6-WebEngine 후 재시작하세요."
            )
            return

        # 이 행 위쪽 goto 행에서 URL 찾기
        url = ""
        for r in range(row - 1, -1, -1):
            combo = self._auth_table.cellWidget(r, 0)
            if combo and combo.currentText() == "goto":
                item = self._auth_table.item(r, 1)
                if item:
                    url = item.text().strip()
                if url:
                    break

        # goto URL 없으면 Step 1 URL 사용
        if not url:
            url = self._url_edit.text().strip()

        if not url.startswith(("http://", "https://")):
            QMessageBox.warning(
                self, "URL 없음",
                "이 행 위에 'goto' 행을 추가하고 URL을 입력하거나,\n"
                "Step 1에서 대상 URL을 먼저 입력하세요."
            )
            return

        dlg = SelectorPickerDialog(url, parent=self)
        if dlg.exec() == QDialog.Accepted:
            sel = dlg.selected_selector()
            if sel:
                self._auth_table.setItem(row, 1, QTableWidgetItem(sel))

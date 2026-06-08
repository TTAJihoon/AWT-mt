"""AWT 전역 디자인 시스템 — DESIGN.md Apple-inspired (doc/DESIGN.md).

토큰 참조:
  primary      #0066cc  Action Blue — 모든 인터랙티브 요소
  canvas       #ffffff  기본 배경
  parchment    #f5f5f7  섹션 배경 / 교차 타일
  ink          #1d1d1f  기본 텍스트
  ink-muted    #7a7a7a  보조 텍스트
  surface-black #000000 헤더 (global-nav)
  hairline     #e0e0e0  1px 구분선
  divider-soft #f0f0f0  내부 셀 구분선
"""
from __future__ import annotations

# ── 색상 토큰 ──────────────────────────────────────────────────────
PRIMARY         = "#0066cc"
PRIMARY_HOVER   = "#0071e3"
PRIMARY_PRESSED = "#0056b3"
PRIMARY_DIM     = "#cce0ff"   # disabled chunk

CANVAS          = "#ffffff"
PARCHMENT       = "#f5f5f7"
SURFACE_BLACK   = "#000000"
SURFACE_DARK    = "#272729"
SURFACE_PEARL   = "#fafafc"

INK             = "#1d1d1f"
INK_MUTED       = "#7a7a7a"
BODY_MUTED      = "#cccccc"   # dark tile secondary

HAIRLINE        = "#e0e0e0"
DIVIDER_SOFT    = "#f0f0f0"
ON_PRIMARY      = "#ffffff"
ON_DARK         = "#ffffff"
ON_DARK_LINK    = "#2997ff"   # links on dark surface

# ── 유틸리티 스타일 헬퍼 ───────────────────────────────────────────

def pill_btn(bg: str = PRIMARY, fg: str = ON_PRIMARY,
             bg_hover: str = PRIMARY_HOVER,
             bg_pressed: str = PRIMARY_PRESSED,
             bg_disabled: str = "#d2d2d7",
             fg_disabled: str = INK_MUTED) -> str:
    """Primary pill 버튼 인라인 스타일."""
    return (
        f"QPushButton{{background:{bg};color:{fg};border:none;"
        f"border-radius:9999px;padding:7px 20px;font-size:13px;font-weight:500;}}"
        f"QPushButton:hover{{background:{bg_hover};}}"
        f"QPushButton:pressed{{background:{bg_pressed};}}"
        f"QPushButton:disabled{{background:{bg_disabled};color:{fg_disabled};}}"
    )


def utility_btn(bg: str = INK, fg: str = ON_DARK,
                bg_hover: str = "#333333",
                bg_disabled: str = "#d2d2d7",
                fg_disabled: str = INK_MUTED) -> str:
    """Utility rect 버튼 인라인 스타일 (border-radius: sm = 8px)."""
    return (
        f"QPushButton{{background:{bg};color:{fg};border:none;"
        f"border-radius:8px;padding:6px 16px;font-size:13px;}}"
        f"QPushButton:hover{{background:{bg_hover};}}"
        f"QPushButton:disabled{{background:{bg_disabled};color:{fg_disabled};}}"
    )


def ghost_btn(fg: str = PRIMARY, border: str = PRIMARY) -> str:
    """Ghost (secondary) pill 버튼."""
    return (
        f"QPushButton{{background:transparent;color:{fg};"
        f"border:1px solid {border};border-radius:9999px;padding:7px 20px;font-size:13px;}}"
        f"QPushButton:hover{{background:{PARCHMENT};}}"
        f"QPushButton:disabled{{color:{INK_MUTED};border-color:{HAIRLINE};}}"
    )


# ── 전역 QSS ─────────────────────────────────────────────────────
APPLE_QSS = f"""
/* ═══════════════════════════════════════════════════════════════
   AWT — Apple-inspired Design System  (doc/DESIGN.md)
   Font: Segoe UI (SF Pro substitute on Windows)
   Primary: {PRIMARY}  |  Canvas: {CANVAS}  |  Ink: {INK}
═══════════════════════════════════════════════════════════════ */

/* Base */
QWidget {{
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    color: {INK};
    background-color: {CANVAS};
}}
QMainWindow, QDialog {{
    background-color: {PARCHMENT};
}}

/* ── Buttons (pill — DESIGN.md button-primary) ──────────────── */
QPushButton {{
    background-color: {PRIMARY};
    color: {ON_PRIMARY};
    border: none;
    border-radius: 9999px;
    padding: 7px 20px;
    font-size: 13px;
    font-weight: 500;
    min-height: 28px;
}}
QPushButton:hover {{ background-color: {PRIMARY_HOVER}; }}
QPushButton:pressed {{ background-color: {PRIMARY_PRESSED}; }}
QPushButton:disabled {{ background-color: #d2d2d7; color: {INK_MUTED}; }}

/* ── LineEdit ────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {CANVAS};
    color: {INK};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {PRIMARY_DIM};
}}
QLineEdit:focus {{
    border: 2px solid {PRIMARY};
    padding: 5px 9px;
}}
QLineEdit:disabled {{
    background-color: {PARCHMENT};
    color: {INK_MUTED};
}}

/* ── TextEdit / PlainTextEdit ────────────────────────────────── */
QPlainTextEdit, QTextEdit {{
    background-color: {PARCHMENT};
    color: {INK};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: {PRIMARY_DIM};
}}

/* ── ComboBox ────────────────────────────────────────────────── */
QComboBox {{
    background-color: {CANVAS};
    color: {INK};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 28px;
}}
QComboBox:focus {{ border: 2px solid {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {CANVAS};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    selection-background-color: {PARCHMENT};
    selection-color: {INK};
    outline: none;
    padding: 4px;
}}

/* ── Tabs (underline style) ──────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background-color: {CANVAS};
    border-top: 1px solid {HAIRLINE};
}}
QTabBar::tab {{
    background: transparent;
    color: {INK_MUTED};
    padding: 9px 22px;
    font-size: 13px;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {INK};
    border-bottom: 2px solid {PRIMARY};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {INK};
    border-bottom: 2px solid {HAIRLINE};
}}

/* ── Tables ──────────────────────────────────────────────────── */
QTableWidget {{
    background-color: {CANVAS};
    alternate-background-color: {PARCHMENT};
    border: none;
    gridline-color: {DIVIDER_SOFT};
    selection-background-color: #e8f0fd;
    selection-color: {INK};
}}
QTableWidget::item {{
    padding: 5px 8px;
    border-bottom: 1px solid {DIVIDER_SOFT};
}}
QTableWidget::item:selected {{
    background-color: #e8f0fd;
    color: {INK};
}}
QHeaderView::section {{
    background-color: {PARCHMENT};
    color: {INK};
    font-weight: 600;
    font-size: 12px;
    border: none;
    border-bottom: 1px solid {HAIRLINE};
    border-right: 1px solid {DIVIDER_SOFT};
    padding: 6px 8px;
}}
QHeaderView::section:last {{ border-right: none; }}
QHeaderView {{ background-color: {PARCHMENT}; }}

/* ── Progress Bar ────────────────────────────────────────────── */
QProgressBar {{
    border: none;
    border-radius: 4px;
    background-color: #e5e7eb;
    text-align: center;
    font-size: 11px;
    color: {INK_MUTED};
    min-height: 6px;
}}
QProgressBar::chunk {{
    background-color: {PRIMARY};
    border-radius: 4px;
}}

/* ── GroupBox ────────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {HAIRLINE};
    border-radius: 11px;
    margin-top: 10px;
    padding: 14px 12px 10px 12px;
    font-weight: 600;
    font-size: 12px;
    color: {INK_MUTED};
    background-color: {CANVAS};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 4px;
    color: {INK_MUTED};
    background-color: {CANVAS};
}}

/* ── ScrollBar ───────────────────────────────────────────────── */
QScrollBar:vertical {{
    width: 8px;
    background: transparent;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #d2d2d7;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #a0a0a5; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    height: 8px;
    background: transparent;
}}
QScrollBar::handle:horizontal {{
    background: #d2d2d7;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── StatusBar ───────────────────────────────────────────────── */
QStatusBar {{
    background-color: {PARCHMENT};
    color: {INK_MUTED};
    font-size: 11px;
    border-top: 1px solid {HAIRLINE};
}}

/* ── Menu ────────────────────────────────────────────────────── */
QMenu {{
    background-color: {CANVAS};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 5px;
    color: {INK};
    font-size: 13px;
}}
QMenu::item:selected {{ background-color: {PARCHMENT}; }}
QMenu::item:disabled {{ color: {INK_MUTED}; }}

/* ── Splitter ────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {HAIRLINE};
    width: 1px;
    height: 1px;
}}

/* ── CheckBox ────────────────────────────────────────────────── */
QCheckBox {{ color: {INK}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {HAIRLINE};
    border-radius: 4px;
    background: {CANVAS};
}}
QCheckBox::indicator:checked {{
    background-color: {PRIMARY};
    border-color: {PRIMARY};
}}

/* ── SpinBox ─────────────────────────────────────────────────── */
QDoubleSpinBox, QSpinBox {{
    background-color: {CANVAS};
    color: {INK};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 5px 8px;
    min-height: 28px;
}}
QDoubleSpinBox:focus, QSpinBox:focus {{ border: 2px solid {PRIMARY}; }}

/* ── ListWidget ──────────────────────────────────────────────── */
QListWidget {{
    background-color: {CANVAS};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 4px 8px;
    border-radius: 5px;
    color: {INK};
}}
QListWidget::item:selected {{
    background-color: {PARCHMENT};
    color: {INK};
}}
QListWidget::item:hover {{ background-color: {PARCHMENT}; }}

/* ── Label ───────────────────────────────────────────────────── */
QLabel {{ background: transparent; color: {INK}; }}

/* ── ToolTip ─────────────────────────────────────────────────── */
QToolTip {{
    background-color: {INK};
    color: {ON_DARK};
    border: none;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* ── MessageBox ──────────────────────────────────────────────── */
QMessageBox {{ background-color: {CANVAS}; }}
QMessageBox QLabel {{ background: transparent; }}
"""

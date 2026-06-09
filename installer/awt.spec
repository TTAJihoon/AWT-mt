# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — AWT v1.0 Windows 단일 폴더 패키징."""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # 프롬프트 파일 (tc_design_api.md·tc_testdata.md 포함)
        (str(ROOT / "prompts"), "prompts"),
        # 자산: 도메인 불변규칙(YAML) + 결함 카탈로그(JSON) — 런타임 로더가 읽음
        (str(ROOT / "data" / "assets"), "data/assets"),
        # Playwright 브라우저 번들은 playwright install 후 자동 포함
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "anthropic",
        "openai",
        "psycopg2",
        "playwright.sync_api",
        "httpx",                 # api_rest 어댑터 (D61)
        "openpyxl",
        "fitz",          # PyMuPDF
        "docx",          # python-docx
        "cryptography.fernet",
        # 대상 어댑터 — registry에 동적 등록되므로 명시 (D59~D63)
        "app.adapters.web_adapter",
        "app.adapters.api_rest_adapter",
        "app.adapters.api_code_adapter",
        "app.adapters.gui_adapter",
        "app.adapters.api_code.python_runner",
        "app.adapters.api_code.c_runner",
        "app.adapters.api_code.dotnet_runner",
        "app.adapters.api_code.java_runner",
        "app.adapters.value_synth",
        "app.adapters.llm_test_data",
        "app.adapters.report_summary",
        "app.ui.api_key_dialog",
        # 선택 의존(pythonnet/jpype/uiautomation/pywinauto)은 번들 안 함 —
        # 어댑터가 lazy import + 안내 예외로 graceful 처리. 필요 시 빌드 환경에 설치.
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "scipy", "numpy",
        # QtWebEngine 스택 제외 — 용량·빌드시간의 주범(~수백 MB).
        # 웹 셀렉터 피커(보조 기능)만 비활성화되며 _HAS_WEBENGINE 가드로 안전.
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngine",
        "PySide6.QtWebChannel", "PySide6.QtWebSockets",
        # 사용하지 않는 무거운 Qt 모듈
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2", "PySide6.QtPositioning",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtBluetooth", "PySide6.QtNfc",
        "PySide6.QtTest", "PySide6.QtDesigner",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AWT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI 앱: 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "installer" / "awt.ico") if (ROOT / "installer" / "awt.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AWT",
)

# 빌드 후 .env.example을 dist/AWT/에 복사 (실제 .env는 사용자가 직접 편집)
import shutil
_env_example = ROOT / ".env.example"
_env_dest    = ROOT / "dist" / "AWT" / ".env.example"
if _env_example.exists():
    shutil.copy2(str(_env_example), str(_env_dest))

# 로컬 .env가 있으면 함께 복사 (개발/테스트 편의)
_env_src  = ROOT / ".env"
_env_ddst = ROOT / "dist" / "AWT" / ".env"
if _env_src.exists():
    shutil.copy2(str(_env_src), str(_env_ddst))

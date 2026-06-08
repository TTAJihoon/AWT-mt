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
        # 프롬프트 파일
        (str(ROOT / "prompts"), "prompts"),
        # Playwright 브라우저 번들은 playwright install 후 자동 포함
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "anthropic",
        "psycopg2",
        "playwright.sync_api",
        "openpyxl",
        "fitz",          # PyMuPDF
        "docx",          # python-docx
        "cryptography.fernet",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "numpy"],
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

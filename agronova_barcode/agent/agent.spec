# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller sozlamasi — bitta exe fayl yasaydi.

    pyinstaller agent.spec

Natija: dist/OdooPrintAgent-YYYY-MM-DD.exe
"""
import datetime
import os

a = Analysis(
    ["agent_gui.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    # win32com.client — avtoyuklash yorlig'i uchun
    # win32gui/win32con — trey belgichasi uchun
    hiddenimports=["win32print", "win32api", "win32gui", "win32con",
                   "win32com.client", "pythoncom", "pywintypes"],
    hookspath=[],
    runtime_hooks=[],
    # Exe hajmini kamaytiramiz — bular kerak emas
    excludes=["numpy", "pandas", "matplotlib", "PIL", "pytest", "unittest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    # Nomga bild sanasi qo'shiladi — sexda eski va yangi fayl adashmasin.
    # build.ps1 uni AGENT_BUILD_DATE orqali beradi.
    name="OdooPrintAgent-%s" % (os.environ.get("AGENT_BUILD_DATE")
                                or datetime.date.today().isoformat()),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Oyna dasturi — qora konsol chiqmasin
    console=False,
    disable_windowed_traceback=False,
    icon=None,
)

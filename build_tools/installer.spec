# -*- mode: python ; coding: utf-8 -*-
"""
وصفة بناء مثبّت Wun Studio.

    python build_tools/make_installer.py

السكربت أعلاه يحزم نسخة المجلد في payload.zip ثم يستدعي هذه الوصفة، فينتج
ملف واحد يحمل البرنامج بداخله ولا يحتاج المستخدم إلا تشغيله.
"""

import os

ROOT = os.path.abspath(os.getcwd())

DATAS = [
    (os.path.join(ROOT, "build", "payload.zip"), "."),
    (os.path.join(ROOT, "assets", "fonts"), "fonts"),
]

EXCLUDES = [
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtLocation",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtQml",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
    "numpy", "PIL", "tkinter", "unittest", "pydoc", "doctest",
    "fontTools", "setuptools", "pip", "PyInstaller",
]

a = Analysis(
    [os.path.join(ROOT, "build_tools", "installer.py")],
    pathex=[ROOT],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Wun Studio Setup",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "app.ico"),
)

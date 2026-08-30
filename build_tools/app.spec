# -*- mode: python ; coding: utf-8 -*-
"""
وصفة بناء ملف exe مستقل.

    .venv\\Scripts\\pyinstaller.exe build_tools\\app.spec --noconfirm

النتيجة ملف واحد في dist لا يحتاج بايثون ولا أي حزمة مثبّتة على الجهاز.
الاستثناءات في EXCLUDES تحذف وحدات Qt التي لا يستعملها البرنامج، وهي ما
يخفض الحجم إلى أقل من نصف البناء الافتراضي.
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.getcwd()))
PKG = os.path.basename(ROOT)
PARENT = os.path.dirname(ROOT)

# اسم الحزمة يُثبَّت في وحدة صغيرة يقرأها entry.py، لأن اشتقاقه من مسار الملف
# لا يصحّ داخل الـ exe حيث يكون المجلد مؤقتًا بلا اسم معروف.
with open(os.path.join(ROOT, "build_tools", "_pkg.py"), "w",
          encoding="utf-8") as fh:
    fh.write('"""اسم الحزمة، يُولَّد آليًا وقت البناء."""\n\nNAME = %r\n' % PKG)

# ملفات تُحزم بجانب الكود، بنفس البنية النسبية التي يتوقعها theme._assets_dir
DATAS = [
    (os.path.join(ROOT, "assets", "fonts"), os.path.join(PKG, "assets", "fonts")),
]

# وحدات الحزمة تُستورد ديناميكيًا في main.py، فلا يراها المحلّل تلقائيًا
HIDDEN = [
    "%s.main" % PKG,
    "%s.core.rsc7" % PKG,
    "%s.core.ytd_handler" % PKG,
    "%s.core.texture_handler" % PKG,
    "%s.core.export_handler" % PKG,
    "%s.gui.theme" % PKG,
    "%s.gui.icons" % PKG,
    "%s.gui.widgets" % PKG,
    "%s.gui.shell" % PKG,
    "%s.gui.canvas" % PKG,
    "%s.gui.tool_rail" % PKG,
    "%s.gui.texture_list" % PKG,
    "%s.gui.properties" % PKG,
    "%s.gui.main_window" % PKG,
]

# البرنامج يستعمل QtCore و QtGui و QtWidgets و QtSvg فقط
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
    # أدوات تطوير لا علاقة لها بالتشغيل
    "tkinter", "unittest", "pydoc", "doctest", "pytest",
    "fontTools", "setuptools", "pip", "PyInstaller",
    "matplotlib", "scipy", "pandas", "IPython",
]

a = Analysis(
    [os.path.join(ROOT, "build_tools", "entry.py")],
    pathex=[PARENT, ROOT],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
    name="Wun Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,              # تطبيق نافذي: بلا نافذة أوامر سوداء
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT, "assets", "app.ico"),
)

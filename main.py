"""
محرّر تكستشرات YTD - نقطة الدخول.

التشغيل:
    python main.py                 (من داخل مجلد المشروع)
    python main.py ملف.ytd         (فتح ملف مباشرة)
    python -m <اسم_المجلد>.main    (من المجلد الأب)
"""

from __future__ import annotations

import importlib
import os
import sys

# يسمح بتشغيل `python main.py` دون تثبيت الحزمة: نضع المجلد الذي *يحوي*
# مجلد المشروع في مسار الاستيراد.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_PKG_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# اسم الحزمة يُشتق من اسم المجلد الفعلي بدل كتابته حرفيًا، فيعمل المشروع
# مهما كان اسم المجلد الذي استُنسخ إليه.
_PKG = os.path.basename(_PKG_DIR)


REQUIREMENTS = [
    ("PySide6", "PySide6", "واجهة Qt"),
    ("numpy", "numpy", "ترميز التكستشرات وفكّها"),
    ("PIL", "Pillow", "استيراد وتصدير الصور وفكّ BC7"),
]


def check_dependencies():
    """رسالة واضحة بدل ImportError خام."""
    missing = []
    for module, package, purpose in REQUIREMENTS:
        try:
            __import__(module)
        except ImportError:
            missing.append((package, purpose))
    if not missing:
        return

    lines = ["تعذّر تشغيل محرّر تكستشرات YTD - حزم ناقصة:", ""]
    for package, purpose in missing:
        lines.append("  - %s   (مطلوبة لـ %s)" % (package, purpose))
    lines += ["", "ثبّتها كلها بالأمر:", "", "    pip install -r requirements.txt", ""]
    message = "\n".join(lines)

    print(message, file=sys.stderr)
    if all(p != "PySide6" for p, _ in missing):
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "حزم ناقصة", message)
        except Exception:
            pass
    sys.exit(1)


def main():
    check_dependencies()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    theme = importlib.import_module(_PKG + ".gui.theme")
    window_module = importlib.import_module(_PKG + ".gui.main_window")

    # AA_UseHighDpiPixmaps صار سلوكًا افتراضيًا في Qt 6، وضبطه يطلق تحذير إهمال
    app = QApplication(sys.argv)
    app.setApplicationName("محرّر تكستشرات YTD")
    app.setOrganizationName("YTD Texture Editor")
    app.setStyle("Fusion")

    # الخطوط قبل ورقة الأنماط: الأنماط تشير إلى اسم عائلة الخط المحمّل.
    theme.load_fonts()
    theme.apply_palette(app)
    app.setFont(theme.font(10))
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(theme.qss())

    window = window_module.MainWindow()
    window.show()

    # فتح ملف مُمرَّر في سطر الأوامر أو مُفلَت على الاختصار
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and os.path.isfile(args[0]):
        window.load_ytd(args[0])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""
توليد أيقونة التطبيق (assets/app.ico) من نفس رسم الأيقونات المستخدم في الواجهة.

تُشغَّل يدويًا عند تغيير هوية التطبيق فقط، وليست جزءًا من تشغيل البرنامج:

    python build_tools/make_icon.py
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(_ROOT))

from PySide6.QtCore import QRectF, Qt                       # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter          # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

_PKG = os.path.basename(_ROOT)
theme = __import__(_PKG + ".gui.theme", fromlist=["theme"])
icons = __import__(_PKG + ".gui.icons", fromlist=["icons"])

SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QImage:
    """مربّع داكن بزوايا دائرية وعليه رمز الطبقات بلون التمييز."""
    img = QImage(size, size, QImage.Format_RGBA8888)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)

    radius = size * 0.22
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.BG_ELEV))
    p.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # حافة داخلية خفيفة تعطي عمقًا عند الأحجام الكبيرة
    if size >= 32:
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(theme.BORDER_HI))
        p.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1),
                          radius, radius)

    # سماكة الخط بوحدات شبكة الـ SVG (24 وحدة) لا بالبكسل: لو تناسبت مع حجم
    # الصورة لانطبقت الخطوط على بعضها وصار الرمز كتلة صمّاء. نغلّظها قليلًا
    # في الأحجام الصغيرة فقط حتى تبقى مقروءة في شريط المهام.
    glyph = int(size * 0.62)
    stroke = 2.6 if size <= 24 else (2.1 if size <= 48 else 1.7)
    pm = icons.pixmap("layers", glyph, theme.ACCENT, stroke)
    p.drawPixmap((size - glyph) // 2, (size - glyph) // 2, pm)
    p.end()
    return img


def main():
    app = QApplication(sys.argv)
    theme.load_fonts()

    from PIL import Image
    frames = []
    tmp_dir = os.path.join(_ROOT, "assets")
    os.makedirs(tmp_dir, exist_ok=True)

    for size in SIZES:
        path = os.path.join(tmp_dir, "_icon_%d.png" % size)
        render(size).save(path)
        frames.append(Image.open(path).convert("RGBA"))

    out = os.path.join(tmp_dir, "app.ico")
    frames[-1].save(out, format="ICO",
                    sizes=[(f.width, f.height) for f in frames])

    for size in SIZES:
        os.remove(os.path.join(tmp_dir, "_icon_%d.png" % size))

    print("wrote %s (%d bytes, %d sizes)"
          % (out, os.path.getsize(out), len(SIZES)))
    app.quit()


if __name__ == "__main__":
    main()

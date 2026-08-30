"""
مصنع الأيقونات.

كل أيقونة مسار SVG مكتوب داخل الملف نفسه، فلا يعتمد المشروع على أي ملف
أيقونات خارجي ولا على حزمة إضافية. الأيقونة تُرسم باللون المطلوب لحظة
الطلب وتُخزّن مؤقتًا، فتغيير لون الثيم لا يحتاج إعادة تصدير أي شيء.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

# مسارات SVG على شبكة 24×24، كلها خطوط بلا تعبئة
PATHS = {
    # ملفات
    "open":      "M3 7.5A2 2 0 0 1 5 5.5h3.6l1.8 2H19a2 2 0 0 1 2 2v8.5"
                 "a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
    "save":      "M12 3.5v10.5m0 0-4-4m4 4 4-4M5 17v2.5h14V17",
    "export":    "M12 15V3.5m0 0L8.5 7M12 3.5 15.5 7M4.5 14v5.5h15V14",
    "import":    "M12 3.5V15m0 0-3.5-3.5M12 15l3.5-3.5M4.5 14v5.5h15V14",

    # تاريخ
    "undo":      "M9.5 14.5 4.5 9.5l5-5M4.5 9.5h9a6 6 0 0 1 0 12h-3",
    "redo":      "M14.5 14.5l5-5-5-5M19.5 9.5h-9a6 6 0 0 0 0 12h3",
    "revert":    "M3.5 12a8.5 8.5 0 1 0 2.9-6.4M3.5 4.5v5h5",

    # أدوات الرسم
    "brush":     "M16.5 3.2a2.55 2.55 0 0 1 3.6 3.6L8 19 3 21l2-5z"
                 "M14.5 5.2 18.8 9.5",
    "eraser":    "M8.5 20.5 3.8 15.8a1.8 1.8 0 0 1 0-2.5l8.4-8.4a1.8 1.8 0 0 1 2.5 0"
                 "l5 5a1.8 1.8 0 0 1 0 2.5l-8.1 8.1zM9 20.5h11M8.5 9.5 15 16",
    "text":      "M5 5.5h14M12 5.5v13M8.5 18.5h7",
    "rect":      "M3.5 6.5h17v11h-17z",
    "ellipse":   "M12 6.5c4.7 0 8.5 2.5 8.5 5.5s-3.8 5.5-8.5 5.5S3.5 15 3.5 12"
                 " 7.3 6.5 12 6.5z",
    "line":      "M4.5 19.5 19.5 4.5",
    "pick":      "M17.5 2.8 21.2 6.5l-8.6 8.6-3.7-3.7zM10.5 13.5 6 18v3h3l4.5-4.5"
                 "M4.5 18.5 3 21l2.5-1.5",

    # التكبير
    "zoom_in":   "M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20.5 20.5 16 16"
                 "M8.4 11h5.2M11 8.4v5.2",
    "zoom_out":  "M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20.5 20.5 16 16"
                 "M8.4 11h5.2",
    "fit":       "M4 9.5V4h5.5M20 9.5V4h-5.5M4 14.5V20h5.5M20 14.5V20h-5.5",
    "actual":    "M5.5 5.5h13v13h-13zM9.5 9.5h5v5h-5z",

    # عمليات على التكستشر
    "rotate_cw":  "M20.5 12a8.5 8.5 0 1 1-2.5-6M20.5 3.5v5h-5",
    "rotate_ccw": "M3.5 12a8.5 8.5 0 1 0 2.5-6M3.5 3.5v5h5",
    "flip_h":     "M12 3v18M8.5 7.5 4 12l4.5 4.5zM15.5 7.5 20 12l-4.5 4.5z",
    "flip_v":     "M3 12h18M7.5 8.5 12 4l4.5 4.5zM7.5 15.5 12 20l4.5-4.5z",
    "crop":       "M6.5 2.5v15h15M2.5 6.5h15v15",
    "resize":     "M15 3.5h5.5V9M9 20.5H3.5V15M20.5 3.5 14 10M3.5 20.5 10 14",
    "trash":      "M4 6.5h16M9.5 10.5v6M14.5 10.5v6M6 6.5 7 20.5h10l1-14"
                  "M9 6.5V3.5h6v3",
    "image":      "M3.5 5h17v14h-17zM3.5 16l5-5 4 4 3-3 5 5M8.7 10a1.6 1.6 0 1 1 0-3.2"
                  " 1.6 1.6 0 0 1 0 3.2z",
    "layers":     "M12 3 21 8l-9 5-9-5zM3 13l9 5 9-5",
    "pan":        "M12 3v18M3 12h18M12 3 9.2 5.8M12 3l2.8 2.8M12 21l-2.8-2.8M12 21l2.8-2.8M3 12l2.8-2.8M3 12l2.8 2.8M21 12l-2.8-2.8M21 12l-2.8 2.8",

    "fill":       "M11 2.8 3.6 10.2a2 2 0 0 0 0 2.8l5.4 5.4a2 2 0 0 0 2.8 0"
                  "l7.4-7.4zM7.2 7l8 8M19.4 15c.9 1.3 1.5 2.3 1.5 2.9"
                  "a1.5 1.5 0 1 1-3 0c0-.6.6-1.6 1.5-2.9z",
    "gradient":   "M3.5 3.5h17v17h-17zM3.5 9.5h17M3.5 14h17M3.5 17.5h17",
    "select":     "M3.5 8.5v-5h5M15.5 3.5h5v5M20.5 15.5v5h-5M8.5 20.5h-5v-5",
    "adjust":     "M4 7h9M17 7h3M4 17h3M11 17h9M15 4.5v5M7 14.5v5",
    "compare":    "M12 3.5v17M3.5 7.5h5v9h-5zM15.5 7.5h5v9h-5z",
    "grid_view":  "M3.5 3.5h17v17h-17zM9 3.5v17M15 3.5v17M3.5 9h17M3.5 15h17",
    "batch":      "M7 3.5h13.5V17M4.5 7h13v13.5h-13z",
    "navigator":  "M3.5 3.5h17v17h-17zM8 8h8v8H8z",

    # واجهة
    "search":    "M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zM20.5 20.5 16 16",
    "close":     "M6 6l12 12M18 6 6 18",
    "minimize":  "M6 12h12",
    "maximize":  "M5 5h14v14H5z",
    "restore":   "M8.5 8.5V5h10.5v10.5H15.5M5 8.5h10.5V19H5z",
    "chevron":   "M6.5 9.5 12 15l5.5-5.5",
    "check":     "M5 12.5 9.5 17 19 7.5",
    "info":      "M12 3.2a8.8 8.8 0 1 0 0 17.6 8.8 8.8 0 0 0 0-17.6z"
                 "M12 11v6M12 7.3v.6",
    "warn":      "M12 3.5 21.5 20h-19zM12 9.5v5M12 17v.6",
    "grid":      "M3.5 3.5h7v7h-7zM13.5 3.5h7v7h-7zM3.5 13.5h7v7h-7z"
                 "M13.5 13.5h7v7h-7z",
}

_CACHE: dict[tuple, QIcon] = {}


def _svg(path: str, color: str, width: float) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        'fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" '
        'stroke-linejoin="round"><path d="%s"/></svg>'
        % (color, width, path)
    ).encode("utf-8")


def pixmap(name: str, size=20, color: str | None = None, width=1.6) -> QPixmap:
    """رسم أيقونة كـ QPixmap بالحجم واللون المطلوبين."""
    path = PATHS.get(name)
    if path is None:
        return QPixmap()
    renderer = QSvgRenderer(QByteArray(_svg(path, color or theme.TXT, width)))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pm


def icon(name: str, size=20, color: str | None = None, width=1.6) -> QIcon:
    """
    أيقونة مخزّنة مؤقتًا.

    التخزين المؤقت مهم لأن قائمة التكستشرات وريل الأدوات يطلبان الأيقونة
    نفسها عشرات المرات أثناء إعادة الرسم.
    """
    key = (name, size, color or theme.TXT, width)
    hit = _CACHE.get(key)
    if hit is None:
        hit = QIcon(pixmap(name, size, color, width))
        _CACHE[key] = hit
    return hit


def icon_size(size=20) -> QSize:
    return QSize(size, size)

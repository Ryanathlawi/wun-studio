"""
ريل الأدوات: شريط عمودي رفيع بأيقونات، ملاصق للكانفس.

وضع الأدوات في عمود بجانب مساحة الرسم - بدل شريط أفقي في الأعلى - يقصّر
المسافة بين اليد والأداة، ويترك العرض كله للتكستشر.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QVBoxLayout, QWidget

from . import canvas as cv
from . import theme
from .widgets import Divider, IconButton

TOOLS = [
    (cv.TOOL_BRUSH,   "brush",   "فرشاة",  "B"),
    (cv.TOOL_ERASER,  "eraser",  "ممحاة",  "E"),
    (cv.TOOL_TEXT,    "text",    "نص",     "T"),
    (cv.TOOL_RECT,    "rect",    "مستطيل", "R"),
    (cv.TOOL_ELLIPSE, "ellipse", "بيضاوي", "L"),
    (cv.TOOL_LINE,    "line",    "خط",     "N"),
    (cv.TOOL_FILL,    "fill",     "دلو تعبئة", "F"),
    (cv.TOOL_GRADIENT, "gradient", "تدرّج لوني", "G"),
    (cv.TOOL_SELECT,  "select",   "تحديد مستطيل", "M"),
    (cv.TOOL_PICK,    "pick",     "ملقاط ألوان", "I"),
    (cv.TOOL_PAN,     "pan",      "تحريك اللوحة", "H"),
]


class ToolRail(QWidget):
    """عمود الأدوات وأزرار التكبير."""

    toolChanged = Signal(str)
    zoomInRequested = Signal()
    zoomOutRequested = Signal()
    fitRequested = Signal()
    actualSizeRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Rail")
        self.setFixedWidth(theme.RAIL_W)

        column = QVBoxLayout(self)
        column.setContentsMargins(7, 9, 7, 9)
        column.setSpacing(4)
        column.setAlignment(Qt.AlignHCenter)

        self.buttons = {}
        group = QButtonGroup(self)
        group.setExclusive(True)

        for key, icon_name, label, shortcut in TOOLS:
            btn = IconButton(icon_name, "%s  (%s)" % (label, shortcut),
                             size=theme.RAIL_W - 14, icon_size=19, checkable=True)
            btn.clicked.connect(lambda _c=False, k=key: self._pick(k))
            group.addButton(btn)
            column.addWidget(btn)
            self.buttons[key] = btn

        self.buttons[cv.TOOL_BRUSH].setChecked(True)

        column.addSpacing(6)
        column.addWidget(Divider())
        column.addSpacing(6)

        zoom = [
            ("zoom_in",  "تكبير  (Ctrl +)",       self.zoomInRequested),
            ("zoom_out", "تصغير  (Ctrl -)",       self.zoomOutRequested),
            ("fit",      "ملء الشاشة  (Ctrl+0)",  self.fitRequested),
            ("actual",   "الحجم الأصلي  (Ctrl+1)", self.actualSizeRequested),
        ]
        for icon_name, tip, signal in zoom:
            btn = IconButton(icon_name, tip, size=theme.RAIL_W - 14, icon_size=18)
            btn.clicked.connect(signal)
            column.addWidget(btn)

        column.addStretch(1)

    def _pick(self, key):
        self.set_tool(key)
        self.toolChanged.emit(key)

    def set_tool(self, key):
        btn = self.buttons.get(key)
        if btn is not None and not btn.isChecked():
            btn.setChecked(True)
        for k, b in self.buttons.items():
            b.setChecked(k == key)

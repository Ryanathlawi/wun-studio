"""
لوحة الملفات المفتوحة.

تظهر فوق قائمة التكستشرات عند فتح أكثر من ملف، وتعرض لكل ملف اسمه وعدد
تكستشراته وعلامة تعديل. الملفات تُقرأ عند اختيارها لا عند فتحها، لأن مجلد
خرائط كامل قد يضم عشرات الملفات بحجم 3072×3072 ولا معنى لتحليلها كلها
مقدّمًا.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QStyle, QStyledItemDelegate,
                               QVBoxLayout, QWidget)

from . import icons, theme

ROW_H = 40
PAD = 9
DATA = Qt.UserRole + 1


class FileDelegate(QStyledItemDelegate):
    """صف ملف واحد: أيقونة حالة، اسم، عدد التكستشرات."""

    def sizeHint(self, option, index):
        return QSize(10, ROW_H)

    def paint(self, painter: QPainter, option, index):
        data = index.data(DATA) or {}
        rect = option.rect
        rtl = option.direction == Qt.RightToLeft

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        body = rect.adjusted(3, 2, -3, -2)
        if option.state & QStyle.State_Selected:
            painter.setBrush(QColor(theme.ACCENT_DEEP))
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
        elif option.state & QStyle.State_MouseOver:
            painter.setBrush(QColor(theme.BG_HOVER))
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(QColor(theme.BG_ELEV))
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(body, theme.R_CTRL, theme.R_CTRL)

        # أيقونة الحالة على جهة البداية
        glyph = 15
        gx = (body.right() - PAD - glyph) if rtl else (body.left() + PAD)
        gy = body.top() + (body.height() - glyph) // 2
        name = "warn" if data.get("error") else "layers"
        tint = theme.WARN if data.get("error") else (
            theme.ACCENT if data.get("loaded") else theme.TXT_MUTE)
        painter.drawPixmap(gx, gy, icons.pixmap(name, glyph, tint))

        # عدّاد التكستشرات على الجهة المقابلة
        count = data.get("count")
        badge = "" if count is None else str(count)
        painter.setFont(theme.font(9))
        badge_w = painter.fontMetrics().horizontalAdvance(badge) + 2 if badge else 0
        if badge:
            painter.setPen(QColor(theme.TXT_MUTE))
            bx = body.left() + PAD if rtl else body.right() - PAD - badge_w
            painter.drawText(QRect(bx, body.top(), badge_w, body.height()),
                             Qt.AlignVCenter | Qt.AlignCenter, badge)

        # نقطة التعديل
        dot = 6
        dot_w = 0
        if data.get("edited"):
            dot_w = dot + 6
            dx = (body.left() + PAD + badge_w + 6) if rtl else \
                 (body.right() - PAD - badge_w - dot_w)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.WARN))
            painter.drawEllipse(dx, body.top() + body.height() // 2 - dot // 2,
                                dot, dot)

        # الاسم بين الاثنين، مع فرجة تفصله عن العدّاد ونقطة التعديل
        gap = 10
        used = PAD + glyph + PAD + badge_w + dot_w + PAD + gap
        text_w = max(20, body.width() - used)
        tx = (body.left() + PAD + badge_w + dot_w + gap) if rtl else \
             (gx + glyph + PAD)
        painter.setFont(theme.font(10))
        painter.setPen(QColor(theme.TXT if data.get("loaded") else theme.TXT_DIM))
        label = painter.fontMetrics().elidedText(data.get("name", ""),
                                                 Qt.ElideMiddle, text_w)
        painter.drawText(QRect(tx, body.top(), text_w, body.height()),
                         Qt.AlignVCenter | (Qt.AlignRight if rtl else Qt.AlignLeft),
                         label)
        painter.restore()


class FilePanel(QWidget):
    """قائمة الملفات المفتوحة."""

    fileSelected = Signal(int)          # فهرس الملف

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self._rows = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("open", 15, theme.TXT_DIM))
        title = QLabel("الملفات المفتوحة")
        title.setObjectName("PanelTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count_label)
        outer.addLayout(head)

        self.list = QListWidget()
        self.list.setItemDelegate(FileDelegate(self))
        self.list.setMouseTracking(True)
        self.list.setSpacing(1)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._on_row)
        outer.addWidget(self.list, 1)

    # -------------------------------------------------------------- المحتوى

    def populate(self, documents):
        """بناء القائمة من كائنات الملفات."""
        self.list.blockSignals(True)
        self.list.clear()
        self._rows = {}
        for i, doc in enumerate(documents):
            item = QListWidgetItem()
            item.setData(DATA, self._row_data(doc))
            item.setToolTip(doc.path)
            self.list.addItem(item)
            self._rows[i] = item
        self.list.blockSignals(False)
        self.count_label.setText(str(len(documents)))

        # ارتفاع مناسب للعدد، بحد أقصى حتى لا تبتلع قائمة التكستشرات
        rows = min(max(len(documents), 1), 6)
        self.list.setFixedHeight(rows * (ROW_H + 2) + 6)

    @staticmethod
    def _row_data(doc):
        return {
            "name": doc.name,
            "loaded": doc.ytd is not None,
            "edited": bool(doc.edits),
            "error": doc.error,
            "count": len(doc.ytd.textures) if doc.ytd is not None else None,
        }

    def refresh(self, index, doc):
        item = self._rows.get(index)
        if item is not None:
            item.setData(DATA, self._row_data(doc))
            item.setToolTip(doc.error or doc.path)

    def select(self, index):
        item = self._rows.get(index)
        if item is not None and self.list.currentItem() is not item:
            self.list.setCurrentItem(item)

    def _on_row(self, row):
        if row >= 0:
            self.fileSelected.emit(row)

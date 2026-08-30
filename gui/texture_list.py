"""
لوحة التكستشرات: بحث + قائمة مرسومة يدويًا.

الرسم بمفوّض مخصص بدل عناصر Qt الجاهزة يسمح بعرض المصغّرة والاسم والأبعاد
والصيغة وحالة التعديل في صف واحد مضغوط، وهو ما تحتاجه القواميس الكبيرة التي
قد تضم مئات التكستشرات.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QStyle, QStyledItemDelegate,
                               QVBoxLayout, QWidget)

from . import icons, theme
from .canvas import numpy_to_qimage

THUMB = 46
ROW_H = 62
PAD = 9

DATA = Qt.UserRole + 1


def _checker_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor("#2C3038"))
    p = QPainter(pm)
    for y in range(0, size, 7):
        for x in range(0, size, 7):
            if ((x // 7) + (y // 7)) % 2 == 0:
                p.fillRect(x, y, 7, 7, QColor("#23272E"))
    p.end()
    return pm


class TextureDelegate(QStyledItemDelegate):
    """يرسم صفًا واحدًا: مصغّرة، اسم، سطر معلومات، ومؤشر حالة."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checker = _checker_pixmap(THUMB)
        self._broken = icons.pixmap("warn", 22, theme.WARN)

    def sizeHint(self, option, index):
        return QSize(10, ROW_H)

    def paint(self, painter: QPainter, option, index):
        data = index.data(DATA) or {}
        rect = option.rect
        rtl = option.direction == Qt.RightToLeft

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        # ---- الخلفية
        body = rect.adjusted(3, 2, -3, -2)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        if selected:
            painter.setBrush(QColor(theme.ACCENT_DEEP))
            painter.setPen(QPen(QColor(theme.ACCENT), 1))
        elif hovered:
            painter.setBrush(QColor(theme.BG_HOVER))
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(QColor(theme.BG_ELEV))
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(body, theme.R_CTRL, theme.R_CTRL)

        if selected:
            # شريط على الحافة البادئة يميّز الصف المختار بلا ضجيج لوني
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.ACCENT))
            bar_x = body.right() - 3 if rtl else body.left()
            painter.drawRoundedRect(bar_x, body.top() + 9, 3,
                                    body.height() - 18, 1.5, 1.5)

        # ---- المصغّرة (على جهة البداية حسب اتجاه الواجهة)
        thumb_x = (body.right() - PAD - THUMB) if rtl else (body.left() + PAD)
        thumb_y = body.top() + (body.height() - THUMB) // 2
        thumb_rect = QRect(thumb_x, thumb_y, THUMB, THUMB)

        painter.save()
        painter.setClipRect(thumb_rect)
        painter.drawPixmap(thumb_rect.topLeft(), self._checker)
        painter.restore()

        pm = data.get("thumb")
        if pm is not None and not pm.isNull():
            x = thumb_rect.x() + (THUMB - pm.width()) // 2
            y = thumb_rect.y() + (THUMB - pm.height()) // 2
            painter.drawPixmap(x, y, pm)
        else:
            painter.drawPixmap(thumb_rect.x() + (THUMB - 22) // 2,
                               thumb_rect.y() + (THUMB - 22) // 2, self._broken)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(theme.BORDER_HI), 1))
        painter.drawRoundedRect(thumb_rect, 5, 5)

        # ---- النصوص
        text_left = body.left() + PAD
        text_right = thumb_rect.left() - PAD
        if not rtl:
            text_left = thumb_rect.right() + PAD
            text_right = body.right() - PAD
        text_rect = QRect(text_left, body.top() + 9,
                          max(10, text_right - text_left), body.height() - 18)
        align = (Qt.AlignRight if rtl else Qt.AlignLeft) | Qt.AlignTop

        name_font = theme.font(10, medium=True)
        painter.setFont(name_font)
        painter.setPen(QColor(theme.TXT if data.get("editable", True)
                              else theme.WARN))
        name = painter.fontMetrics().elidedText(
            data.get("name", ""), Qt.ElideMiddle, text_rect.width() - 16)
        painter.drawText(text_rect, align, name)

        painter.setFont(theme.font(9))
        painter.setPen(QColor(theme.TXT_MUTE))
        meta = "%s · %s" % (data.get("size", ""), data.get("format", ""))
        meta_rect = QRect(text_rect.left(), text_rect.top() + 22,
                          text_rect.width(), 18)
        meta = painter.fontMetrics().elidedText(meta, Qt.ElideRight,
                                                meta_rect.width())
        painter.drawText(meta_rect, align, meta)

        # ---- مؤشر التعديل
        if data.get("edited"):
            dot_x = (body.left() + PAD + 3) if rtl else (body.right() - PAD - 9)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.WARN))
            painter.drawEllipse(dot_x, body.top() + body.height() // 2 - 3, 6, 6)

        painter.restore()


class TexturePanel(QWidget):
    """قائمة التكستشرات داخل القاموس المفتوح، مع بحث فوري."""

    textureSelected = Signal(int)          # فهرس التكستشر

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self._entries = []
        self._rows = {}                    # فهرس التكستشر -> QListWidgetItem

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(9)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("layers", 15, theme.TXT_DIM))
        title = QLabel("التكستشرات")
        title.setObjectName("PanelTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("Hint")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count_label)
        outer.addLayout(head)

        self.search = QLineEdit()
        self.search.setPlaceholderText("ابحث باسم التكستشر…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(34)
        self.search.textChanged.connect(self._apply_filter)
        outer.addWidget(self.search)

        self.list = QListWidget()
        self.list.setItemDelegate(TextureDelegate(self))
        self.list.setMouseTracking(True)
        self.list.setSpacing(1)
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentItemChanged.connect(self._on_current_changed)
        outer.addWidget(self.list, 1)

        self.summary = QLabel("لم يُفتح أي ملف بعد")
        self.summary.setObjectName("Hint")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)

    # -------------------------------------------------------------- المحتوى

    def clear(self):
        self._entries = []
        self._rows = {}
        self.list.clear()
        self.count_label.setText("")
        self.summary.setText("لم يُفتح أي ملف بعد")

    def populate(self, ytd, progress=None):
        """تعبئة القائمة من قاموس محمّل."""
        self.list.blockSignals(True)
        self.list.clear()
        self._entries = list(ytd.textures)
        self._rows = {}

        broken = 0
        for i, entry in enumerate(self._entries):
            if progress is not None:
                progress(i, len(self._entries))

            thumb = None
            if entry.editable:
                try:
                    arr = ytd.thumbnail(entry, THUMB)
                    thumb = QPixmap.fromImage(
                        numpy_to_qimage(arr).scaled(THUMB, THUMB,
                                                    Qt.KeepAspectRatio,
                                                    Qt.SmoothTransformation))
                except Exception:
                    thumb = None
            if thumb is None:
                broken += 1

            item = QListWidgetItem()
            item.setData(DATA, {
                "index": entry.index,
                "name": entry.name,
                "size": "%d×%d" % (entry.width, entry.height),
                "format": entry.format_name,
                "editable": entry.editable,
                "edited": False,
                "thumb": thumb,
            })
            item.setToolTip(entry.error or entry.describe())
            self.list.addItem(item)
            self._rows[entry.index] = item

        self.list.blockSignals(False)
        self.count_label.setText("%d" % len(self._entries))
        if broken:
            self.summary.setText(
                "%d تكستشر بصيغة غير مدعومة، ستُنسخ كما هي عند الحفظ."
                % broken)
        else:
            self.summary.setText("كل التكستشرات قابلة للتحرير.")

        if self._entries:
            self.list.setCurrentRow(0)

    # -------------------------------------------------------------- التحديث

    def mark_edited(self, index, edited=True):
        item = self._rows.get(index)
        if item is None:
            return
        data = dict(item.data(DATA) or {})
        data["edited"] = bool(edited)
        item.setData(DATA, data)

    def update_thumbnail(self, index, arr):
        """تحديث المصغّرة بعد تعديل التكستشر."""
        item = self._rows.get(index)
        if item is None:
            return
        data = dict(item.data(DATA) or {})
        data["thumb"] = QPixmap.fromImage(
            numpy_to_qimage(arr).scaled(THUMB, THUMB, Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation))
        item.setData(DATA, data)

    def clear_all_edited(self):
        for index in self._rows:
            self.mark_edited(index, False)

    def select_index(self, index):
        item = self._rows.get(index)
        if item is not None:
            self.list.setCurrentItem(item)

    # ---------------------------------------------------------------- البحث

    def _apply_filter(self, text):
        needle = (text or "").strip().lower()
        visible = 0
        for i in range(self.list.count()):
            item = self.list.item(i)
            data = item.data(DATA) or {}
            match = needle in data.get("name", "").lower()
            item.setHidden(not match)
            visible += int(match)
        self.count_label.setText(
            "%d" % len(self._entries) if not needle
            else "%d / %d" % (visible, len(self._entries)))

    def _on_current_changed(self, current, _previous):
        if current is None:
            return
        data = current.data(DATA) or {}
        if "index" in data:
            self.textureSelected.emit(data["index"])

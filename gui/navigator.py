"""
مصغّرة الملاحة.

تعرض التكستشر كاملًا في مربّع صغير مع مستطيل يبيّن الجزء الظاهر على الشاشة.
على تكستشر 3072×3072 معروض بنسبة ٥٠٪ لا ترى إلا سُدس المساحة، فبدونها يضيع
إحساسك بمكانك. النقر أو السحب داخلها ينقل العرض مباشرة.
"""

from __future__ import annotations

from ..i18n import t

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme
from .canvas import numpy_to_qimage

MAX_SIDE = 168


class Navigator(QWidget):
    """مصغّرة تفاعلية لموضع العرض داخل التكستشر."""

    centerRequested = Signal(QPointF)      # نقطة بإحداثيات الصورة

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(MAX_SIDE + 16)
        self.setCursor(Qt.PointingHandCursor)
        self.setLayoutDirection(Qt.LeftToRight)

        self._thumb: QPixmap | None = None
        self._image_size = (0, 0)
        self._viewport = QRectF()
        self._dragging = False

    # -------------------------------------------------------------- المحتوى

    def set_image(self, array: np.ndarray | None):
        if array is None:
            self._thumb = None
            self._image_size = (0, 0)
            self.update()
            return

        h, w = array.shape[:2]
        self._image_size = (w, h)
        # تصغير بالقفز لا بالتنعيم: على 3072×3072 الفرق بين ٤ أجزاء من الثانية
        # وجزء من الألف، والنتيجة كافية لمصغّرة بعرض 168 بكسل
        step = max(1, int(max(w, h) / MAX_SIDE))
        small = np.ascontiguousarray(array[::step, ::step])
        image = numpy_to_qimage(small)
        self._thumb = QPixmap.fromImage(
            image.scaled(MAX_SIDE, MAX_SIDE, Qt.KeepAspectRatio,
                         Qt.SmoothTransformation))
        self.update()

    def set_viewport(self, rect: QRectF):
        self._viewport = QRectF(rect)
        self.update()

    # -------------------------------------------------------------- الهندسة

    def _thumb_rect(self) -> QRectF:
        if self._thumb is None:
            return QRectF()
        x = (self.width() - self._thumb.width()) / 2
        y = (self.height() - self._thumb.height()) / 2
        return QRectF(x, y, self._thumb.width(), self._thumb.height())

    def _to_image(self, pos: QPointF) -> QPointF | None:
        box = self._thumb_rect()
        if box.isEmpty() or not self._image_size[0]:
            return None
        tx = (pos.x() - box.left()) / box.width()
        ty = (pos.y() - box.top()) / box.height()
        tx = max(0.0, min(1.0, tx))
        ty = max(0.0, min(1.0, ty))
        return QPointF(tx * self._image_size[0], ty * self._image_size[1])

    # -------------------------------------------------------------- الأحداث

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        point = self._to_image(ev.position())
        if point is not None:
            self._dragging = True
            self.centerRequested.emit(point)

    def mouseMoveEvent(self, ev):
        if not self._dragging:
            return
        point = self._to_image(ev.position())
        if point is not None:
            self.centerRequested.emit(point)

    def mouseReleaseEvent(self, ev):
        self._dragging = False

    # ---------------------------------------------------------------- الرسم

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        if self._thumb is None:
            p.setPen(QColor(theme.TXT_MUTE))
            p.drawText(self.rect(), Qt.AlignCenter, t("لا يوجد تكستشر"))
            p.end()
            return

        box = self._thumb_rect()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.BG_CANVAS))
        p.drawRoundedRect(box.adjusted(-2, -2, 2, 2), 5, 5)
        p.drawPixmap(box.topLeft(), self._thumb)

        width, height = self._image_size
        if width and height and not self._viewport.isEmpty():
            scale_x = box.width() / width
            scale_y = box.height() / height
            view = QRectF(
                box.left() + self._viewport.left() * scale_x,
                box.top() + self._viewport.top() * scale_y,
                self._viewport.width() * scale_x,
                self._viewport.height() * scale_y).intersected(box)

            if not view.isEmpty():
                # تعتيم ما هو خارج نافذة العرض ليبرز الجزء الظاهر
                p.setBrush(QColor(0, 0, 0, 110))
                p.setPen(Qt.NoPen)
                p.drawRect(QRectF(box.left(), box.top(),
                                  view.left() - box.left(), box.height()))
                p.drawRect(QRectF(view.right(), box.top(),
                                  box.right() - view.right(), box.height()))
                p.drawRect(QRectF(view.left(), box.top(),
                                  view.width(), view.top() - box.top()))
                p.drawRect(QRectF(view.left(), view.bottom(),
                                  view.width(), box.bottom() - view.bottom()))

                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(theme.ACCENT), 1.5))
                p.drawRect(view)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(theme.BORDER_HI), 1))
        p.drawRoundedRect(box.adjusted(-2, -2, 2, 2), 5, 5)
        p.end()

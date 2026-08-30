"""
غلاف النافذة: نافذة بلا إطار نظام، بشريط عنوان مخصص وحواف قابلة للسحب.

بناء الإطار يدويًا هو ما يعطي الواجهة شخصيتها: زوايا دائرية، ظل خارجي،
وشريط علوي يحمل أوامر الملف بدل شريط ويندوز الرمادي. مقابل ذلك يلزم تنفيذ
السحب وتغيير الحجم والتكبير يدويًا، وهو ما يقوم به هذا الملف.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)

from . import icons, theme
from .widgets import IconButton

SHADOW_MARGIN = 10          # هامش خارجي يستوعب الظل


class TitleBar(QWidget):
    """الشريط العلوي: هوية التطبيق، اسم الملف المفتوح، وأزرار النافذة."""

    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()
    aboutRequested = Signal()
    homeRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(theme.TITLEBAR_H)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 8, 0)
        row.setSpacing(10)

        self.btn_home = IconButton("layers", "الرجوع إلى الأدوات", 30, 18)
        self.btn_home.clicked.connect(self.homeRequested)
        self.btn_home.hide()
        row.addWidget(self.btn_home)

        # اسم المنتج يبقى بالإنجليزية كما هو، والواجهة حوله عربية
        title = QLabel(theme.APP_NAME)
        title.setFont(theme.font(10, medium=True))
        title.setLayoutDirection(Qt.LeftToRight)
        row.addWidget(title)

        sep = QLabel("|")
        sep.setStyleSheet("color: %s;" % theme.BORDER_HI)
        row.addWidget(sep)

        self.file_label = QLabel("لا يوجد ملف مفتوح")
        self.file_label.setObjectName("Hint")
        row.addWidget(self.file_label)

        self.dirty_dot = QLabel("●")
        self.dirty_dot.setStyleSheet("color: %s; font-size: 9pt;" % theme.WARN)
        self.dirty_dot.setToolTip("توجد تعديلات غير محفوظة")
        self.dirty_dot.hide()
        row.addWidget(self.dirty_dot)

        row.addStretch(1)

        self.btn_about = IconButton("info", "عن البرنامج", 34, 16)
        self.btn_about.clicked.connect(self.aboutRequested)
        row.addWidget(self.btn_about)

        self.btn_min = IconButton("minimize", "تصغير", 34, 16)
        self.btn_max = IconButton("maximize", "تكبير", 34, 15)
        self.btn_close = IconButton("close", "إغلاق", 34, 16)
        self.btn_min.clicked.connect(self.minimizeRequested)
        self.btn_max.clicked.connect(self.maximizeRequested)
        self.btn_close.clicked.connect(self.closeRequested)
        for btn in (self.btn_min, self.btn_max, self.btn_close):
            row.addWidget(btn)

    # ------------------------------------------------------------- عرض الحالة

    def set_file(self, name: str | None):
        self.file_label.setText(name or "لا يوجد ملف مفتوح")

    def set_context(self, text: str | None):
        self.file_label.setText(text or "")

    def set_dirty(self, dirty: bool):
        self.dirty_dot.setVisible(bool(dirty))

    def set_maximized(self, maximized: bool):
        self.btn_max.set_icon_name("restore" if maximized else "maximize")
        self.btn_max.setToolTip("استعادة" if maximized else "تكبير")


class FramelessWindow(QWidget):
    """
    نافذة بلا إطار نظام.

    الطبقات: هذه النافذة الشفافة -> هامش الظل -> الإطار المرسوم (#Shell)
    الذي يحوي شريط العنوان ومساحة المحتوى.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setMinimumSize(1080, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*([SHADOW_MARGIN] * 4))
        outer.setSpacing(0)

        self.frame = QFrame()
        self.frame.setObjectName("Shell")
        self.frame.setMouseTracking(True)
        outer.addWidget(self.frame)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 190))
        self.frame.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self.frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        self.title_bar = TitleBar()
        self.title_bar.minimizeRequested.connect(self.showMinimized)
        self.title_bar.maximizeRequested.connect(self.toggle_maximized)
        self.title_bar.closeRequested.connect(self.close)
        self.title_bar.aboutRequested.connect(self.show_about)
        self.title_bar.homeRequested.connect(self.show_home)
        inner.addWidget(self.title_bar)

        self.body = QWidget()
        self.body.setMouseTracking(True)
        inner.addWidget(self.body, 1)

        self._drag_offset: QPoint | None = None
        self._resize_edges = ""
        self._resize_origin = QRect()
        self._press_global = QPoint()

    def show_about(self):
        pass

    def show_home(self):
        pass

    # ------------------------------------------------------------- التكبير

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        # يُستدعى أيضًا أثناء البناء قبل تركيب التخطيط
        if self.layout() is None or not hasattr(self, "title_bar"):
            return
        maximized = self.isMaximized()
        margin = 0 if maximized else SHADOW_MARGIN
        self.layout().setContentsMargins(margin, margin, margin, margin)
        self.frame.setStyleSheet(
            "#Shell { border-radius: 0px; }" if maximized else "")
        self.title_bar.set_maximized(maximized)

    # ------------------------------------------------ السحب وتغيير الحجم

    def _edges_at(self, pos: QPoint) -> str:
        """أي حواف النافذة تقع تحت المؤشر."""
        if self.isMaximized():
            return ""
        margin = SHADOW_MARGIN
        grip = theme.RESIZE_EDGE + margin
        edges = ""
        if pos.y() <= grip:
            edges += "t"
        elif pos.y() >= self.height() - grip:
            edges += "b"
        if pos.x() <= grip:
            edges += "l"
        elif pos.x() >= self.width() - grip:
            edges += "r"
        return edges

    @staticmethod
    def _cursor_for(edges: str):
        if edges in ("tl", "br"):
            return Qt.SizeFDiagCursor
        if edges in ("tr", "bl"):
            return Qt.SizeBDiagCursor
        if edges in ("l", "r"):
            return Qt.SizeHorCursor
        if edges in ("t", "b"):
            return Qt.SizeVerCursor
        return Qt.ArrowCursor

    def _in_title_bar(self, pos: QPoint) -> bool:
        local = self.title_bar.mapFrom(self, pos)
        if not self.title_bar.rect().contains(local):
            return False
        child = self.title_bar.childAt(local)
        return not isinstance(child, IconButton)

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return
        pos = ev.position().toPoint()
        self._resize_edges = self._edges_at(pos)
        if self._resize_edges:
            self._resize_origin = self.geometry()
            self._press_global = ev.globalPosition().toPoint()
        elif self._in_title_bar(pos):
            self._drag_offset = (ev.globalPosition().toPoint()
                                 - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()

        if self._resize_edges and ev.buttons() & Qt.LeftButton:
            self._apply_resize(ev.globalPosition().toPoint())
            return

        if self._drag_offset is not None and ev.buttons() & Qt.LeftButton:
            if self.isMaximized():
                # الاستعادة أثناء السحب: تبقى النافذة تحت المؤشر
                ratio = pos.x() / max(1, self.width())
                self.showNormal()
                width = self.width()
                self._drag_offset = QPoint(int(width * ratio), pos.y())
            self.move(ev.globalPosition().toPoint() - self._drag_offset)
            return

        self.setCursor(QCursor(self._cursor_for(self._edges_at(pos))))

    def mouseReleaseEvent(self, ev):
        self._drag_offset = None
        self._resize_edges = ""
        self.unsetCursor()

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._in_title_bar(
                ev.position().toPoint()):
            self.toggle_maximized()

    def _apply_resize(self, global_pos: QPoint):
        delta = global_pos - self._press_global
        rect = QRect(self._resize_origin)
        minimum = self.minimumSize()

        if "l" in self._resize_edges:
            rect.setLeft(min(rect.left() + delta.x(),
                             rect.right() - minimum.width()))
        if "r" in self._resize_edges:
            rect.setRight(max(rect.right() + delta.x(),
                              rect.left() + minimum.width()))
        if "t" in self._resize_edges:
            rect.setTop(min(rect.top() + delta.y(),
                            rect.bottom() - minimum.height()))
        if "b" in self._resize_edges:
            rect.setBottom(max(rect.bottom() + delta.y(),
                               rect.top() + minimum.height()))
        self.setGeometry(rect)

    def leaveEvent(self, ev):
        self.unsetCursor()
        super().leaveEvent(ev)

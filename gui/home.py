"""
الشاشة الرئيسية: مركز اختيار الأداة.

الخلفية نقشة كنتور خفيفة فوق كحلي عميق، مستمدّة من هوية Wun. البطاقات
ترتفع قليلًا عند التحويم وتضيء حافتها، وتظهر عند الفتح بتتابع قصير.
كل الحركة على عناصر الواجهة فقط، ولا شيء منها يمسّ الكانفس.
"""

from __future__ import annotations

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, Qt, QTimer,
                            QVariantAnimation)
from PySide6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath,
                           QPen)
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from . import backdrop, icons, theme

CARD_W = 274
CARD_H = 184
LIFT = 6.0


class ToolCard(QWidget):
    """بطاقة أداة قابلة للنقر."""

    from PySide6.QtCore import Signal
    clicked = Signal(str)

    def __init__(self, key, icon_name, title, description, ready=True,
                 parent=None):
        super().__init__(parent)
        self.key = key
        self.icon_name = icon_name
        self.ready = ready
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor if ready else Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover, True)

        self._lift = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self._animation.valueChanged.connect(self._on_lift)

        column = QVBoxLayout(self)
        column.setContentsMargins(22, 20, 22, 20)
        column.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(0)
        self.glyph = QLabel()
        self.glyph.setPixmap(icons.pixmap(
            icon_name, 34, theme.ACCENT if ready else theme.TXT_MUTE, 1.5,
            gradient=ready))
        head.addWidget(self.glyph)
        head.addStretch(1)
        if not ready:
            soon = QLabel("قريبًا")
            soon.setStyleSheet(
                "color: %s; background: %s; border-radius: 5px;"
                "padding: 2px 8px; font-size: 8pt;" % (theme.WARN, "#2A2318"))
            head.addWidget(soon)
        column.addLayout(head)
        column.addStretch(1)

        self.title = QLabel(title)
        self.title.setFont(theme.font(13, medium=True))
        self.title.setStyleSheet("color: %s; background: transparent;"
                                 % (theme.TXT if ready else theme.TXT_DIM))
        column.addWidget(self.title)

        self.description = QLabel(description)
        self.description.setObjectName("Hint")
        self.description.setWordWrap(True)
        self.description.setStyleSheet("background: transparent;")
        column.addWidget(self.description)

    def _on_lift(self, value):
        self._lift = float(value)
        self.update()

    def _animate_to(self, target):
        self._animation.stop()
        self._animation.setStartValue(self._lift)
        self._animation.setEndValue(target)
        self._animation.start()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.ready:
            self.clicked.emit(self.key)

    def enterEvent(self, ev):
        if self.ready:
            self._animate_to(LIFT)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._animate_to(0.0)
        super().leaveEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        progress = self._lift / LIFT if LIFT else 0.0
        rect = QRectF(self.rect()).adjusted(1, 1 - self._lift, -1,
                                            -1 - self._lift)
        radius = theme.R_PANEL + 3

        if progress > 0.01:
            # هالة ناعمة أسفل البطاقة تعطي إحساس الارتفاع
            halo = QColor(theme.ACCENT)
            for step in range(4):
                halo.setAlpha(int(16 * progress / (step + 1)))
                p.setPen(Qt.NoPen)
                p.setBrush(halo)
                spread = 2 + step * 3
                p.drawRoundedRect(rect.adjusted(-spread, -spread + 3,
                                                spread, spread + 3),
                                  radius + spread, radius + spread)

        body = QColor(theme.BG_PANEL)
        if progress > 0:
            body = QColor(theme.BG_ELEV)
        p.setBrush(body)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, radius, radius)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(path)
        backdrop.paint(p, rect.toRect(), offset=self.mapTo(
            self.window(), QPointF(0, 0).toPoint()), strength=0.13,
            thickness=0.075)
        p.restore()

        border = QLinearGradient(rect.topRight(), rect.bottomLeft())
        if progress > 0.01:
            border.setColorAt(0.0, QColor(theme.ACCENT_HI))
            border.setColorAt(0.5, QColor(theme.ACCENT))
            border.setColorAt(1.0, QColor(theme.ACCENT_DEEP))
            p.setPen(QPen(border, 1.4))
        else:
            p.setPen(QPen(QColor(theme.BORDER), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, radius, radius)

        if progress > 0.01:
            top = QLinearGradient(rect.left(), 0, rect.right(), 0)
            top.setColorAt(0.0, QColor(0, 0, 0, 0))
            mid = QColor(theme.ACCENT_HI)
            mid.setAlpha(int(230 * progress))
            top.setColorAt(0.5, mid)
            top.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(top)
            p.drawRoundedRect(QRectF(rect.left() + 14, rect.top(),
                                     rect.width() - 28, 2.4), 1.2, 1.2)
        p.end()


class HomeScreen(QWidget):
    """شاشة اختيار الأداة."""

    from PySide6.QtCore import Signal
    toolChosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Home")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 24, 40, 18)
        outer.setSpacing(0)
        outer.addStretch(2)

        mark = QLabel()
        mark.setPixmap(icons.pixmap("layers", 86, theme.ACCENT, 1.45,
                                    gradient=True))
        mark.setAlignment(Qt.AlignCenter)
        outer.addWidget(mark)
        outer.addSpacing(14)

        name = QLabel(theme.APP_NAME)
        name.setFont(theme.font(24, medium=True))
        name.setAlignment(Qt.AlignCenter)
        name.setLayoutDirection(Qt.LeftToRight)
        outer.addWidget(name)

        tagline = QLabel(theme.APP_TAGLINE)
        tagline.setObjectName("Hint")
        tagline.setAlignment(Qt.AlignCenter)
        outer.addWidget(tagline)
        outer.addSpacing(30)

        self.grid = QGridLayout()
        self.grid.setSpacing(18)
        self.grid.setAlignment(Qt.AlignCenter)
        outer.addLayout(self.grid)
        outer.addStretch(3)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        credit = QLabel("%s · الإصدار %s" % (theme.AUTHOR, theme.VERSION))
        credit.setObjectName("Hint")
        copyright_label = QLabel(theme.COPYRIGHT)
        copyright_label.setObjectName("Hint")
        footer.addWidget(credit)
        footer.addStretch(1)
        footer.addWidget(copyright_label)
        outer.addLayout(footer)

        self._cards = []
        self._shown = False

    def add_tool(self, key, icon_name, title, description, ready=True):
        card = ToolCard(key, icon_name, title, description, ready)
        card.clicked.connect(self.toolChosen)
        position = len(self._cards)
        self.grid.addWidget(card, position // 4, position % 4)
        self._cards.append(card)
        return card

    def showEvent(self, ev):
        super().showEvent(ev)
        if self._shown:
            return
        self._shown = True
        for index, card in enumerate(self._cards):
            effect = QGraphicsOpacityEffect(card)
            effect.setOpacity(0.0)
            card.setGraphicsEffect(effect)
            animation = QVariantAnimation(card)
            animation.setDuration(320)
            animation.setStartValue(0.0)
            animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            animation.valueChanged.connect(effect.setOpacity)
            animation.finished.connect(
                lambda c=card: c.setGraphicsEffect(None))
            QTimer.singleShot(90 * index, animation.start)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(theme.BG_APP))
        backdrop.paint(p, self.rect(), strength=0.30, thickness=0.075)
        backdrop.glow(p, self.rect(), alpha=30)
        p.end()

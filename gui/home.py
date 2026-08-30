"""
الشاشة الرئيسية: مركز اختيار الأداة.

أول ما يفتح البرنامج تظهر هذه الشاشة بالهوية وبطاقات الأدوات المتاحة. كل
بطاقة تفتح أداتها، والرجوع إلى هنا متاح دائمًا من زر في شريط العنوان.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from . import icons, theme

CARD_W = 268
CARD_H = 176


class ToolCard(QWidget):
    """بطاقة أداة قابلة للنقر."""

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

        column = QVBoxLayout(self)
        column.setContentsMargins(20, 18, 20, 18)
        column.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(0)
        self.glyph = QLabel()
        self.glyph.setPixmap(icons.pixmap(icon_name, 30, theme.ACCENT if ready
                                          else theme.TXT_MUTE, 1.6))
        head.addWidget(self.glyph)
        head.addStretch(1)
        if not ready:
            soon = QLabel("قريبًا")
            soon.setStyleSheet(
                "color: %s; background: %s; border-radius: 5px;"
                "padding: 2px 8px; font-size: 8pt;"
                % (theme.WARN, "#2A2318"))
            head.addWidget(soon)
        column.addLayout(head)

        column.addStretch(1)

        self.title = QLabel(title)
        self.title.setFont(theme.font(13, medium=True))
        self.title.setStyleSheet("color: %s;"
                                 % (theme.TXT if ready else theme.TXT_DIM))
        column.addWidget(self.title)

        self.description = QLabel(description)
        self.description.setObjectName("Hint")
        self.description.setWordWrap(True)
        column.addWidget(self.description)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.ready:
            self.clicked.emit(self.key)

    def enterEvent(self, ev):
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.update()
        super().leaveEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        hovered = self.underMouse() and self.ready
        p.setBrush(QColor(theme.BG_ELEV if hovered else theme.BG_PANEL))
        p.setPen(QPen(QColor(theme.ACCENT if hovered else theme.BORDER),
                      1.4 if hovered else 1.0))
        p.drawRoundedRect(rect, theme.R_PANEL + 2, theme.R_PANEL + 2)

        if hovered:
            # شريط علوي رفيع بلون التمييز يوضّح البطاقة النشطة
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.ACCENT))
            p.drawRoundedRect(QRectF(rect.left() + 16, rect.top(),
                                     rect.width() - 32, 3), 2, 2)
        p.end()


class HomeScreen(QWidget):
    """شاشة اختيار الأداة."""

    toolChosen = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Home")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 24, 40, 18)
        outer.setSpacing(0)

        outer.addStretch(2)

        mark = QLabel()
        mark.setPixmap(icons.pixmap("layers", 68, theme.ACCENT, 1.5))
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
        self.grid.setSpacing(16)
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

    def add_tool(self, key, icon_name, title, description, ready=True):
        card = ToolCard(key, icon_name, title, description, ready)
        card.clicked.connect(self.toolChosen)
        position = len(self._cards)
        self.grid.addWidget(card, position // 3, position % 3)
        self._cards.append(card)
        return card

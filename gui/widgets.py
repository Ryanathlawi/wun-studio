"""
عناصر واجهة قابلة لإعادة الاستخدام.

كلها مبنية على عناصر Qt القياسية مع رسم إضافي بسيط، فتبقى الواجهة متسقة
دون تكرار كود التنسيق في كل لوحة.
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QTransform
from PySide6.QtWidgets import (QAbstractSpinBox, QColorDialog, QFrame,
                               QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QSlider, QSpinBox, QToolButton, QVBoxLayout,
                               QWidget)

from . import icons, theme


class IconButton(QToolButton):
    """زر أيقونة مربّع، يُستخدم في ريل الأدوات وشريط العنوان."""

    def __init__(self, name, tip="", size=38, icon_size=19, checkable=False,
                 danger=False, parent=None):
        super().__init__(parent)
        self._name = name
        self._icon_size = icon_size
        self._danger = danger
        self.setCheckable(checkable)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setAutoRaise(True)
        self._refresh()

    def _refresh(self):
        self.update()

    def set_icon_name(self, name):
        self._name = name
        self.update()

    def enterEvent(self, ev):
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.update()
        super().leaveEvent(ev)

    def nextCheckState(self):
        super().nextCheckState()
        self.update()

    def setChecked(self, value):
        super().setChecked(value)
        self.update()

    def _stroke_color(self):
        if not self.isEnabled():
            return theme.TXT_MUTE
        if self.isChecked():
            return "#FFFFFF"
        if self._danger:
            return theme.DANGER
        return theme.TXT if self.underMouse() else theme.TXT_DIM

    def paintEvent(self, ev):
        """رسم الخلفية والأيقونة في تمريرة واحدة بلا اعتماد على نمط Qt."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        if self.isChecked():
            p.setPen(Qt.NoPen)
            # الأداة المختارة تبقى مميّزة حتى وهي معطّلة، لكن بلون أخفت
            p.setBrush(QColor(theme.ACCENT if self.isEnabled()
                              else theme.ACCENT_DEEP))
            p.drawRoundedRect(rect, theme.R_CTRL, theme.R_CTRL)
        elif self.underMouse() and self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.BG_HOVER))
            p.drawRoundedRect(rect, theme.R_CTRL, theme.R_CTRL)

        pm = icons.pixmap(self._name, self._icon_size, self._stroke_color())
        p.drawPixmap((self.width() - self._icon_size) // 2,
                     (self.height() - self._icon_size) // 2, pm)
        p.end()


class Divider(QFrame):
    """خط فاصل رفيع."""

    def __init__(self, vertical=False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        self.setStyleSheet("color: %s; background: %s; border: none;"
                           % (theme.BORDER, theme.BORDER))
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)


class Badge(QLabel):
    """شارة صغيرة ملوّنة لعرض الصيغة أو الحالة."""

    def __init__(self, text="", tone="dim", parent=None):
        super().__init__(text, parent)
        self.set_tone(tone)
        self.setAlignment(Qt.AlignCenter)

    def set_tone(self, tone):
        colors = {"dim": (theme.TXT_MUTE, theme.BG_INPUT),
                  "accent": (theme.ACCENT, theme.ACCENT_DEEP),
                  "ok": (theme.OK, "#16281F"),
                  "warn": (theme.WARN, "#2A2318"),
                  "danger": (theme.DANGER, "#2A1B1E")}
        fg, bg = colors.get(tone, colors["dim"])
        self.setStyleSheet(
            "color: %s; background: %s; border-radius: 5px;"
            "padding: 2px 7px; font-size: 8pt;" % (fg, bg))


class SectionHeader(QWidget):
    """
    رأس قسم قابل للنقر.

    الأيقونة داخل شريحة مستديرة بلون التمييز، والقسم المفتوح يحمل شريطًا
    رفيعًا على حافته البادئة. الغرض أن تُقرأ الأقسام كوحدات مستقلة لا كنصوص
    متتابعة على خلفية واحدة.
    """

    clicked = Signal()

    CHIP = 28
    PAD = 9

    def __init__(self, title, icon_name=None, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._expanded = True
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setAttribute(Qt.WA_Hover, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(self.PAD, 0, 10, 0)
        row.setSpacing(10)

        # الشريحة عنصر حقيقي في التخطيط لا رسمًا بإحداثيات محسوبة: التخطيط
        # وحده يعرف أين تقع الحافة البادئة في الواجهة العربية
        self.chip = QLabel()
        self.chip.setFixedSize(self.CHIP, self.CHIP)
        self.chip.setAlignment(Qt.AlignCenter)
        self.chip.setStyleSheet("background: transparent;")
        if icon_name:
            self.chip.setPixmap(icons.pixmap(icon_name, 16, theme.ACCENT))
        row.addWidget(self.chip)

        self.label = QLabel(title)
        self.label.setFont(theme.font(10, medium=True))
        self.label.setStyleSheet("background: transparent;")
        row.addWidget(self.label)
        row.addStretch(1)

        self.arrow = QLabel()
        self.arrow.setStyleSheet("background: transparent;")
        self.arrow.setPixmap(icons.pixmap("chevron", 13, theme.TXT_MUTE))
        row.addWidget(self.arrow)

    def set_expanded(self, value):
        self._expanded = bool(value)
        pixmap = icons.pixmap("chevron", 13,
                              theme.ACCENT if self._expanded else theme.TXT_MUTE)
        if not self._expanded:
            pixmap = pixmap.transformed(QTransform().rotate(180))
        self.arrow.setPixmap(pixmap)
        if self._icon_name:
            self.chip.setPixmap(icons.pixmap(
                self._icon_name, 16,
                theme.ACCENT if self._expanded else theme.TXT_DIM))
        self.label.setStyleSheet(
            "background: transparent; color: %s;"
            % (theme.TXT if self._expanded else theme.TXT_DIM))
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()

    def enterEvent(self, ev):
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self.update()
        super().leaveEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rtl = self.layoutDirection() == Qt.RightToLeft
        body = self.rect().adjusted(0, 3, 0, -3)

        if self.underMouse() or self._expanded:
            fill = QColor(theme.BG_ELEV)
            fill.setAlpha(220 if self._expanded else 150)
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(body, theme.R_CTRL, theme.R_CTRL)

        if self._expanded:
            bar = QColor(theme.ACCENT)
            p.setBrush(bar)
            p.setPen(Qt.NoPen)
            x = body.right() - 2 if rtl else body.left()
            p.drawRoundedRect(x, body.top() + 7, 3, body.height() - 14, 1.5, 1.5)

        tint = QColor(theme.ACCENT)
        tint.setAlpha(46 if self._expanded else 26)
        p.setBrush(tint)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(self.chip.geometry(), 8, 8)
        p.end()


class Section(QWidget):
    """
    قسم قابل للطي بعنوان.

    اللوحة الجانبية مزدحمة بطبيعتها، والطي يسمح بإخفاء ما لا يُستعمل الآن
    دون فقد الوصول إليه.
    """

    toggled = Signal(bool)

    def __init__(self, title, icon_name=None, expanded=True, parent=None):
        super().__init__(parent)
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = SectionHeader(title, icon_name)
        self.header.clicked.connect(self.toggle)
        outer.addWidget(self.header)

        self.body = QWidget()
        self.body.setObjectName("SectionBody")
        self._body_layout = QVBoxLayout(self.body)
        self._body_layout.setContentsMargins(12, 6, 12, 14)
        self._body_layout.setSpacing(9)
        outer.addWidget(self.body)

        self.header.set_expanded(expanded)
        self.body.setVisible(expanded)

    def _sync_header(self):
        self.header.set_expanded(self._expanded)

    def toggle(self):
        self.set_expanded(not self._expanded)

    def set_expanded(self, value):
        self._expanded = bool(value)
        self.body.setVisible(self._expanded)
        self._sync_header()
        self.toggled.emit(self._expanded)

    def add(self, widget):
        self._body_layout.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self._body_layout.addLayout(layout)
        return layout


class Field(QWidget):
    """صف: تسمية على اليمين وعنصر تحكم على اليسار."""

    def __init__(self, label, widget, label_width=58, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.label = QLabel(label)
        self.label.setObjectName("PanelTitle")
        self.label.setFixedWidth(label_width)
        row.addWidget(self.label)
        row.addWidget(widget, 1)
        self.widget = widget


class SpinBox(QSpinBox):
    """حقل رقمي بلا أسهم، مع لاحقة وحدة."""

    def __init__(self, minimum=0, maximum=99999, value=0, suffix=" بكسل",
                 parent=None):
        super().__init__(parent)
        self.setRange(minimum, maximum)
        self.setValue(value)
        self.setSuffix(suffix)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setFixedHeight(32)
        # الحد الأدنى للعرض يُحسب افتراضيًا من أكبر قيمة ممكنة، وهو ما
        # يمدّد اللوحة كلها؛ نسمح للحقل بالانكماش بدل ذلك.
        self.setMinimumWidth(58)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)


class SliderField(QWidget):
    """منزلق مع تسمية وقيمة حيّة."""

    valueChanged = Signal(int)

    def __init__(self, label, minimum, maximum, value, suffix="", parent=None):
        super().__init__(parent)
        self._suffix = suffix

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(5)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(label)
        self.label.setObjectName("PanelTitle")
        self.value_label = QLabel()
        self.value_label.setObjectName("Value")
        head.addWidget(self.label)
        head.addStretch(1)
        head.addWidget(self.value_label)
        outer.addLayout(head)

        self.slider = QSlider(Qt.Horizontal)
        # المنزلق يمثّل مقدارًا لا نصًّا: نتركه من اليسار لليمين حتى ينمو
        # التعبئة مع القيمة بدل أن ينعكس مع اتجاه الواجهة العربي.
        self.slider.setLayoutDirection(Qt.LeftToRight)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.valueChanged.connect(self._on_change)
        outer.addWidget(self.slider)

        self._on_change(value)

    def _on_change(self, value):
        self.value_label.setText("%d%s" % (value, self._suffix))
        self.valueChanged.emit(value)

    def value(self):
        return self.slider.value()

    def setValue(self, value):
        self.slider.setValue(value)


class ColorSwatch(QPushButton):
    """زر اختيار لون يعرض عيّنة اللون وقيمته."""

    colorChanged = Signal(QColor)

    def __init__(self, color=QColor(255, 60, 60), parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.clicked.connect(self._choose)
        self.setStyleSheet(
            "text-align: right; padding-right: 42px; padding-left: 10px;")
        self._sync()

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        color = QColor(color)
        if color.isValid() and color != self._color:
            self._color = color
            self._sync()
            self.colorChanged.emit(self.color())

    def _sync(self):
        # عزل ثنائي الاتجاه حتى لا تنتقل علامة # إلى آخر النص في الواجهة العربية
        self.setText("⁦%s⁩ · %d%%"
                     % (self._color.name().upper(),
                        round(self._color.alpha() / 255 * 100)))

    def _choose(self):
        dlg = QColorDialog(self._color, self)
        dlg.setOption(QColorDialog.ShowAlphaChannel, True)
        dlg.setWindowTitle("اختيار اللون")
        if dlg.exec():
            self.setColor(dlg.selectedColor())

    def paintEvent(self, ev):
        super().paintEvent(ev)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        # عيّنة اللون على اليمين مع رقعة شطرنجية تُظهر الشفافية
        size = 22
        y = (self.height() - size) // 2
        x = self.width() - size - 8 if self.layoutDirection() == Qt.LeftToRight else 8
        for row in range(0, size, 6):
            for col in range(0, size, 6):
                shade = "#3A3F4A" if ((row // 6) + (col // 6)) % 2 else "#2A2F38"
                p.fillRect(x + col, y + row, 6, 6, QColor(shade))
        p.setBrush(self._color)
        p.setPen(QPen(QColor(theme.BORDER_HI), 1))
        p.drawRoundedRect(x, y, size, size, 5, 5)
        p.end()


class EmptyState(QWidget):
    """رسالة مركزية تظهر عندما لا يوجد محتوى."""

    def __init__(self, icon_name, title, hint="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, 44, theme.TXT_MUTE, 1.3))
        glyph.setAlignment(Qt.AlignCenter)
        layout.addWidget(glyph)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color: %s;" % theme.TXT_DIM)
        layout.addWidget(self.title)

        if hint:
            self.hint = QLabel(hint)
            self.hint.setObjectName("Hint")
            self.hint.setAlignment(Qt.AlignCenter)
            self.hint.setWordWrap(True)
            layout.addWidget(self.hint)


def elide(label: QLabel, text: str, width: int):
    """قصّ النص بثلاث نقاط إذا تجاوز العرض المتاح."""
    metrics = QFontMetrics(label.font())
    label.setText(metrics.elidedText(text, Qt.ElideMiddle, width))
    label.setToolTip(text)


def fade_in(widget: QWidget, duration=140):
    """ظهور تدريجي خفيف يخفّ من حدّة تبدّل اللوحات."""
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.start(QPropertyAnimation.DeleteWhenStopped)
    return anim

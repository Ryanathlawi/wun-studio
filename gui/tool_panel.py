"""Right sidebar: settings for the active tool, plus image-wide operations."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFontComboBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)


class ColorButton(QPushButton):
    """A button that shows and edits a colour."""

    colorChanged = Signal(QColor)

    def __init__(self, color=QColor(255, 60, 60), parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedHeight(28)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._choose)
        self._refresh()

    def color(self):
        return QColor(self._color)

    def setColor(self, color):
        self._color = QColor(color)
        self._refresh()
        self.colorChanged.emit(self.color())

    def _refresh(self):
        c = self._color
        text_col = "#101010" if c.lightness() > 140 else "#f0f0f0"
        self.setText("%s  %d%%" % (c.name().upper(), round(c.alpha() / 255 * 100)))
        self.setStyleSheet(
            "QPushButton { background: %s; color: %s; border: 1px solid #4a4d54;"
            " border-radius: 6px; font-weight: 600; }" % (c.name(), text_col))

    def _choose(self):
        dlg = QColorDialog(self._color, self)
        dlg.setOption(QColorDialog.ShowAlphaChannel, True)
        if dlg.exec():
            self.setColor(dlg.currentColor())


def _slider(minimum, maximum, value):
    s = QSlider(Qt.Horizontal)
    s.setRange(minimum, maximum)
    s.setValue(value)
    return s


class ToolPanel(QWidget):
    """Everything on the right-hand side of the window."""

    brushSizeChanged = Signal(int)
    brushOpacityChanged = Signal(float)
    brushColorChanged = Signal(QColor)
    antialiasChanged = Signal(bool)
    shapeFilledChanged = Signal(bool)

    textEdited = Signal()
    applyTextRequested = Signal()
    cancelTextRequested = Signal()

    importImageRequested = Signal()
    imageGeometryEdited = Signal()
    applyImageRequested = Signal()
    discardImageRequested = Signal()
    fitImageRequested = Signal()
    resetImageSizeRequested = Signal()
    imageKeepAspectChanged = Signal(bool)

    clearRequested = Signal()
    rotateRequested = Signal(int)
    flipRequested = Signal(bool)
    resizeRequested = Signal()
    cropRequested = Signal()
    revertRequested = Signal()

    exportPngRequested = Signal()
    exportDdsRequested = Signal()
    importTextureRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        # the panel is a fixed-width column; never scroll it sideways
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        # extra right margin leaves room for the vertical scrollbar
        layout.setContentsMargins(10, 10, 16, 10)
        layout.setSpacing(10)

        layout.addWidget(self._build_brush_group())
        layout.addWidget(self._build_text_group())
        layout.addWidget(self._build_placed_image_group())
        layout.addWidget(self._build_image_group())
        layout.addWidget(self._build_export_group())
        layout.addStretch(1)

    # --------------------------------------------------------------- brush

    def _build_brush_group(self):
        box = QGroupBox("Brush / Shape")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setSpacing(8)

        self.size_slider = _slider(1, 512, 16)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 512)
        self.size_spin.setValue(16)
        self.size_spin.setSuffix(" px")
        row = QHBoxLayout()
        row.addWidget(self.size_slider, 1)
        row.addWidget(self.size_spin)
        holder = QWidget()
        holder.setLayout(row)
        form.addRow("Size", holder)

        self.size_slider.valueChanged.connect(self.size_spin.setValue)
        self.size_spin.valueChanged.connect(self.size_slider.setValue)
        self.size_spin.valueChanged.connect(self.brushSizeChanged)

        self.opacity_slider = _slider(1, 100, 100)
        self.opacity_label = QLabel("100%")
        self.opacity_label.setMinimumWidth(38)
        orow = QHBoxLayout()
        orow.addWidget(self.opacity_slider, 1)
        orow.addWidget(self.opacity_label)
        oholder = QWidget()
        oholder.setLayout(orow)
        form.addRow("Opacity", oholder)
        self.opacity_slider.valueChanged.connect(self._on_opacity)

        self.color_button = ColorButton()
        self.color_button.colorChanged.connect(self.brushColorChanged)
        form.addRow("Colour", self.color_button)

        self.antialias_check = QCheckBox("Smooth edges")
        self.antialias_check.setChecked(True)
        self.antialias_check.toggled.connect(self.antialiasChanged)
        form.addRow("", self.antialias_check)

        self.filled_check = QCheckBox("Filled shapes")
        self.filled_check.toggled.connect(self.shapeFilledChanged)
        form.addRow("", self.filled_check)
        return box

    def _on_opacity(self, value):
        self.opacity_label.setText("%d%%" % value)
        self.brushOpacityChanged.emit(value / 100.0)

    # ---------------------------------------------------------------- text

    def _build_text_group(self):
        box = QGroupBox("Text")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        hint = QLabel("Choose the Text tool, then click on the canvas. "
                      "Drag the text to move it.")
        hint.setWordWrap(True)
        hint.setProperty("hint", True)
        layout.addWidget(hint)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Text content")
        self.text_edit.setFixedHeight(58)
        self.text_edit.textChanged.connect(self.textEdited)
        layout.addWidget(self.text_edit)

        form = QFormLayout()
        form.setSpacing(8)

        self.font_combo = QFontComboBox()
        self.font_combo.currentFontChanged.connect(lambda _f: self.textEdited.emit())
        form.addRow("Font", self.font_combo)

        self.font_size = QSpinBox()
        self.font_size.setRange(4, 2000)
        self.font_size.setValue(48)
        self.font_size.setSuffix(" px")
        self.font_size.valueChanged.connect(lambda _v: self.textEdited.emit())
        form.addRow("Size", self.font_size)

        self.text_color = ColorButton(QColor(255, 255, 255))
        self.text_color.colorChanged.connect(lambda _c: self.textEdited.emit())
        form.addRow("Colour", self.text_color)

        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.italic_check = QCheckBox("Italic")
        self.bold_check.toggled.connect(lambda _v: self.textEdited.emit())
        self.italic_check.toggled.connect(lambda _v: self.textEdited.emit())
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        style_row.addStretch(1)
        style_holder = QWidget()
        style_holder.setLayout(style_row)
        form.addRow("Style", style_holder)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.apply_text_btn = QPushButton("Apply text")
        self.apply_text_btn.setProperty("accent", True)
        self.apply_text_btn.clicked.connect(self.applyTextRequested)
        self.cancel_text_btn = QPushButton("Discard")
        self.cancel_text_btn.setProperty("danger", True)
        self.cancel_text_btn.clicked.connect(self.cancelTextRequested)
        buttons.addWidget(self.apply_text_btn, 1)
        buttons.addWidget(self.cancel_text_btn)
        layout.addLayout(buttons)

        self.set_text_controls_enabled(False)
        return box

    def set_text_controls_enabled(self, enabled):
        for w in (self.text_edit, self.font_combo, self.font_size,
                  self.text_color, self.bold_check, self.italic_check,
                  self.apply_text_btn, self.cancel_text_btn):
            w.setEnabled(enabled)

    def load_text_item(self, item):
        """Push a canvas TextItem into the controls without re-emitting."""
        enabled = item is not None
        self.set_text_controls_enabled(enabled)
        if item is None:
            return
        for w in (self.text_edit, self.font_combo, self.font_size,
                  self.bold_check, self.italic_check):
            w.blockSignals(True)
        self.text_edit.setPlainText(item.text)
        self.font_combo.setCurrentFont(item.font())
        self.font_size.setValue(int(item.size))
        self.bold_check.setChecked(item.bold)
        self.italic_check.setChecked(item.italic)
        for w in (self.text_edit, self.font_combo, self.font_size,
                  self.bold_check, self.italic_check):
            w.blockSignals(False)
        self.text_color.blockSignals(True)
        self.text_color.setColor(item.color)
        self.text_color.blockSignals(False)

    def text_settings(self):
        return {
            "text": self.text_edit.toPlainText(),
            "family": self.font_combo.currentFont().family(),
            "size": self.font_size.value(),
            "color": self.text_color.color(),
            "bold": self.bold_check.isChecked(),
            "italic": self.italic_check.isChecked(),
        }

    # -------------------------------------------------------- placed image

    def _build_placed_image_group(self):
        box = QGroupBox("Place image")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        self.import_image_btn = QPushButton("Upload image...")
        self.import_image_btn.setProperty("accent", True)
        self.import_image_btn.clicked.connect(self.importImageRequested)
        layout.addWidget(self.import_image_btn)

        hint = QLabel("Drag the picture to move it, or drag a corner handle "
                      "to resize. Set an exact size below.")
        hint.setWordWrap(True)
        hint.setProperty("hint", True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(8)

        self.img_width = QSpinBox()
        self.img_width.setRange(1, 16384)
        self.img_width.setSuffix(" px")
        self.img_width.valueChanged.connect(self._on_image_geometry)
        form.addRow("Width", self.img_width)

        self.img_height = QSpinBox()
        self.img_height.setRange(1, 16384)
        self.img_height.setSuffix(" px")
        self.img_height.valueChanged.connect(self._on_image_geometry)
        form.addRow("Height", self.img_height)

        self.img_x = QSpinBox()
        self.img_x.setRange(-16384, 16384)
        self.img_x.setSuffix(" px")
        self.img_x.valueChanged.connect(self._on_image_geometry)
        form.addRow("X", self.img_x)

        self.img_y = QSpinBox()
        self.img_y.setRange(-16384, 16384)
        self.img_y.setSuffix(" px")
        self.img_y.valueChanged.connect(self._on_image_geometry)
        form.addRow("Y", self.img_y)

        self.img_opacity = _slider(1, 100, 100)
        self.img_opacity_label = QLabel("100%")
        self.img_opacity_label.setMinimumWidth(38)
        orow = QHBoxLayout()
        orow.addWidget(self.img_opacity, 1)
        orow.addWidget(self.img_opacity_label)
        oholder = QWidget()
        oholder.setLayout(orow)
        self.img_opacity.valueChanged.connect(self._on_image_opacity)
        form.addRow("Opacity", oholder)
        layout.addLayout(form)

        self.img_aspect = QCheckBox("Lock aspect ratio")
        self.img_aspect.setChecked(True)
        self.img_aspect.toggled.connect(self.imageKeepAspectChanged)
        layout.addWidget(self.img_aspect)

        sizes = QHBoxLayout()
        self.img_fit_btn = QPushButton("Fill texture")
        self.img_fit_btn.clicked.connect(self.fitImageRequested)
        self.img_reset_btn = QPushButton("Original size")
        self.img_reset_btn.clicked.connect(self.resetImageSizeRequested)
        sizes.addWidget(self.img_fit_btn)
        sizes.addWidget(self.img_reset_btn)
        layout.addLayout(sizes)

        buttons = QHBoxLayout()
        self.apply_image_btn = QPushButton("Apply image")
        self.apply_image_btn.setProperty("accent", True)
        self.apply_image_btn.clicked.connect(self.applyImageRequested)
        self.discard_image_btn = QPushButton("Discard")
        self.discard_image_btn.setProperty("danger", True)
        self.discard_image_btn.clicked.connect(self.discardImageRequested)
        buttons.addWidget(self.apply_image_btn, 1)
        buttons.addWidget(self.discard_image_btn)
        layout.addLayout(buttons)

        self.set_image_controls_enabled(False)
        return box

    def _image_widgets(self):
        return (self.img_width, self.img_height, self.img_x, self.img_y,
                self.img_opacity, self.img_aspect, self.img_fit_btn,
                self.img_reset_btn, self.apply_image_btn, self.discard_image_btn)

    def set_image_controls_enabled(self, enabled):
        for w in self._image_widgets():
            w.setEnabled(enabled)

    def load_image_item(self, item):
        """Push a canvas ImageItem into the controls without re-emitting."""
        enabled = item is not None
        self.set_image_controls_enabled(enabled)
        if item is None:
            return
        for w in (self.img_width, self.img_height, self.img_x, self.img_y,
                  self.img_opacity):
            w.blockSignals(True)
        self.img_width.setValue(int(round(item.width)))
        self.img_height.setValue(int(round(item.height)))
        self.img_x.setValue(int(round(item.pos.x())))
        self.img_y.setValue(int(round(item.pos.y())))
        self.img_opacity.setValue(int(round(item.opacity * 100)))
        self.img_opacity_label.setText("%d%%" % self.img_opacity.value())
        for w in (self.img_width, self.img_height, self.img_x, self.img_y,
                  self.img_opacity):
            w.blockSignals(False)

    def _on_image_opacity(self, value):
        self.img_opacity_label.setText("%d%%" % value)
        self.imageGeometryEdited.emit()

    def _on_image_geometry(self, _value=None):
        self.imageGeometryEdited.emit()

    def image_geometry(self):
        return {
            "width": self.img_width.value(),
            "height": self.img_height.value(),
            "x": self.img_x.value(),
            "y": self.img_y.value(),
            "opacity": self.img_opacity.value() / 100.0,
            "keep_aspect": self.img_aspect.isChecked(),
        }

    def sync_image_size(self, width, height):
        """Write back a size the aspect lock adjusted, without re-emitting."""
        for w in (self.img_width, self.img_height):
            w.blockSignals(True)
        self.img_width.setValue(int(round(width)))
        self.img_height.setValue(int(round(height)))
        for w in (self.img_width, self.img_height):
            w.blockSignals(False)

    # --------------------------------------------------------------- image

    def _build_image_group(self):
        box = QGroupBox("Texture")
        grid = QGridLayout(box)
        grid.setSpacing(6)

        def add(row, col, text, slot, span=1):
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            grid.addWidget(btn, row, col, 1, span)
            return btn

        add(0, 0, "Rotate CW", lambda: self.rotateRequested.emit(90))
        add(0, 1, "Rotate CCW", lambda: self.rotateRequested.emit(-90))
        add(1, 0, "Flip H", lambda: self.flipRequested.emit(True))
        add(1, 1, "Flip V", lambda: self.flipRequested.emit(False))
        add(2, 0, "Resize...", self.resizeRequested.emit)
        add(2, 1, "Crop...", self.cropRequested.emit)
        add(3, 0, "Replace with image...", self.importTextureRequested.emit, 2)
        self.clear_btn = add(4, 0, "Clear", self.clearRequested.emit)
        self.revert_btn = add(4, 1, "Revert", self.revertRequested.emit)
        self.revert_btn.setProperty("danger", True)

        note = QLabel("Rotate / resize / crop keep the original texture size, "
                      "which is required to write the .ytd back in place.")
        note.setWordWrap(True)
        note.setProperty("hint", True)
        grid.addWidget(note, 5, 0, 1, 2)
        return box

    # -------------------------------------------------------------- export

    def _build_export_group(self):
        box = QGroupBox("Export single texture")
        row = QHBoxLayout(box)
        png = QPushButton("PNG...")
        png.clicked.connect(self.exportPngRequested)
        dds = QPushButton("DDS...")
        dds.clicked.connect(self.exportDdsRequested)
        row.addWidget(png)
        row.addWidget(dds)
        return box

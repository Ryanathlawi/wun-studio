"""
لوحة الخصائص: إعدادات الأداة النشطة وعمليات التكستشر والتصدير.

كل مجموعة قسم مستقل قابل للطي، فالمستخدم الذي يرسم فقط يطوي أقسام النص
والصورة ويبقي أمامه ما يستعمله.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFontComboBox,
                               QGridLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import icons, theme
from .widgets import (ColorSwatch, Divider, Field, Section, SliderField,
                      SpinBox)


def _button(text, icon_name=None, kind=None, tip=""):
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMinimumHeight(34)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, 16,
                               "#FFFFFF" if kind == "primary" else theme.TXT_DIM))
    if kind:
        btn.setProperty("kind", kind)
    if tip:
        btn.setToolTip(tip)
    return btn


class PropertiesPanel(QWidget):
    """اللوحة الجانبية لإعدادات التحرير."""

    # الفرشاة والأشكال
    brushSizeChanged = Signal(int)
    brushOpacityChanged = Signal(float)
    brushColorChanged = Signal(QColor)
    antialiasChanged = Signal(bool)
    shapeFilledChanged = Signal(bool)

    # النص
    textEdited = Signal()
    applyTextRequested = Signal()
    cancelTextRequested = Signal()

    # الصورة العائمة
    importImageRequested = Signal()
    imageGeometryEdited = Signal()
    applyImageRequested = Signal()
    discardImageRequested = Signal()
    fitImageRequested = Signal()
    resetImageSizeRequested = Signal()
    imageKeepAspectChanged = Signal(bool)

    # عمليات التكستشر
    clearRequested = Signal()
    rotateRequested = Signal(int)
    flipRequested = Signal(bool)
    resizeRequested = Signal()
    cropRequested = Signal()
    revertRequested = Signal()
    importTextureRequested = Signal()

    # الأدوات الجديدة
    fillToleranceChanged = Signal(int)
    gradientColorChanged = Signal(QColor)
    selectAllRequested = Signal()
    clearSelectionRequested = Signal()
    cropToSelectionRequested = Signal()

    # التعديلات اللونية
    adjustPreviewRequested = Signal()
    adjustApplyRequested = Signal()
    adjustResetRequested = Signal()

    # العرض
    gridToggled = Signal(bool)
    gridSizeChanged = Signal(int)
    compareToggled = Signal(bool)
    compareSplitChanged = Signal(int)

    # المعالجة الدفعية
    batchStampRequested = Signal()
    batchExportRequested = Signal()
    batchImportRequested = Signal()

    # التصدير
    exportPngRequested = Signal()
    exportDdsRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 6, 10)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(7)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("grid", 15, theme.TXT_DIM))
        title = QLabel("الخصائص")
        title.setObjectName("PanelTitle")
        head.addWidget(glyph)
        head.addWidget(title)
        head.addStretch(1)
        outer.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # شبكة أمان: أي محتوى يتجاوز العرض يصير قابلًا للتمرير بدل أن
        # يُقصّ بصمت كما حدث مع قائمة الخطوط على جهاز فيه خطوط كثيرة
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        outer.addWidget(scroll, 1)

        host = QWidget()
        self._column = QVBoxLayout(host)
        self._column.setContentsMargins(0, 0, 6, 0)
        self._column.setSpacing(4)
        scroll.setWidget(host)

        self._column.addWidget(self._build_brush())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_adjust())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_selection_view())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_batch())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_text())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_placed_image())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_texture_ops())
        self._column.addWidget(Divider())
        self._column.addWidget(self._build_export())
        self._column.addStretch(1)

        self.set_text_controls_enabled(False)
        self.set_image_controls_enabled(False)

    # ------------------------------------------------------ الفرشاة والأشكال

    def _build_brush(self):
        section = Section("الأدوات", "brush", expanded=True)

        self.size_slider = SliderField("الحجم", 1, 256, 16, " بكسل")
        self.size_slider.valueChanged.connect(self.brushSizeChanged)
        section.add(self.size_slider)

        self.opacity_slider = SliderField("الشفافية", 1, 100, 100, "٪")
        self.opacity_slider.valueChanged.connect(
            lambda v: self.brushOpacityChanged.emit(v / 100.0))
        section.add(self.opacity_slider)

        self.color_swatch = ColorSwatch(QColor(theme.ACCENT))
        self.color_swatch.colorChanged.connect(self.brushColorChanged)
        section.add(Field("اللون", self.color_swatch))

        self.antialias = QCheckBox("حواف ناعمة")
        self.antialias.setChecked(True)
        self.antialias.toggled.connect(self.antialiasChanged)
        section.add(self.antialias)

        self.filled = QCheckBox("أشكال معبّأة")
        self.filled.toggled.connect(self.shapeFilledChanged)
        section.add(self.filled)

        section.add(Divider())

        self.tolerance = SliderField("تسامح الدلو", 0, 128, 32)
        self.tolerance.valueChanged.connect(self.fillToleranceChanged)
        section.add(self.tolerance)

        self.gradient_swatch = ColorSwatch(QColor("#000000"))
        self.gradient_swatch.colorChanged.connect(self.gradientColorChanged)
        section.add(Field("نهاية التدرّج", self.gradient_swatch))

        hint = QLabel("الدلو يملأ المنطقة المتشابهة حول نقطة النقر، والتدرّج "
                      "يُرسم من اللون الأساسي إلى لون النهاية باتجاه سحبك.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        section.add(hint)
        return section

    # ---------------------------------------------------- التعديلات اللونية

    def _build_adjust(self):
        section = Section("الألوان", "adjust", expanded=False)
        self.adjust_section = section

        self.adj_brightness = SliderField("السطوع", -100, 100, 0)
        self.adj_contrast = SliderField("التباين", -100, 100, 0)
        self.adj_saturation = SliderField("التشبّع", -100, 100, 0)
        self.adj_hue = SliderField("الصبغة", -180, 180, 0, "°")
        for widget in (self.adj_brightness, self.adj_contrast,
                       self.adj_saturation, self.adj_hue):
            widget.valueChanged.connect(
                lambda _v: self.adjustPreviewRequested.emit())
            section.add(widget)

        row = QHBoxLayout()
        self.adj_grayscale = QCheckBox("تدرّج رمادي")
        self.adj_invert = QCheckBox("عكس الألوان")
        for widget in (self.adj_grayscale, self.adj_invert):
            widget.toggled.connect(
                lambda _v: self.adjustPreviewRequested.emit())
            row.addWidget(widget)
        row.addStretch(1)
        section.add_layout(row)

        actions = QHBoxLayout()
        self.adj_apply = _button("تطبيق", "check", "primary")
        self.adj_apply.clicked.connect(self.adjustApplyRequested)
        self.adj_reset = _button("تصفير", "revert")
        self.adj_reset.clicked.connect(self.adjustResetRequested)
        actions.addWidget(self.adj_apply, 2)
        actions.addWidget(self.adj_reset, 1)
        section.add_layout(actions)

        note = QLabel("المعاينة فورية على نسخة مصغّرة، و«تطبيق» يعيد الحساب "
                      "على الدقة الكاملة.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        section.add(note)
        return section

    def adjust_params(self):
        return {
            "brightness": self.adj_brightness.value(),
            "contrast": self.adj_contrast.value(),
            "saturation": self.adj_saturation.value(),
            "hue": self.adj_hue.value(),
            "grayscale": self.adj_grayscale.isChecked(),
            "invert": self.adj_invert.isChecked(),
        }

    def reset_adjust(self):
        for widget in (self.adj_brightness, self.adj_contrast,
                       self.adj_saturation, self.adj_hue):
            widget.slider.blockSignals(True)
            widget.setValue(0)
            widget.slider.blockSignals(False)
        for widget in (self.adj_grayscale, self.adj_invert):
            widget.blockSignals(True)
            widget.setChecked(False)
            widget.blockSignals(False)

    # ------------------------------------------------------- التحديد والعرض

    def _build_selection_view(self):
        section = Section("العرض", "select", expanded=False)

        row = QHBoxLayout()
        select_all = _button("تحديد الكل", "select")
        select_all.clicked.connect(self.selectAllRequested)
        clear = _button("إلغاء التحديد", "close")
        clear.clicked.connect(self.clearSelectionRequested)
        row.addWidget(select_all)
        row.addWidget(clear)
        section.add_layout(row)

        crop_selection = _button("قصّ على التحديد", "crop")
        crop_selection.clicked.connect(self.cropToSelectionRequested)
        section.add(crop_selection)

        self.selection_label = QLabel("لا يوجد تحديد")
        self.selection_label.setObjectName("Hint")
        section.add(self.selection_label)

        section.add(Divider())

        self.grid_check = QCheckBox("إظهار شبكة المحاذاة")
        self.grid_check.toggled.connect(self.gridToggled)
        section.add(self.grid_check)

        self.grid_size = SliderField("مقاس الشبكة", 8, 512, 64, " بكسل")
        self.grid_size.valueChanged.connect(self.gridSizeChanged)
        section.add(self.grid_size)

        self.compare_check = QCheckBox("مقارنة قبل / بعد")
        self.compare_check.toggled.connect(self.compareToggled)
        section.add(self.compare_check)

        self.compare_split = SliderField("موضع المقسّم", 0, 100, 50, "٪")
        self.compare_split.valueChanged.connect(self.compareSplitChanged)
        section.add(self.compare_split)
        return section

    def set_selection_text(self, rect):
        if rect is None:
            self.selection_label.setText("لا يوجد تحديد")
        else:
            self.selection_label.setText(
                "التحديد: %d×%d عند س %d، ص %d"
                % (rect.width(), rect.height(), rect.left(), rect.top()))

    # ----------------------------------------------------- المعالجة الدفعية

    def _build_batch(self):
        section = Section("الدفعات", "batch", expanded=False)

        stamp = _button("ختم صورة على كل الملفات…", "image", "primary")
        stamp.clicked.connect(self.batchStampRequested)
        section.add(stamp)

        export_all = _button("تصدير كل التكستشرات PNG…", "export")
        export_all.clicked.connect(self.batchExportRequested)
        section.add(export_all)

        import_all = _button("استيراد مجلد PNG بمطابقة الأسماء…", "import")
        import_all.clicked.connect(self.batchImportRequested)
        section.add(import_all)

        note = QLabel("الختم يلصق الصورة على كل الملفات المفتوحة بنفس الموضع "
                      "النسبي، والاستيراد يستبدل كل تكستشر باسمه المطابق.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        section.add(note)
        return section

    # ---------------------------------------------------------------- النص

    def _build_text(self):
        section = Section("النص", "text", expanded=False)
        self.text_section = section

        hint = QLabel("اختر أداة النص ثم انقر على الكانفس. اسحب النص لتحريكه، "
                      "وثبّته بـ Ctrl+Enter.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        section.add(hint)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("محتوى النص")
        self.text_edit.setFixedHeight(66)
        self.text_edit.textChanged.connect(self.textEdited)
        section.add(self.text_edit)

        self.font_combo = QFontComboBox()
        self.font_combo.setFixedHeight(32)
        self.font_combo.setCurrentFont(theme.font(10))
        # القائمة تحسب عرضها الأدنى من أطول اسم خط مثبّت على الجهاز، وعلى جهاز
        # فيه مئات الخطوط يدفع ذلك اللوحة كلها أوسع من مساحتها فيُقصّ المحتوى.
        # نثبّت العرض على عدد أحرف معقول، ونترك القائمة المنسدلة وحدها عريضة
        # حتى تبقى الأسماء الطويلة مقروءة عند فتحها.
        self.font_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.font_combo.setMinimumContentsLength(10)
        self.font_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.font_combo.view().setMinimumWidth(280)
        self.font_combo.currentFontChanged.connect(lambda _f: self.textEdited.emit())
        section.add(Field("الخط", self.font_combo))

        self.font_size = SpinBox(4, 900, 48, " بكسل")
        self.font_size.valueChanged.connect(lambda _v: self.textEdited.emit())
        section.add(Field("المقاس", self.font_size))

        self.text_color = ColorSwatch(QColor("#FFFFFF"))
        self.text_color.colorChanged.connect(lambda _c: self.textEdited.emit())
        section.add(Field("اللون", self.text_color))

        style_row = QHBoxLayout()
        self.bold = QCheckBox("عريض")
        self.italic = QCheckBox("مائل")
        self.bold.toggled.connect(self.textEdited)
        self.italic.toggled.connect(self.textEdited)
        style_row.addWidget(self.bold)
        style_row.addWidget(self.italic)
        style_row.addStretch(1)
        section.add_layout(style_row)

        actions = QHBoxLayout()
        self.apply_text_btn = _button("تثبيت النص", "check", "primary")
        self.apply_text_btn.clicked.connect(self.applyTextRequested)
        self.cancel_text_btn = _button("إلغاء", "close")
        self.cancel_text_btn.clicked.connect(self.cancelTextRequested)
        actions.addWidget(self.apply_text_btn, 2)
        actions.addWidget(self.cancel_text_btn, 1)
        section.add_layout(actions)
        return section

    def set_text_controls_enabled(self, enabled):
        for w in (self.text_edit, self.font_combo, self.font_size,
                  self.text_color, self.bold, self.italic,
                  self.apply_text_btn, self.cancel_text_btn):
            w.setEnabled(enabled)

    def load_text_item(self, item):
        """مزامنة الحقول مع النص العائم الحالي."""
        self.set_text_controls_enabled(item is not None)
        if item is None:
            return
        self.text_section.set_expanded(True)
        blockers = [self.text_edit, self.font_combo, self.font_size,
                    self.bold, self.italic]
        for w in blockers:
            w.blockSignals(True)
        self.text_edit.setPlainText(item.text)
        self.font_combo.setCurrentFont(item.font())
        self.font_size.setValue(int(item.size))
        self.bold.setChecked(item.bold)
        self.italic.setChecked(item.italic)
        for w in blockers:
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
            "bold": self.bold.isChecked(),
            "italic": self.italic.isChecked(),
        }

    # -------------------------------------------------------- الصورة العائمة

    def _build_placed_image(self):
        section = Section("الصور", "image", expanded=False)
        self.image_section = section

        self.import_image_btn = _button("رفع صورة…", "import", "primary")
        self.import_image_btn.clicked.connect(self.importImageRequested)
        section.add(self.import_image_btn)

        hint = QLabel("اسحب الصورة لتحريكها، أو اسحب زاوية لتغيير حجمها. "
                      "ويمكنك ضبط المقاس رقميًا بالأسفل.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        section.add(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        self.img_width = SpinBox(1, 16384, 1)
        self.img_height = SpinBox(1, 16384, 1)
        self.img_x = SpinBox(-16384, 16384, 0)
        self.img_y = SpinBox(-16384, 16384, 0)
        for spin in (self.img_width, self.img_height, self.img_x, self.img_y):
            spin.valueChanged.connect(self._on_geometry)
        for row, (label, widget) in enumerate([
                ("العرض", self.img_width), ("الارتفاع", self.img_height),
                ("س", self.img_x), ("ص", self.img_y)]):
            tag = QLabel(label)
            tag.setObjectName("PanelTitle")
            grid.addWidget(tag, row // 2, (row % 2) * 2)
            grid.addWidget(widget, row // 2, (row % 2) * 2 + 1)
        section.add_layout(grid)

        self.img_opacity = SliderField("الشفافية", 1, 100, 100, "٪")
        self.img_opacity.valueChanged.connect(self._on_geometry)
        section.add(self.img_opacity)

        self.keep_aspect = QCheckBox("حافظ على النسبة")
        self.keep_aspect.setChecked(True)
        self.keep_aspect.toggled.connect(self.imageKeepAspectChanged)
        section.add(self.keep_aspect)

        row = QHBoxLayout()
        self.img_fit_btn = _button("ملء التكستشر", "fit")
        self.img_fit_btn.clicked.connect(self.fitImageRequested)
        self.img_reset_btn = _button("الحجم الأصلي", "actual")
        self.img_reset_btn.clicked.connect(self.resetImageSizeRequested)
        row.addWidget(self.img_fit_btn)
        row.addWidget(self.img_reset_btn)
        section.add_layout(row)

        actions = QHBoxLayout()
        self.apply_image_btn = _button("تثبيت الصورة", "check", "primary")
        self.apply_image_btn.clicked.connect(self.applyImageRequested)
        self.discard_image_btn = _button("إلغاء", "close")
        self.discard_image_btn.clicked.connect(self.discardImageRequested)
        actions.addWidget(self.apply_image_btn, 2)
        actions.addWidget(self.discard_image_btn, 1)
        section.add_layout(actions)
        return section

    def _image_widgets(self):
        return (self.img_width, self.img_height, self.img_x, self.img_y,
                self.img_opacity, self.keep_aspect, self.img_fit_btn,
                self.img_reset_btn, self.apply_image_btn, self.discard_image_btn)

    def set_image_controls_enabled(self, enabled):
        for w in self._image_widgets():
            w.setEnabled(enabled)

    def load_image_item(self, item):
        """مزامنة الحقول مع الصورة العائمة الحالية."""
        self.set_image_controls_enabled(item is not None)
        if item is None:
            return
        self.image_section.set_expanded(True)
        widgets = (self.img_width, self.img_height, self.img_x, self.img_y,
                   self.img_opacity)
        for w in widgets:
            w.blockSignals(True)
        self.img_width.setValue(int(round(item.width)))
        self.img_height.setValue(int(round(item.height)))
        self.img_x.setValue(int(round(item.pos.x())))
        self.img_y.setValue(int(round(item.pos.y())))
        self.img_opacity.setValue(int(round(item.opacity * 100)))
        for w in widgets:
            w.blockSignals(False)

    def _on_geometry(self, _value=None):
        self.imageGeometryEdited.emit()

    def image_geometry(self):
        return {
            "width": self.img_width.value(),
            "height": self.img_height.value(),
            "x": self.img_x.value(),
            "y": self.img_y.value(),
            "opacity": self.img_opacity.value() / 100.0,
            "keep_aspect": self.keep_aspect.isChecked(),
        }

    def sync_image_size(self, width, height):
        """كتابة المقاس المحسوب في الحقول دون إطلاق إشارة جديدة."""
        for widget, value in ((self.img_width, width), (self.img_height, height)):
            widget.blockSignals(True)
            widget.setValue(int(round(value)))
            widget.blockSignals(False)

    # ------------------------------------------------------- عمليات التكستشر

    def _build_texture_ops(self):
        section = Section("التكستشر", "resize", expanded=True)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)

        def cell(row, col, text, icon_name, slot, span=1, kind=None):
            btn = _button(text, icon_name, kind)
            btn.clicked.connect(slot)
            grid.addWidget(btn, row, col, 1, span)
            return btn

        cell(0, 0, "تدوير يمينًا", "rotate_cw",
             lambda: self.rotateRequested.emit(90))
        cell(0, 1, "تدوير يسارًا", "rotate_ccw",
             lambda: self.rotateRequested.emit(-90))
        cell(1, 0, "قلب أفقي", "flip_h", lambda: self.flipRequested.emit(True))
        cell(1, 1, "قلب رأسي", "flip_v", lambda: self.flipRequested.emit(False))
        cell(2, 0, "تحجيم…", "resize", self.resizeRequested.emit)
        cell(2, 1, "قص…", "crop", self.cropRequested.emit)
        cell(3, 0, "استبدال بصورة…", "image",
             self.importTextureRequested.emit, span=2)
        self.clear_btn = cell(4, 0, "مسح", "trash", self.clearRequested.emit)
        self.revert_btn = cell(4, 1, "استرجاع", "revert",
                               self.revertRequested.emit, kind="danger")
        section.add_layout(grid)

        note = QLabel("التدوير والتحجيم والقص تحافظ على أبعاد التكستشر الأصلية، "
                      "وهو شرط لإعادة كتابته داخل ملف الـ ytd.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        section.add(note)
        return section

    # ------------------------------------------------------------- التصدير

    def _build_export(self):
        section = Section("التصدير", "export", expanded=False)
        row = QHBoxLayout()
        png = _button("PNG…", "export")
        png.clicked.connect(self.exportPngRequested)
        dds = _button("DDS…", "export")
        dds.clicked.connect(self.exportDdsRequested)
        row.addWidget(png)
        row.addWidget(dds)
        section.add_layout(row)

        note = QLabel("تصدير DDS يكتب بيانات السطح كما هي داخل الملف، "
                      "لا تعديلاتك غير المحفوظة.")
        note.setObjectName("Hint")
        note.setWordWrap(True)
        section.add(note)
        return section

"""
النافذة الرئيسية: تجميع اللوحات والكانفس والريل وربطها بالنواة.

هذا الملف لا يعرف شيئًا عن صيغة YTD؛ كل ما يفعله هو تحويل نقرات المستخدم
إلى استدعاءات على core ثم عرض النتيجة.
"""

from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QLabel, QMessageBox,
                               QProgressDialog, QVBoxLayout, QWidget)

from ..core import export_handler as exporter
from ..core.export_handler import ExportError
from ..core.ytd_handler import YtdError, YtdFile
from . import canvas as cv
from . import icons, theme
from .canvas import Canvas
from .properties import PropertiesPanel, _button
from .shell import FramelessWindow
from .texture_list import TexturePanel
from .tool_rail import ToolRail
from .widgets import Divider, EmptyState, SpinBox

IMAGE_FILTER = ("الصور (*.png *.jpg *.jpeg *.bmp *.tga *.dds *.webp);;"
                "كل الملفات (*)")
YTD_FILTER = "قاموس تكستشرات GTA V (*.ytd);;كل الملفات (*)"


# --------------------------------------------------------------------------
# حوارات مساعدة
# --------------------------------------------------------------------------

def _box(parent, icon, title, text, detail=None):
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if detail:
        box.setDetailedText(detail)
    return box


def show_error(parent, title, text):
    box = _box(parent, QMessageBox.Critical, title, text)
    box.addButton("حسنًا", QMessageBox.AcceptRole)
    box.exec()


def show_info(parent, title, text, detail=None):
    box = _box(parent, QMessageBox.Information, title, text, detail)
    box.addButton("حسنًا", QMessageBox.AcceptRole)
    box.exec()


def ask(parent, title, text, confirm="نعم", cancel="إلغاء", warning=False):
    box = _box(parent, QMessageBox.Warning if warning else QMessageBox.Question,
               title, text)
    yes = box.addButton(confirm, QMessageBox.YesRole)
    box.addButton(cancel, QMessageBox.RejectRole)
    box.exec()
    return box.clickedButton() is yes


class SizeDialog(QDialog):
    """حوار رقمي صغير يُستخدم للتحجيم والقص."""

    def __init__(self, title, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(9)
        self.spins = {}
        for key, label, value, maximum in fields:
            spin = SpinBox(0 if key in ("x", "y") else 1, maximum, value)
            form.addRow(label, spin)
            self.spins[key] = spin
        layout.addLayout(form)

        self.keep_canvas = QCheckBox("احتفظ بأبعاد التكستشر الأصلية")
        self.keep_canvas.setChecked(True)
        self.keep_canvas.setToolTip(
            "مطلوب لإعادة الحفظ داخل ملف الـ ytd. إلغاء هذا الخيار يغيّر أبعاد "
            "الكانفس فلا يعود التكستشر قابلًا للكتابة في مكانه.")
        layout.addWidget(self.keep_canvas)

        buttons = QDialogButtonBox()
        ok = buttons.addButton("تطبيق", QDialogButtonBox.AcceptRole)
        ok.setProperty("kind", "primary")
        buttons.addButton("إلغاء", QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {k: s.value() for k, s in self.spins.items()}


# --------------------------------------------------------------------------
# النافذة
# --------------------------------------------------------------------------

class MainWindow(FramelessWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTD Texture Editor")
        self.resize(1560, 960)

        self.ytd: YtdFile | None = None
        self.current = None                 # TextureEntry
        self.edits = {}                     # فهرس التكستشر -> مصفوفة RGBA
        self.originals = {}                 # فهرس التكستشر -> النسخة الأصلية
        self._dirty = False

        self._build_ui()
        self._connect()
        self._install_shortcuts()
        self._update_actions()

    # ------------------------------------------------------------- البناء

    def _build_ui(self):
        root = QVBoxLayout(self.body)
        root.setContentsMargins(10, 4, 10, 10)
        root.setSpacing(9)

        root.addWidget(self._build_command_bar())

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(9)

        self.textures = TexturePanel()
        self.textures.setFixedWidth(296)
        row.addWidget(self.textures)

        self.rail = ToolRail()
        row.addWidget(self.rail)

        row.addWidget(self._build_canvas_host(), 1)

        self.properties = PropertiesPanel()
        self.properties.setFixedWidth(330)
        row.addWidget(self.properties)

        root.addLayout(row, 1)
        root.addWidget(self._build_status_bar())

    def _build_command_bar(self):
        bar = QWidget()
        bar.setFixedHeight(46)
        row = QHBoxLayout(bar)
        row.setContentsMargins(2, 0, 2, 0)
        row.setSpacing(7)

        self.btn_open = _button("فتح ملف YTD", "open", "primary",
                                "فتح قاموس تكستشرات  (Ctrl+O)")
        self.btn_save = _button("حفظ باسم", "save", None,
                                "كتابة ملف ytd جديد بتعديلاتك  (Ctrl+Shift+S)")
        self.btn_save.setEnabled(False)
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_save)

        row.addWidget(Divider(vertical=True))

        self.btn_undo = _button("تراجع", "undo", None, "تراجع  (Ctrl+Z)")
        self.btn_redo = _button("إعادة", "redo", None, "إعادة  (Ctrl+Y)")
        self.btn_undo.setEnabled(False)
        self.btn_redo.setEnabled(False)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)

        row.addStretch(1)

        self.lbl_texture = QLabel("لم يُختر تكستشر")
        self.lbl_texture.setFont(theme.font(10, medium=True))
        self.badge_size = QLabel("—")
        self.badge_size.setObjectName("Hint")
        self.badge_format = QLabel("—")
        self.badge_format.setObjectName("Hint")
        for widget in (self.lbl_texture, self.badge_size, self.badge_format):
            row.addWidget(widget)
            if widget is not self.badge_format:
                dot = QLabel("·")
                dot.setStyleSheet("color: %s;" % theme.BORDER_HI)
                row.addWidget(dot)
        return bar

    def _build_canvas_host(self):
        host = QWidget()
        host.setObjectName("CanvasHost")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(1, 1, 1, 1)

        self.canvas = Canvas()
        self.empty = EmptyState(
            "layers", "لم يُفتح أي ملف بعد",
            "افتح ملف ytd من الزر أعلاه، ثم اختر تكستشرًا من القائمة.")
        layout.addWidget(self.empty)
        layout.addWidget(self.canvas)
        self.canvas.hide()
        return host

    def _build_status_bar(self):
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(24)
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(14)

        self.st_state = QLabel("جاهز")
        self.st_state.setObjectName("Hint")
        self.st_cursor = QLabel("—")
        self.st_cursor.setObjectName("Hint")
        self.st_zoom = QLabel("100%")
        self.st_zoom.setObjectName("Hint")

        row.addWidget(self.st_state)
        row.addStretch(1)
        row.addWidget(self.st_cursor)
        row.addWidget(Divider(vertical=True))
        row.addWidget(self.st_zoom)
        return bar

    # -------------------------------------------------------------- الربط

    def _connect(self):
        self.btn_open.clicked.connect(self.open_ytd)
        self.btn_save.clicked.connect(self.save_as_ytd)
        self.btn_undo.clicked.connect(lambda: self.canvas.undo())
        self.btn_redo.clicked.connect(lambda: self.canvas.redo())

        self.rail.toolChanged.connect(self._set_tool)
        self.rail.zoomInRequested.connect(lambda: self.canvas.zoom_by(1.25))
        self.rail.zoomOutRequested.connect(lambda: self.canvas.zoom_by(1 / 1.25))
        self.rail.fitRequested.connect(self.canvas.fit_to_view)
        self.rail.actualSizeRequested.connect(self.canvas.reset_zoom)

        self.textures.textureSelected.connect(self.select_texture)

        c = self.canvas
        c.zoomChanged.connect(
            lambda z: self.st_zoom.setText("%d%%" % round(z * 100)))
        c.cursorMoved.connect(
            lambda x, y: self.st_cursor.setText("س %d، ص %d" % (x, y)))
        c.historyChanged.connect(self._on_history)
        c.imageChanged.connect(self._on_image_changed)
        c.textItemChanged.connect(self._on_text_item)
        c.imageItemChanged.connect(self.properties.load_image_item)
        c.imageItemMoved.connect(self.properties.load_image_item)
        c.colorPicked.connect(self.properties.color_swatch.setColor)

        p = self.properties
        p.brushSizeChanged.connect(lambda v: setattr(c, "brush_size", v))
        p.brushOpacityChanged.connect(lambda v: setattr(c, "brush_opacity", v))
        p.brushColorChanged.connect(lambda col: setattr(c, "brush_color", col))
        p.antialiasChanged.connect(lambda v: setattr(c, "brush_hardness", v))
        p.shapeFilledChanged.connect(lambda v: setattr(c, "shape_filled", v))

        p.textEdited.connect(self._sync_text_item)
        p.applyTextRequested.connect(self._apply_text)
        p.cancelTextRequested.connect(c.cancel_text)

        p.importImageRequested.connect(self._place_image)
        p.imageGeometryEdited.connect(self._sync_image_item)
        p.applyImageRequested.connect(self._apply_image_item)
        p.discardImageRequested.connect(c.cancel_image_item)
        p.fitImageRequested.connect(c.fit_image_item)
        p.resetImageSizeRequested.connect(c.reset_image_item_size)
        p.imageKeepAspectChanged.connect(
            lambda v: setattr(c, "image_keep_aspect", v))

        p.clearRequested.connect(self._clear_canvas)
        p.rotateRequested.connect(self._rotate)
        p.flipRequested.connect(c.flip)
        p.resizeRequested.connect(self._resize_dialog)
        p.cropRequested.connect(self._crop_dialog)
        p.importTextureRequested.connect(self._replace_texture)
        p.revertRequested.connect(self._revert_texture)
        p.exportPngRequested.connect(self._export_png)
        p.exportDdsRequested.connect(self._export_dds)

    def _install_shortcuts(self):
        binds = [
            ("Ctrl+O", self.open_ytd),
            ("Ctrl+Shift+S", self.save_as_ytd),
            ("Ctrl+Z", lambda: self.canvas.undo()),
            ("Ctrl+Y", lambda: self.canvas.redo()),
            ("Ctrl+Shift+Z", lambda: self.canvas.redo()),
            ("Ctrl+=", lambda: self.canvas.zoom_by(1.25)),
            ("Ctrl++", lambda: self.canvas.zoom_by(1.25)),
            ("Ctrl+-", lambda: self.canvas.zoom_by(1 / 1.25)),
            ("Ctrl+0", self.canvas.fit_to_view),
            ("Ctrl+1", self.canvas.reset_zoom),
            ("Ctrl+Return", self._apply_floating),
            ("Ctrl+F", self.textures.search.setFocus),
        ]
        for key, slot in binds:
            QShortcut(QKeySequence(key), self, activated=slot)

        from .tool_rail import TOOLS
        for key, _icon, _label, letter in TOOLS:
            QShortcut(QKeySequence(letter), self,
                      activated=lambda k=key: self._pick_tool(k))

    def _pick_tool(self, key):
        self.rail.set_tool(key)
        self._set_tool(key)

    # ------------------------------------------------------------ المساعدات

    def _update_actions(self):
        has_ytd = self.ytd is not None
        has_img = self.canvas.has_image()
        self.btn_save.setEnabled(has_ytd)
        self.properties.setEnabled(has_img)
        self.rail.setEnabled(has_img)
        self.canvas.setVisible(has_img)
        self.empty.setVisible(not has_img)

    def _on_history(self, can_undo, can_redo):
        self.btn_undo.setEnabled(can_undo)
        self.btn_redo.setEnabled(can_redo)

    def _on_image_changed(self):
        if self.current is None:
            return
        if not self._dirty:
            self._dirty = True
            self.textures.mark_edited(self.current.index, True)
        self.title_bar.set_dirty(True)
        self._refresh_status()

    def _refresh_status(self):
        if self.current is None:
            self.lbl_texture.setText("لم يُختر تكستشر")
            self.badge_size.setText("—")
            self.badge_format.setText("—")
            return
        self.lbl_texture.setText(self.current.name + (" ●" if self._dirty else ""))
        w, h = self.canvas.image_size()
        native = "%d×%d" % (self.current.width, self.current.height)
        self.badge_size.setText(
            native if (w, h) == (self.current.width, self.current.height)
            else "%d×%d (الأصل %s)" % (w, h, native))
        self.badge_format.setText("%s · %d مستوى" % (self.current.format_name,
                                                     self.current.levels))

    def _set_tool(self, key):
        self.canvas.tool = key
        if key != cv.TOOL_TEXT and self.canvas.text_item is None:
            self.properties.set_text_controls_enabled(False)

    def _status(self, text):
        self.st_state.setText(text)

    # ---------------------------------------------------------------- الفتح

    def open_ytd(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "فتح قاموس تكستشرات", "", YTD_FILTER)
        if path:
            self.load_ytd(path)

    def load_ytd(self, path):
        if self.ytd is not None and (self._dirty or self.edits):
            if not ask(self, "تعديلات غير محفوظة",
                       "لديك تعديلات لم تُحفظ. هل تفتح ملفًا آخر رغم ذلك؟",
                       "افتح على أي حال"):
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ytd = YtdFile.open(path)
        except YtdError as exc:
            QApplication.restoreOverrideCursor()
            show_error(self, "تعذّر فتح الملف", str(exc))
            return
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            show_error(self, "تعذّر فتح الملف",
                       "خطأ غير متوقع أثناء قراءة الملف:\n\n%s\n\n%s"
                       % (exc, traceback.format_exc(limit=3)))
            return

        self.ytd = ytd
        self.edits = {}
        self.originals = {}
        self.current = None
        self._dirty = False
        self.canvas.clear_document()
        self.title_bar.set_dirty(False)

        progress = None
        if len(ytd.textures) > 6:
            progress = QProgressDialog("جاري بناء معاينات التكستشرات…", None, 0,
                                       len(ytd.textures), self)
            progress.setWindowTitle(os.path.basename(path))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(400)

        def on_progress(done, total):
            if progress is not None:
                progress.setValue(done)
                QApplication.processEvents()

        try:
            self.textures.populate(ytd, on_progress)
        finally:
            if progress is not None:
                progress.close()
            QApplication.restoreOverrideCursor()

        self.title_bar.set_file(os.path.basename(path))
        self._update_actions()
        self._status("فُتح %s — %d تكستشر"
                     % (os.path.basename(path), len(ytd.textures)))

        broken = [t for t in ytd.textures if not t.editable]
        if broken:
            show_info(
                self, "بعض التكستشرات غير مقروءة",
                "%d من أصل %d تكستشر بصيغة لا يستطيع المحرر فكّها. تظهر "
                "باللون البرتقالي وستُنسخ إلى الملف الناتج دون تغيير."
                % (len(broken), len(ytd.textures)),
                "\n\n".join("%s: %s" % (t.name, t.error) for t in broken))

    # -------------------------------------------------------------- التكستشر

    def _stash_current(self):
        """حفظ حالة الكانفس في قائمة التعديلات قبل الانتقال لتكستشر آخر."""
        if self.current is not None and self._dirty:
            img = self.canvas.to_numpy()
            if img is not None:
                self.edits[self.current.index] = img
                self.textures.update_thumbnail(self.current.index, img)

    def select_texture(self, index):
        if self.ytd is None:
            return
        entry = next((t for t in self.ytd.textures if t.index == index), None)
        if entry is None:
            return
        if self.current is not None and entry.index == self.current.index:
            return

        self._stash_current()

        if not entry.editable:
            self.current = entry
            self.canvas.clear_document()
            self._dirty = False
            self._refresh_status()
            self._update_actions()
            show_error(self, "تكستشر غير قابل للتحرير",
                       "%s\n\n%s" % (entry.name, entry.error))
            return

        try:
            if entry.index in self.edits:
                image = self.edits[entry.index]
            else:
                image = self.ytd.decode(entry)
            if entry.index not in self.originals:
                self.originals[entry.index] = self.ytd.decode(entry)
        except YtdError as exc:
            show_error(self, "تعذّر فكّ التكستشر", str(exc))
            return

        self.current = entry
        self._dirty = entry.index in self.edits
        self.canvas.load_numpy(image)
        self._refresh_status()
        self._update_actions()
        self._status("%s — %s" % (entry.name, entry.format_name))

    def _revert_texture(self):
        if self.current is None:
            return
        original = self.originals.get(self.current.index)
        if original is None:
            return
        if not ask(self, "استرجاع التكستشر",
                   "هل تتجاهل كل تعديلاتك على «%s» وتعيد تحميله من الملف؟"
                   % self.current.name, "استرجع"):
            return
        self.edits.pop(self.current.index, None)
        self.textures.mark_edited(self.current.index, False)
        self.textures.update_thumbnail(self.current.index, original)
        self._dirty = False
        self.canvas.load_numpy(original)
        self.title_bar.set_dirty(bool(self.edits))
        self._refresh_status()

    # ---------------------------------------------------------------- النص

    def _on_text_item(self, item):
        self.properties.load_text_item(item)
        if item is not None:
            self.rail.set_tool(cv.TOOL_TEXT)
            self.canvas.tool = cv.TOOL_TEXT

    def _sync_text_item(self):
        item = self.canvas.text_item
        if item is None:
            return
        s = self.properties.text_settings()
        item.text = s["text"]
        item.family = s["family"]
        item.size = s["size"]
        item.color = QColor(s["color"])
        item.bold = s["bold"]
        item.italic = s["italic"]
        self.canvas.update()

    def _apply_floating(self):
        """Ctrl+Enter يثبّت أي طبقة عائمة نشطة."""
        if self.canvas.text_item is not None:
            self._apply_text()
        elif self.canvas.image_item is not None:
            self._apply_image_item()

    def _apply_text(self):
        if self.canvas.text_item is None:
            return
        self._sync_text_item()
        if not self.canvas.apply_text():
            show_error(self, "لا يوجد ما يُثبَّت", "اكتب نصًا أولًا.")

    # ------------------------------------------------------ عمليات التكستشر

    def _clear_canvas(self):
        if ask(self, "مسح الكانفس",
               "هل تمسح التكستشر بالكامل ليصير شفافًا؟", "امسح"):
            self.canvas.clear_image()

    def _rotate(self, degrees):
        if self.current is None or not self.canvas.has_image():
            return
        w, h = self.canvas.image_size()
        if w != h:
            if not ask(self, "تدوير",
                       "تدوير تكستشر غير مربّع يبدّل عرضه بارتفاعه "
                       "(%d×%d يصير %d×%d)، فلا يعود قابلًا للكتابة داخل هذا "
                       "الملف.\n\nهل تريد التدوير على أي حال؟" % (w, h, h, w),
                       "دوّر", warning=True):
                return
        self.canvas.rotate(degrees)
        self._refresh_status()

    def _resize_dialog(self):
        if not self.canvas.has_image():
            return
        w, h = self.canvas.image_size()
        dlg = SizeDialog("تحجيم المحتوى",
                         [("w", "العرض", w, 16384), ("h", "الارتفاع", h, 16384)],
                         self)
        if not dlg.exec():
            return
        v = dlg.values()
        self.canvas.scale_content(v["w"], v["h"], dlg.keep_canvas.isChecked())
        self._refresh_status()

    def _crop_dialog(self):
        if not self.canvas.has_image():
            return
        w, h = self.canvas.image_size()
        dlg = SizeDialog("قص", [
            ("x", "س", 0, max(0, w - 1)),
            ("y", "ص", 0, max(0, h - 1)),
            ("w", "العرض", w, w),
            ("h", "الارتفاع", h, h),
        ], self)
        if not dlg.exec():
            return
        v = dlg.values()
        self.canvas.crop_to(QRect(v["x"], v["y"], v["w"], v["h"]),
                            keep_size=dlg.keep_canvas.isChecked())
        self._refresh_status()

    # -------------------------------------------------------- الصورة العائمة

    def _place_image(self):
        if not self.canvas.has_image():
            return
        path, _ = QFileDialog.getOpenFileName(self, "رفع صورة", "", IMAGE_FILTER)
        if not path:
            return
        try:
            arr = exporter.load_image(path)
        except ExportError as exc:
            show_error(self, "تعذّر تحميل الصورة", str(exc))
            return

        item = self.canvas.place_image(arr)
        if item is None:
            show_error(self, "تعذّر لصق الصورة",
                       "قُرئ الملف لكنه لا يحتوي على بكسلات صالحة.")
            return
        self._status("لُصقت %s بمقاس %d×%d — اسحبها لتحريكها ثم اضغط "
                     "«تثبيت الصورة»"
                     % (os.path.basename(path), *item.source_size))

    def _sync_image_item(self):
        """تطبيق الحقول الرقمية من اللوحة على الطبقة العائمة."""
        item = self.canvas.image_item
        if item is None:
            return
        g = self.properties.image_geometry()
        width = float(g["width"])
        height = float(g["height"])
        if g["keep_aspect"]:
            # العرض هو البعد القائد عندما تكون النسبة مقفلة
            if abs(width - item.width) > 0.5:
                height = max(1.0, width / item.aspect)
            elif abs(height - item.height) > 0.5:
                width = max(1.0, height * item.aspect)
            self.properties.sync_image_size(width, height)

        item.width = width
        item.height = height
        item.pos = QPointF(float(g["x"]), float(g["y"]))
        item.opacity = g["opacity"]
        self.canvas.update()

    def _apply_image_item(self):
        if self.canvas.image_item is None:
            return
        self._sync_image_item()
        self.canvas.apply_image_item()

    def _replace_texture(self):
        if self.current is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "استبدال التكستشر بصورة", "", IMAGE_FILTER)
        if not path:
            return
        try:
            arr = exporter.load_image(path)
        except ExportError as exc:
            show_error(self, "تعذّر تحميل الصورة", str(exc))
            return

        self.canvas.push_undo()
        self.canvas.clear_image()
        # تمديد الصورة إلى الأبعاد الأصلية حتى تبقى النتيجة قابلة للتصدير
        self.canvas.overlay_image(arr, fit=True)

    # -------------------------------------------------------------- التصدير

    def _export_png(self):
        if self.current is None or not self.canvas.has_image():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير PNG", self.current.name + ".png", "صورة PNG (*.png)")
        if not path:
            return
        try:
            exporter.export_png(self.canvas.to_numpy(), path)
        except ExportError as exc:
            show_error(self, "فشل التصدير", str(exc))
            return
        self._status("صُدِّر %s" % os.path.basename(path))

    def _export_dds(self):
        if self.current is None or self.ytd is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير DDS", self.current.name + ".dds", "تكستشر DDS (*.dds)")
        if not path:
            return
        try:
            raw = self.ytd.raw_data(self.current)
            exporter.export_dds(self.current, raw, path)
        except (ExportError, YtdError) as exc:
            show_error(self, "فشل التصدير", str(exc))
            return
        show_info(self, "صُدِّر DDS",
                  "صُدِّرت بيانات السطح كما هي مخزّنة داخل ملف الـ ytd.\n\n"
                  "ملاحظة: هذه ليست تعديلاتك غير المحفوظة على الكانفس.")

    # --------------------------------------------------------------- الحفظ

    def save_as_ytd(self):
        if self.ytd is None:
            return
        self._stash_current()

        if not self.edits:
            if not ask(self, "لا توجد تعديلات",
                       "لم يُعدَّل أي تكستشر. هل تحفظ نسخة من الملف رغم ذلك؟",
                       "احفظ نسخة"):
                return

        base = os.path.splitext(os.path.basename(self.ytd.path or "textures"))[0]
        default = os.path.join(os.path.dirname(self.ytd.path or ""),
                               base + "_edited.ytd")
        path, _ = QFileDialog.getSaveFileName(self, "حفظ باسم", default,
                                              YTD_FILTER)
        if not path:
            return
        if not path.lower().endswith(".ytd"):
            path += ".ytd"

        allow_overwrite = False
        if self.ytd.path and os.path.abspath(path).lower() == \
                os.path.abspath(self.ytd.path).lower():
            if not ask(self, "الكتابة فوق الملف الأصلي",
                       "سيُكتب فوق الملف الذي فتحته:\n\n%s\n\n"
                       "لا يمكن التراجع بعد الكتابة. هل تتابع؟" % self.ytd.path,
                       "اكتب فوقه", warning=True):
                return
            allow_overwrite = True

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            applied, problems = exporter.save_ytd_as(
                self.ytd, self.edits, path, allow_overwrite_source=allow_overwrite)
        except ExportError as exc:
            QApplication.restoreOverrideCursor()
            show_error(self, "فشل الحفظ", str(exc))
            return
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            show_error(self, "فشل الحفظ",
                       "خطأ غير متوقع أثناء كتابة الملف:\n\n%s\n\n%s"
                       % (exc, traceback.format_exc(limit=3)))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self._after_save(path, applied, problems)

    def _after_save(self, path, applied, problems):
        """
        تصفير حالة التعديل بعد حفظ ناجح.

        بدون هذا يظل البرنامج يعتبر التعديلات معلّقة، فيسأل عن «تغييرات غير
        محفوظة» عند الإغلاق رغم أن كل شيء كُتب فعلًا.
        """
        self.edits = {}
        self._dirty = False
        self.textures.clear_all_edited()
        self.title_bar.set_dirty(False)
        self._refresh_status()

        message = "كُتب %s\n\nحُدِّث %d تكستشر." % (os.path.basename(path),
                                                   len(applied))
        if problems:
            show_info(self, "حُفظ مع تنبيهات", message, "\n\n".join(problems))
        else:
            show_info(self, "تم الحفظ", message)
        self._status("حُفظ %s" % os.path.basename(path))

    # -------------------------------------------------------------- الإغلاق

    def closeEvent(self, ev):
        self._stash_current()
        if self.edits:
            if not ask(self, "تعديلات غير محفوظة",
                       "لديك تعديلات لم تُحفظ. هل تخرج دون حفظها؟",
                       "اخرج دون حفظ", warning=True):
                ev.ignore()
                return
        ev.accept()

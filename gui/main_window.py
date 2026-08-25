"""Main application window - wires the sidebar, canvas and tool panel together."""

from __future__ import annotations

import os
import traceback

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox,
                               QDockWidget, QFileDialog, QFormLayout, QLabel,
                               QMainWindow, QMessageBox, QProgressDialog, QSpinBox,
                               QStatusBar,
                               QVBoxLayout, QWidget)

from ..core import export_handler as exporter
from ..core import texture_handler as tex
from ..core.export_handler import ExportError
from ..core.ytd_handler import YtdError, YtdFile
from . import canvas as cv
from .canvas import Canvas, TextItem
from .texture_sidebar import TextureSidebar
from .tool_panel import ToolPanel
from .toolbar import EditorToolBar

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tga *.dds *.webp);;All files (*)"


class SizeDialog(QDialog):
    """Small numeric dialog used for both Resize and Crop."""

    def __init__(self, title, fields, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.spins = {}
        for key, label, value, maximum in fields:
            spin = QSpinBox()
            spin.setRange(0 if key in ("x", "y") else 1, maximum)
            spin.setValue(value)
            form.addRow(label, spin)
            self.spins[key] = spin
        layout.addLayout(form)

        self.keep_canvas = QCheckBox("Keep the original texture size")
        self.keep_canvas.setChecked(True)
        self.keep_canvas.setToolTip(
            "Required for saving back into the .ytd. Unchecking this changes "
            "the canvas size and the texture can no longer be written back.")
        layout.addWidget(self.keep_canvas)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {k: s.value() for k, s in self.spins.items()}


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YTD Texture Editor")
        self.resize(1500, 940)

        self.ytd: YtdFile | None = None
        self.current = None                 # TextureEntry
        self.edits = {}                     # texture index -> RGBA ndarray
        self.originals = {}                 # texture index -> pristine RGBA
        self._dirty = False

        self._build_ui()
        self._connect()
        self._update_actions()

    # ------------------------------------------------------------------ ui

    def _build_ui(self):
        self.toolbar = EditorToolBar(self)
        self.addToolBar(self.toolbar)

        self.canvas = Canvas(self)
        self.setCentralWidget(self.canvas)

        self.sidebar = TextureSidebar(self)
        dock_left = QDockWidget("Textures", self)
        dock_left.setWidget(self.sidebar)
        dock_left.setFeatures(QDockWidget.DockWidgetMovable)
        dock_left.setMinimumWidth(250)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock_left)

        self.tools = ToolPanel(self)
        dock_right = QDockWidget("Tool settings", self)
        dock_right.setWidget(self.tools)
        dock_right.setFeatures(QDockWidget.DockWidgetMovable)
        dock_right.setMinimumWidth(330)
        self.addDockWidget(Qt.RightDockWidgetArea, dock_right)
        self.resizeDocks([dock_left, dock_right], [270, 350], Qt.Horizontal)

        status = QStatusBar()
        self.setStatusBar(status)
        self.lbl_texture = QLabel("No texture")
        self.lbl_size = QLabel("-")
        self.lbl_format = QLabel("-")
        self.lbl_cursor = QLabel("-")
        self.lbl_zoom = QLabel("100%")
        for w in (self.lbl_texture, self.lbl_size, self.lbl_format,
                  self.lbl_cursor):
            status.addWidget(w)
            status.addWidget(QLabel("  |  "))
        status.addPermanentWidget(self.lbl_zoom)

        # Extra shortcuts that are not toolbar buttons
        act_apply = QAction(self)
        act_apply.setShortcut(QKeySequence("Ctrl+Return"))
        act_apply.triggered.connect(self._apply_floating)
        self.addAction(act_apply)

    def _connect(self):
        tb = self.toolbar
        tb.act_open.triggered.connect(self.open_ytd)
        tb.act_save_as.triggered.connect(self.save_as_ytd)
        tb.act_undo.triggered.connect(self.canvas.undo)
        tb.act_redo.triggered.connect(self.canvas.redo)
        tb.act_zoom_in.triggered.connect(lambda: self.canvas.zoom_by(1.25))
        tb.act_zoom_out.triggered.connect(lambda: self.canvas.zoom_by(1 / 1.25))
        tb.act_zoom_fit.triggered.connect(self.canvas.fit_to_view)
        tb.act_zoom_reset.triggered.connect(self.canvas.reset_zoom)
        tb.toolChanged.connect(self._set_tool)

        self.sidebar.textureSelected.connect(self.select_texture)

        c = self.canvas
        c.zoomChanged.connect(lambda z: self.lbl_zoom.setText("%d%%" % round(z * 100)))
        c.cursorMoved.connect(lambda x, y: self.lbl_cursor.setText("x %d, y %d" % (x, y)))
        c.historyChanged.connect(self._on_history)
        c.imageChanged.connect(self._on_image_changed)
        c.textItemChanged.connect(self._on_text_item)
        c.colorPicked.connect(self._on_color_picked)

        t = self.tools
        t.brushSizeChanged.connect(lambda v: setattr(c, "brush_size", v))
        t.brushOpacityChanged.connect(lambda v: setattr(c, "brush_opacity", v))
        t.brushColorChanged.connect(lambda col: setattr(c, "brush_color", col))
        t.antialiasChanged.connect(lambda v: setattr(c, "brush_hardness", v))
        t.shapeFilledChanged.connect(lambda v: setattr(c, "shape_filled", v))

        t.textEdited.connect(self._sync_text_item)
        t.applyTextRequested.connect(self._apply_text)
        t.cancelTextRequested.connect(self.canvas.cancel_text)

        c.imageItemChanged.connect(self._on_image_item)
        c.imageItemMoved.connect(self.tools.load_image_item)

        t.importImageRequested.connect(self._place_image)
        t.imageGeometryEdited.connect(self._sync_image_item)
        t.applyImageRequested.connect(self._apply_image_item)
        t.discardImageRequested.connect(self.canvas.cancel_image_item)
        t.fitImageRequested.connect(self.canvas.fit_image_item)
        t.resetImageSizeRequested.connect(self.canvas.reset_image_item_size)
        t.imageKeepAspectChanged.connect(
            lambda v: setattr(c, "image_keep_aspect", v))

        t.clearRequested.connect(self._clear_canvas)
        t.rotateRequested.connect(self._rotate)
        t.flipRequested.connect(self.canvas.flip)
        t.resizeRequested.connect(self._resize_dialog)
        t.cropRequested.connect(self._crop_dialog)
        t.importTextureRequested.connect(self._replace_texture)
        t.revertRequested.connect(self._revert_texture)
        t.exportPngRequested.connect(self._export_png)
        t.exportDdsRequested.connect(self._export_dds)

    # ------------------------------------------------------------- helpers

    def _error(self, title, message):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        box.exec()

    def _info(self, title, message, detail=None):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(title)
        box.setText(message)
        if detail:
            box.setDetailedText(detail)
        box.exec()

    def _update_actions(self):
        has_ytd = self.ytd is not None
        has_img = self.canvas.has_image()
        self.toolbar.act_save_as.setEnabled(has_ytd)
        self.tools.setEnabled(has_img)

    def _on_history(self, can_undo, can_redo):
        self.toolbar.act_undo.setEnabled(can_undo)
        self.toolbar.act_redo.setEnabled(can_redo)

    def _on_image_changed(self):
        if self.current is None:
            return
        if not self._dirty:
            self._dirty = True
            self.sidebar.mark_edited(self.current.index, True)
        self._refresh_status()

    def _refresh_status(self):
        if self.current is None:
            self.lbl_texture.setText("No texture")
            self.lbl_size.setText("-")
            self.lbl_format.setText("-")
            return
        name = self.current.name + (" *" if self._dirty else "")
        self.lbl_texture.setText(name)
        w, h = self.canvas.image_size()
        native = "%dx%d" % (self.current.width, self.current.height)
        self.lbl_size.setText(native if (w, h) == (self.current.width,
                                                   self.current.height)
                              else "%dx%d  (native %s)" % (w, h, native))
        self.lbl_format.setText("%s, %d mip(s)" % (self.current.format_name,
                                                   self.current.levels))

    def _set_tool(self, key):
        self.canvas.tool = key
        if key != cv.TOOL_TEXT and self.canvas.text_item is None:
            self.tools.set_text_controls_enabled(False)

    def _on_color_picked(self, color):
        self.tools.color_button.setColor(color)

    # ---------------------------------------------------------------- open

    def open_ytd(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open texture dictionary", "",
            "GTA V texture dictionary (*.ytd);;All files (*)")
        if not path:
            return
        self.load_ytd(path)

    def load_ytd(self, path):
        if self.ytd is not None and (self._dirty or self.edits):
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "You have unsaved texture edits. Open a different file anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ytd = YtdFile.open(path)
        except YtdError as exc:
            QApplication.restoreOverrideCursor()
            self._error("Could not open the .ytd", str(exc))
            return
        except Exception as exc:                       # unexpected
            QApplication.restoreOverrideCursor()
            self._error("Could not open the .ytd",
                        "Unexpected error while reading the file:\n\n%s\n\n%s"
                        % (exc, traceback.format_exc(limit=3)))
            return

        self.ytd = ytd
        self.edits = {}
        self.originals = {}
        self.current = None
        self._dirty = False
        self.canvas.clear_document()

        progress = None
        if len(ytd.textures) > 6:
            progress = QProgressDialog("Building texture previews...", None, 0,
                                       len(ytd.textures), self)
            progress.setWindowTitle("Opening %s" % os.path.basename(path))
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(400)

        def on_progress(done, total):
            if progress is not None:
                progress.setValue(done)
                QApplication.processEvents()

        try:
            self.sidebar.populate(ytd, on_progress)
        finally:
            if progress is not None:
                progress.close()
            QApplication.restoreOverrideCursor()

        self.toolbar.set_file_label(os.path.basename(path))
        self.setWindowTitle("YTD Texture Editor  -  %s" % os.path.basename(path))
        self._update_actions()

        broken = [t for t in ytd.textures if not t.editable]
        if broken:
            self._info(
                "Some textures could not be read",
                "%d of %d textures use a format this editor cannot decode. "
                "They are listed in orange and will be copied to the output "
                "file unchanged." % (len(broken), len(ytd.textures)),
                "\n\n".join("%s: %s" % (t.name, t.error) for t in broken))

    # ------------------------------------------------------------- texture

    def _stash_current(self):
        """Remember the current canvas into `edits` before switching away."""
        if self.current is not None and self._dirty:
            img = self.canvas.to_numpy()
            if img is not None:
                self.edits[self.current.index] = img

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
            self._error("Texture cannot be edited",
                        "%s\n\n%s" % (entry.name, entry.error))
            return

        try:
            if entry.index in self.edits:
                image = self.edits[entry.index]
            else:
                image = self.ytd.decode(entry)
                self.originals[entry.index] = image.copy()
        except YtdError as exc:
            self._error("Could not decode the texture", str(exc))
            return

        if entry.index not in self.originals:
            try:
                self.originals[entry.index] = self.ytd.decode(entry)
            except YtdError:
                pass

        self.current = entry
        self._dirty = entry.index in self.edits
        self.canvas.load_numpy(image)
        self._refresh_status()
        self._update_actions()

    def _revert_texture(self):
        if self.current is None:
            return
        original = self.originals.get(self.current.index)
        if original is None:
            return
        reply = QMessageBox.question(
            self, "Revert texture",
            "Discard all edits to '%s' and reload it from the file?"
            % self.current.name,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self.edits.pop(self.current.index, None)
        self.sidebar.mark_edited(self.current.index, False)
        self._dirty = False
        self.canvas.load_numpy(original)
        self._refresh_status()

    # ---------------------------------------------------------------- text

    def _on_text_item(self, item):
        self.tools.load_text_item(item)
        if item is not None:
            self.toolbar.set_tool(cv.TOOL_TEXT)
            self.canvas.tool = cv.TOOL_TEXT

    def _sync_text_item(self):
        item = self.canvas.text_item
        if item is None:
            return
        s = self.tools.text_settings()
        item.text = s["text"]
        item.family = s["family"]
        item.size = s["size"]
        item.color = QColor(s["color"])
        item.bold = s["bold"]
        item.italic = s["italic"]
        self.canvas.update()

    def _apply_floating(self):
        """Ctrl+Enter confirms whichever floating layer is active."""
        if self.canvas.text_item is not None:
            self._apply_text()
        elif self.canvas.image_item is not None:
            self._apply_image_item()

    def _apply_text(self):
        if self.canvas.text_item is None:
            return
        self._sync_text_item()
        if not self.canvas.apply_text():
            self._error("Nothing to apply", "Enter some text first.")

    # ------------------------------------------------------- image actions

    def _clear_canvas(self):
        reply = QMessageBox.question(
            self, "Clear canvas",
            "Erase the whole texture to transparent?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.canvas.clear_image()

    def _rotate(self, degrees):
        if self.current is None or not self.canvas.has_image():
            return
        w, h = self.canvas.image_size()
        if w != h:
            reply = QMessageBox.question(
                self, "Rotate",
                "Rotating a non-square texture swaps its width and height "
                "(%dx%d becomes %dx%d), so it can no longer be written back "
                "into this .ytd.\n\nRotate anyway?" % (w, h, h, w),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        self.canvas.rotate(degrees)
        self._refresh_status()

    def _resize_dialog(self):
        if not self.canvas.has_image():
            return
        w, h = self.canvas.image_size()
        dlg = SizeDialog("Resize artwork", [
            ("w", "Width", w, 16384),
            ("h", "Height", h, 16384),
        ], self)
        if not dlg.exec():
            return
        v = dlg.values()
        self.canvas.scale_content(v["w"], v["h"], dlg.keep_canvas.isChecked())
        self._refresh_status()

    def _crop_dialog(self):
        if not self.canvas.has_image():
            return
        from PySide6.QtCore import QRect
        w, h = self.canvas.image_size()
        dlg = SizeDialog("Crop", [
            ("x", "X", 0, max(0, w - 1)),
            ("y", "Y", 0, max(0, h - 1)),
            ("w", "Width", w, w),
            ("h", "Height", h, h),
        ], self)
        if not dlg.exec():
            return
        v = dlg.values()
        self.canvas.crop_to(QRect(v["x"], v["y"], v["w"], v["h"]),
                            keep_size=dlg.keep_canvas.isChecked())
        self._refresh_status()

    # -------------------------------------------------------- placed image

    def _place_image(self):
        """Upload a picture and drop it on the canvas as a movable layer."""
        if not self.canvas.has_image():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Upload image", "", IMAGE_FILTER)
        if not path:
            return
        try:
            arr = exporter.load_image(path)
        except ExportError as exc:
            self._error("Could not load the image", str(exc))
            return

        item = self.canvas.place_image(arr)
        if item is None:
            self._error("Could not place the image",
                        "The file loaded but contained no usable pixels.")
            return
        self.statusBar().showMessage(
            "Placed %s (%dx%d) - drag to move, drag a corner to resize, then "
            "Apply image" % (os.path.basename(path), *item.source_size), 8000)

    def _on_image_item(self, item):
        self.tools.load_image_item(item)

    def _sync_image_item(self):
        """Apply the numeric fields from the panel back onto the canvas item."""
        item = self.canvas.image_item
        if item is None:
            return
        g = self.tools.image_geometry()
        width = float(g["width"])
        height = float(g["height"])
        if g["keep_aspect"]:
            # width is the master dimension when the ratio is locked
            if abs(width - item.width) > 0.5:
                height = max(1.0, width / item.aspect)
            elif abs(height - item.height) > 0.5:
                width = max(1.0, height * item.aspect)
            self.tools.sync_image_size(width, height)

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
            self, "Replace texture with image", "", IMAGE_FILTER)
        if not path:
            return
        try:
            arr = exporter.load_image(path)
        except ExportError as exc:
            self._error("Could not load the image", str(exc))
            return

        self.canvas.push_undo()
        self.canvas.clear_image()
        # stretch to the texture's native size so the result stays exportable
        self.canvas.overlay_image(arr, fit=True)

    # -------------------------------------------------------------- export

    def _export_png(self):
        if self.current is None or not self.canvas.has_image():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", self.current.name + ".png", "PNG image (*.png)")
        if not path:
            return
        try:
            exporter.export_png(self.canvas.to_numpy(), path)
        except ExportError as exc:
            self._error("Export failed", str(exc))
            return
        self.statusBar().showMessage("Exported %s" % os.path.basename(path), 4000)

    def _export_dds(self):
        if self.current is None or self.ytd is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export DDS", self.current.name + ".dds", "DDS texture (*.dds)")
        if not path:
            return
        try:
            raw = self.ytd.raw_data(self.current)
            exporter.export_dds(self.current, raw, path)
        except (ExportError, YtdError) as exc:
            self._error("Export failed", str(exc))
            return
        self._info("DDS exported",
                   "Exported the texture's original, uncompressed-on-disk "
                   "surface data.\n\nNote: this is the data as stored in the "
                   ".ytd, not your unsaved canvas edits.")

    # ---------------------------------------------------------------- save

    def save_as_ytd(self):
        if self.ytd is None:
            return
        self._stash_current()

        if not self.edits:
            reply = QMessageBox.question(
                self, "No edits",
                "No textures have been modified. Save a copy of the .ytd anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        base = os.path.splitext(os.path.basename(self.ytd.path or "textures"))[0]
        default = os.path.join(os.path.dirname(self.ytd.path or ""),
                               base + "_edited.ytd")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As YTD", default,
            "GTA V texture dictionary (*.ytd);;All files (*)")
        if not path:
            return
        if not path.lower().endswith(".ytd"):
            path += ".ytd"

        allow_overwrite = False
        if self.ytd.path and os.path.abspath(path).lower() == \
                os.path.abspath(self.ytd.path).lower():
            reply = QMessageBox.warning(
                self, "Overwrite the original?",
                "This will overwrite the file you opened:\n\n%s\n\n"
                "There is no undo once it is written. Continue?" % self.ytd.path,
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
            allow_overwrite = True

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            applied, problems = exporter.save_ytd_as(
                self.ytd, self.edits, path, allow_overwrite_source=allow_overwrite)
        except ExportError as exc:
            QApplication.restoreOverrideCursor()
            self._error("Save failed", str(exc))
            return
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._error("Save failed",
                        "Unexpected error while writing the .ytd:\n\n%s\n\n%s"
                        % (exc, traceback.format_exc(limit=3)))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        message = "Wrote %s\n\n%d texture%s updated." % (
            os.path.basename(path), len(applied), "" if len(applied) == 1 else "s")
        if problems:
            self._info("Saved with warnings", message,
                       "\n\n".join(problems))
        else:
            self._info("Saved", message)
        self.statusBar().showMessage("Saved %s" % os.path.basename(path), 6000)

    # --------------------------------------------------------------- close

    def closeEvent(self, ev):
        self._stash_current()
        if self.edits:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "You have unsaved texture edits. Quit without saving?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                ev.ignore()
                return
        ev.accept()

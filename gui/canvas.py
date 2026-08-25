"""
The editing canvas: zoom / pan / brush / eraser / text / shapes / undo.

The canvas always works at the texture's native resolution. Zooming only
changes how it is displayed, never the pixel data, so a texture keeps its
exact dimensions all the way back into the .ytd.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import (QPoint, QPointF, QRect, QRectF, QSizeF, Qt, Signal)
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPen,
                           QPixmap, QTransform)
from PySide6.QtWidgets import QWidget

MIN_ZOOM = 0.02
MAX_ZOOM = 64.0
UNDO_LIMIT = 40

TOOL_BRUSH = "brush"
TOOL_ERASER = "eraser"
TOOL_TEXT = "text"
TOOL_RECT = "rect"
TOOL_ELLIPSE = "ellipse"
TOOL_LINE = "line"
TOOL_PICK = "pick"


# --------------------------------------------------------------------------
# numpy <-> QImage
# --------------------------------------------------------------------------

def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """(h, w, 4) uint8 RGBA -> QImage (owns its own buffer)."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
    return img.copy()


def qimage_to_numpy(img: QImage) -> np.ndarray:
    """QImage -> (h, w, 4) uint8 RGBA."""
    if img.format() != QImage.Format_RGBA8888:
        img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    buf = np.frombuffer(memoryview(ptr), dtype=np.uint8, count=img.sizeInBytes())
    buf = buf.reshape(h, img.bytesPerLine() // 4, 4)
    return np.ascontiguousarray(buf[:, :w, :])


class TextItem:
    """A floating, movable piece of text that has not been baked in yet."""

    def __init__(self, text, pos, family, size, color, bold=False, italic=False):
        self.text = text
        self.pos = QPointF(pos)          # image coordinates, text baseline-left
        self.family = family
        self.size = size
        self.color = QColor(color)
        self.bold = bold
        self.italic = italic

    def font(self):
        f = QFont(self.family)
        f.setPixelSize(max(1, int(self.size)))
        f.setBold(self.bold)
        f.setItalic(self.italic)
        return f


class ImageItem:
    """
    An imported picture floating above the texture until it is applied.

    Like TextItem, this lives outside the pixel data: it can be moved, scaled
    and discarded freely, and only becomes part of the texture when the user
    confirms it.
    """

    HANDLES = ("tl", "tr", "bl", "br")

    def __init__(self, image: QImage, pos, width, height):
        self.image = image                    # the source picture, unmodified
        self.pos = QPointF(pos)               # top-left, in image coordinates
        self.width = float(max(1.0, width))
        self.height = float(max(1.0, height))
        self.opacity = 1.0

    @property
    def source_size(self):
        return (self.image.width(), self.image.height())

    @property
    def aspect(self):
        if self.image.height() <= 0:
            return 1.0
        return self.image.width() / self.image.height()

    def rect(self) -> QRectF:
        return QRectF(self.pos, QSizeF(self.width, self.height))

    def corner(self, handle) -> QPointF:
        r = self.rect()
        return {"tl": r.topLeft(), "tr": r.topRight(),
                "bl": r.bottomLeft(), "br": r.bottomRight()}[handle]

    def resize_from(self, handle, img_pt, keep_aspect=True, minimum=4.0):
        """Drag one corner, keeping the opposite corner pinned."""
        r = self.rect()
        left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()

        if handle in ("br", "tr"):
            new_w = img_pt.x() - left
        else:
            new_w = right - img_pt.x()
        if handle in ("br", "bl"):
            new_h = img_pt.y() - top
        else:
            new_h = bottom - img_pt.y()

        new_w = max(minimum, new_w)
        new_h = max(minimum, new_h)
        if keep_aspect:
            # drive height from width so the picture never skews while dragging
            new_h = max(minimum, new_w / self.aspect)

        self.width = new_w
        self.height = new_h
        x = left if handle in ("br", "tr") else right - new_w
        y = top if handle in ("br", "bl") else bottom - new_h
        self.pos = QPointF(x, y)


class Canvas(QWidget):
    """Interactive texture editor surface."""

    zoomChanged = Signal(float)
    cursorMoved = Signal(int, int)
    imageChanged = Signal()
    historyChanged = Signal(bool, bool)      # can_undo, can_redo
    textItemChanged = Signal(object)         # TextItem or None
    imageItemChanged = Signal(object)        # ImageItem or None (placed/cleared)
    imageItemMoved = Signal(object)          # ImageItem, while dragging/resizing
    colorPicked = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(320, 240)

        self.image: QImage | None = None
        self.zoom = 1.0
        self.offset = QPointF(0, 0)          # top-left of image, in widget px

        self.tool = TOOL_BRUSH
        self.brush_size = 16
        self.brush_color = QColor(255, 60, 60, 255)
        self.brush_opacity = 1.0
        self.brush_hardness = True           # antialiased round brush
        self.shape_filled = False

        self.text_item: TextItem | None = None
        self.image_item: ImageItem | None = None
        self.image_keep_aspect = True

        self._undo: list[QImage] = []
        self._redo: list[QImage] = []

        self._stroke: QImage | None = None   # brush layer, composited on release
        self._last_pt: QPointF | None = None
        self._drag_start: QPointF | None = None
        self._drag_now: QPointF | None = None
        self._panning = False
        self._pan_anchor = QPoint()
        self._moving_text = False
        self._text_grab = QPointF()
        self._moving_image = False
        self._image_grab = QPointF()
        self._image_handle = None
        self._space_down = False

        self._checker = self._make_checker()

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _make_checker() -> QPixmap:
        pm = QPixmap(16, 16)
        pm.fill(QColor(58, 58, 62))
        p = QPainter(pm)
        p.fillRect(0, 0, 8, 8, QColor(48, 48, 52))
        p.fillRect(8, 8, 8, 8, QColor(48, 48, 52))
        p.end()
        return pm

    def has_image(self) -> bool:
        return self.image is not None

    def image_size(self):
        if self.image is None:
            return (0, 0)
        return (self.image.width(), self.image.height())

    # ------------------------------------------------------------ document

    def load_numpy(self, arr: np.ndarray):
        """Replace the document (clears history)."""
        self.image = numpy_to_qimage(arr)
        self._undo.clear()
        self._redo.clear()
        self._stroke = None
        self.set_text_item(None)
        self.set_image_item(None)
        self.fit_to_view()
        self.historyChanged.emit(False, False)
        self.update()

    def to_numpy(self) -> np.ndarray | None:
        if self.image is None:
            return None
        return qimage_to_numpy(self.image)

    def clear_document(self):
        self.image = None
        self._undo.clear()
        self._redo.clear()
        self.set_text_item(None)
        self.set_image_item(None)
        self.historyChanged.emit(False, False)
        self.update()

    # ------------------------------------------------------------- history

    def push_undo(self):
        if self.image is None:
            return
        self._undo.append(self.image.copy())
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()
        self._emit_history()

    def undo(self):
        if not self._undo or self.image is None:
            return
        self._redo.append(self.image.copy())
        self.image = self._undo.pop()
        self._emit_history()
        self.imageChanged.emit()
        self.update()

    def redo(self):
        if not self._redo or self.image is None:
            return
        self._undo.append(self.image.copy())
        self.image = self._redo.pop()
        self._emit_history()
        self.imageChanged.emit()
        self.update()

    def _emit_history(self):
        self.historyChanged.emit(bool(self._undo), bool(self._redo))

    # ---------------------------------------------------------------- view

    def fit_to_view(self):
        if self.image is None:
            return
        w, h = self.image.width(), self.image.height()
        if w == 0 or h == 0:
            return
        pad = 32
        sx = max(1, self.width() - pad) / w
        sy = max(1, self.height() - pad) / h
        self.set_zoom(min(sx, sy, 1.0) if min(sx, sy) < 1.0 else min(sx, sy),
                      center=True)

    def reset_zoom(self):
        self.set_zoom(1.0, center=True)

    def zoom_by(self, factor, focus: QPointF | None = None):
        if self.image is None:
            return
        if focus is None:
            focus = QPointF(self.width() / 2, self.height() / 2)
        img_pt = self.widget_to_image(focus)
        new = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        if abs(new - self.zoom) < 1e-9:
            return
        self.zoom = new
        # keep the point under the cursor anchored
        self.offset = QPointF(focus.x() - img_pt.x() * self.zoom,
                              focus.y() - img_pt.y() * self.zoom)
        self.zoomChanged.emit(self.zoom)
        self.update()

    def set_zoom(self, zoom, center=False):
        if self.image is None:
            return
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        if center:
            w = self.image.width() * self.zoom
            h = self.image.height() * self.zoom
            self.offset = QPointF((self.width() - w) / 2, (self.height() - h) / 2)
        self.zoomChanged.emit(self.zoom)
        self.update()

    def widget_to_image(self, pt: QPointF) -> QPointF:
        return QPointF((pt.x() - self.offset.x()) / self.zoom,
                       (pt.y() - self.offset.y()) / self.zoom)

    def image_to_widget(self, pt: QPointF) -> QPointF:
        return QPointF(pt.x() * self.zoom + self.offset.x(),
                       pt.y() * self.zoom + self.offset.y())

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.image is not None and ev.oldSize().width() <= 0:
            self.fit_to_view()

    # ---------------------------------------------------------------- text

    def set_text_item(self, item):
        self.text_item = item
        self.textItemChanged.emit(item)
        self.update()

    def apply_text(self):
        """Bake the floating text into the pixel data."""
        if self.image is None or self.text_item is None or not self.text_item.text:
            return False
        self.push_undo()
        p = QPainter(self.image)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setFont(self.text_item.font())
        p.setPen(QPen(self.text_item.color))
        p.drawText(self.text_item.pos, self.text_item.text)
        p.end()
        self.set_text_item(None)
        self.imageChanged.emit()
        self.update()
        return True

    def cancel_text(self):
        self.set_text_item(None)

    # -------------------------------------------------------- placed image

    def place_image(self, arr: np.ndarray, margin=0.85):
        """
        Drop an imported picture onto the canvas as a floating layer.

        It starts centred and scaled down to fit inside the texture (never
        scaled up), so an oversized photo lands somewhere usable instead of
        covering everything.
        """
        if self.image is None:
            return None
        src = numpy_to_qimage(arr)
        if src.isNull() or src.width() < 1 or src.height() < 1:
            return None

        cw, ch = self.image.width(), self.image.height()
        scale = min(1.0, (cw * margin) / src.width(), (ch * margin) / src.height())
        w = max(1.0, src.width() * scale)
        h = max(1.0, src.height() * scale)
        item = ImageItem(src, QPointF((cw - w) / 2, (ch - h) / 2), w, h)
        self.set_image_item(item)
        return item

    def set_image_item(self, item):
        self.image_item = item
        self.imageItemChanged.emit(item)
        self.update()

    def apply_image_item(self):
        """Bake the floating picture into the pixel data."""
        if self.image is None or self.image_item is None:
            return False
        item = self.image_item
        self.push_undo()
        p = QPainter(self.image)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setOpacity(item.opacity)
        p.drawImage(item.rect(), item.image)
        p.end()
        self.set_image_item(None)
        self.imageChanged.emit()
        self.update()
        return True

    def cancel_image_item(self):
        self.set_image_item(None)

    def fit_image_item(self):
        """Stretch the floating picture over the whole texture."""
        if self.image_item is None or self.image is None:
            return
        self.image_item.pos = QPointF(0, 0)
        self.image_item.width = float(self.image.width())
        self.image_item.height = float(self.image.height())
        self.imageItemMoved.emit(self.image_item)
        self.update()

    def reset_image_item_size(self):
        """Return the floating picture to its own pixel dimensions."""
        if self.image_item is None:
            return
        w, h = self.image_item.source_size
        self.image_item.width = float(w)
        self.image_item.height = float(h)
        self.imageItemMoved.emit(self.image_item)
        self.update()

    def _image_handle_at(self, widget_pt: QPointF, tolerance=8.0):
        """Which corner grip (if any) is under the cursor, in widget space."""
        if self.image_item is None:
            return None
        for handle in ImageItem.HANDLES:
            c = self.image_to_widget(self.image_item.corner(handle))
            if abs(c.x() - widget_pt.x()) <= tolerance and \
                    abs(c.y() - widget_pt.y()) <= tolerance:
                return handle
        return None

    def _image_hit(self, img_pt) -> bool:
        if self.image_item is None:
            return False
        return self.image_item.rect().contains(img_pt)

    # ------------------------------------------------------ whole-image ops

    def clear_image(self, color: QColor | None = None):
        if self.image is None:
            return
        self.push_undo()
        self.image.fill(color if color is not None else Qt.transparent)
        self.imageChanged.emit()
        self.update()

    def rotate(self, degrees):
        """Rotate by a multiple of 90 degrees (keeps the pixel data lossless)."""
        if self.image is None:
            return
        self.push_undo()
        self.image = self.image.transformed(QTransform().rotate(degrees))
        self.imageChanged.emit()
        self.fit_to_view()
        self.update()

    def flip(self, horizontal=True):
        if self.image is None:
            return
        self.push_undo()
        self.image = self.image.mirrored(horizontal, not horizontal)
        self.imageChanged.emit()
        self.update()

    def scale_content(self, width, height, keep_canvas=True, smooth=True):
        """
        Rescale the artwork.

        With `keep_canvas` (the default) the canvas keeps the texture's native
        dimensions and the scaled artwork is placed inside it - a .ytd texture
        has to keep its original size to be patched back in, so this is the
        variant that stays exportable.
        """
        if self.image is None:
            return
        self.push_undo()
        mode = Qt.SmoothTransformation if smooth else Qt.FastTransformation
        scaled = self.image.scaled(max(1, width), max(1, height),
                                   Qt.IgnoreAspectRatio, mode)
        if keep_canvas:
            canvas = QImage(self.image.size(), QImage.Format_RGBA8888)
            canvas.fill(Qt.transparent)
            p = QPainter(canvas)
            p.drawImage(0, 0, scaled)
            p.end()
            self.image = canvas
        else:
            self.image = scaled
        self.imageChanged.emit()
        self.fit_to_view()
        self.update()

    def crop_to(self, rect: QRect, keep_size=True):
        """
        Crop to `rect`.

        `keep_size` re-expands the crop back to the original canvas size, which
        is what you normally want here: a .ytd texture must keep its original
        dimensions to be written back in place.
        """
        if self.image is None:
            return
        rect = rect.intersected(self.image.rect())
        if rect.isEmpty():
            return
        self.push_undo()
        cropped = self.image.copy(rect)
        if keep_size:
            canvas = QImage(self.image.size(), QImage.Format_RGBA8888)
            canvas.fill(Qt.transparent)
            p = QPainter(canvas)
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawImage(canvas.rect(), cropped)
            p.end()
            self.image = canvas
        else:
            self.image = cropped
        self.imageChanged.emit()
        self.fit_to_view()
        self.update()

    def overlay_image(self, arr: np.ndarray, fit=True):
        """Paste another image on top of the current texture."""
        if self.image is None:
            return
        self.push_undo()
        overlay = numpy_to_qimage(arr)
        p = QPainter(self.image)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        if fit:
            p.drawImage(self.image.rect(), overlay)
        else:
            p.drawImage(0, 0, overlay)
        p.end()
        self.imageChanged.emit()
        self.update()

    # -------------------------------------------------------------- events

    def _pen(self, color=None):
        pen = QPen(color if color is not None else QColor(self.brush_color.rgb() | 0xFF000000))
        pen.setWidthF(max(1.0, float(self.brush_size)))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _begin_stroke(self, img_pt):
        if self.tool == TOOL_ERASER:
            self.push_undo()
            self._stroke = None
        else:
            self.push_undo()
            self._stroke = QImage(self.image.size(), QImage.Format_RGBA8888)
            self._stroke.fill(Qt.transparent)
        self._last_pt = img_pt
        self._paint_segment(img_pt, img_pt)

    def _paint_segment(self, a: QPointF, b: QPointF):
        """Draw one stroke segment. Brush goes to the layer, eraser to the image."""
        if self.tool == TOOL_ERASER:
            p = QPainter(self.image)
            p.setRenderHint(QPainter.Antialiasing, self.brush_hardness)
            p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
            col = QColor(0, 0, 0, max(1, int(round(self.brush_opacity * 255))))
            p.setPen(self._pen(col))
            p.drawLine(a, b)
            p.end()
        else:
            p = QPainter(self._stroke)
            p.setRenderHint(QPainter.Antialiasing, self.brush_hardness)
            col = QColor(self.brush_color)
            col.setAlpha(255)
            p.setPen(self._pen(col))
            p.drawLine(a, b)
            p.end()

    def _commit_stroke(self):
        """
        Composite the brush layer at the chosen opacity.

        Building the stroke on its own layer (rather than painting semi
        transparent segments straight onto the texture) keeps the opacity
        uniform - overlapping segments in a single stroke do not stack up.
        """
        if self._stroke is not None and self.image is not None:
            p = QPainter(self.image)
            p.setOpacity(self.brush_opacity)
            p.drawImage(0, 0, self._stroke)
            p.end()
        self._stroke = None
        self._last_pt = None
        self.imageChanged.emit()
        self.update()

    def _commit_shape(self):
        if self.image is None or self._drag_start is None or self._drag_now is None:
            return
        rect = QRectF(self._drag_start, self._drag_now).normalized()
        self.push_undo()
        p = QPainter(self.image)
        p.setRenderHint(QPainter.Antialiasing, True)
        col = QColor(self.brush_color)
        col.setAlpha(max(1, int(round(self.brush_opacity * 255))))
        p.setPen(self._pen(col))
        if self.shape_filled and self.tool in (TOOL_RECT, TOOL_ELLIPSE):
            p.setBrush(QBrush(col))
        else:
            p.setBrush(Qt.NoBrush)
        if self.tool == TOOL_RECT:
            p.drawRect(rect)
        elif self.tool == TOOL_ELLIPSE:
            p.drawEllipse(rect)
        else:
            p.drawLine(self._drag_start, self._drag_now)
        p.end()
        self._drag_start = None
        self._drag_now = None
        self.imageChanged.emit()
        self.update()

    def _text_hit(self, img_pt) -> bool:
        if self.text_item is None:
            return False
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(self.text_item.font())
        rect = fm.boundingRect(self.text_item.text or " ")
        rect.moveTo(self.text_item.pos.x(), self.text_item.pos.y() - fm.ascent())
        rect.adjust(-4, -4, 4, 4)
        return rect.contains(img_pt)

    def mousePressEvent(self, ev):
        if self.image is None:
            return
        pos = QPointF(ev.position())
        img_pt = self.widget_to_image(pos)

        if ev.button() == Qt.MiddleButton or self._space_down:
            self._panning = True
            self._pan_anchor = ev.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if ev.button() != Qt.LeftButton:
            return

        if self.tool == TOOL_PICK:
            self._pick_color(img_pt)
            return

        # A floating picture takes priority over drawing: its corner grips
        # first (they are small), then the text box, then its body.
        handle = self._image_handle_at(pos)
        if handle is not None:
            self._image_handle = handle
            return

        if self.text_item is not None and self._text_hit(img_pt):
            self._moving_text = True
            self._text_grab = img_pt - self.text_item.pos
            return

        if self._image_hit(img_pt):
            self._moving_image = True
            self._image_grab = img_pt - self.image_item.pos
            self.setCursor(Qt.ClosedHandCursor)
            return

        if self.tool == TOOL_TEXT:
            item = TextItem("New text", img_pt, "Segoe UI", 48,
                            QColor(self.brush_color))
            self.set_text_item(item)
            return

        if self.tool in (TOOL_BRUSH, TOOL_ERASER):
            self._begin_stroke(img_pt)
        elif self.tool in (TOOL_RECT, TOOL_ELLIPSE, TOOL_LINE):
            self._drag_start = img_pt
            self._drag_now = img_pt
        self.update()

    def mouseMoveEvent(self, ev):
        if self.image is None:
            return
        pos = QPointF(ev.position())
        img_pt = self.widget_to_image(pos)
        self.cursorMoved.emit(int(img_pt.x()), int(img_pt.y()))

        if self._panning:
            delta = ev.position().toPoint() - self._pan_anchor
            self._pan_anchor = ev.position().toPoint()
            self.offset += QPointF(delta)
            self.update()
            return

        if self._image_handle is not None and self.image_item is not None:
            self.image_item.resize_from(self._image_handle, img_pt,
                                        self.image_keep_aspect)
            self.imageItemMoved.emit(self.image_item)
            self.update()
            return

        if self._moving_image and self.image_item is not None:
            self.image_item.pos = img_pt - self._image_grab
            self.imageItemMoved.emit(self.image_item)
            self.update()
            return

        if self._moving_text and self.text_item is not None:
            self.text_item.pos = img_pt - self._text_grab
            self.update()
            return

        # hover feedback for the floating picture
        if self.image_item is not None and not (ev.buttons() & Qt.LeftButton):
            handle = self._image_handle_at(pos)
            if handle in ("tl", "br"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ("tr", "bl"):
                self.setCursor(Qt.SizeBDiagCursor)
            elif self._image_hit(img_pt):
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)

        if self._last_pt is not None and (ev.buttons() & Qt.LeftButton):
            self._paint_segment(self._last_pt, img_pt)
            self._last_pt = img_pt
            self.update()
        elif self._drag_start is not None and (ev.buttons() & Qt.LeftButton):
            self._drag_now = img_pt
            self.update()

    def mouseReleaseEvent(self, ev):
        if self._panning and (ev.button() == Qt.MiddleButton or not self._space_down):
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            return
        if self._image_handle is not None:
            self._image_handle = None
            return
        if self._moving_image:
            self._moving_image = False
            self.setCursor(Qt.ArrowCursor)
            return
        if self._moving_text:
            self._moving_text = False
            return
        if self._last_pt is not None:
            self._commit_stroke()
        elif self._drag_start is not None:
            self._commit_shape()

    def wheelEvent(self, ev):
        if self.image is None:
            return
        steps = ev.angleDelta().y() / 120.0
        if steps:
            self.zoom_by(1.15 ** steps, QPointF(ev.position()))

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self._space_down = True
            self.setCursor(Qt.OpenHandCursor)
        elif ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.text_item:
            self.cancel_text()
        elif ev.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.image_item:
            self.cancel_image_item()
        elif ev.key() == Qt.Key_Return and self.text_item:
            self.apply_text()
        elif ev.key() == Qt.Key_Return and self.image_item:
            self.apply_image_item()
        else:
            super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Space:
            self._space_down = False
            self.setCursor(Qt.ArrowCursor)
        else:
            super().keyReleaseEvent(ev)

    def _pick_color(self, img_pt):
        x, y = int(img_pt.x()), int(img_pt.y())
        if 0 <= x < self.image.width() and 0 <= y < self.image.height():
            self.colorPicked.emit(self.image.pixelColor(x, y))

    # --------------------------------------------------------------- paint

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 31, 34))

        if self.image is None:
            p.setPen(QColor(120, 122, 128))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "Open a .ytd file, then pick a texture from the left.")
            p.end()
            return

        w = self.image.width() * self.zoom
        h = self.image.height() * self.zoom
        target = QRectF(self.offset.x(), self.offset.y(), w, h)

        # transparency checkerboard, locked to the image rect
        p.save()
        p.setClipRect(target)
        p.setBrushOrigin(target.topLeft().toPoint())
        p.fillRect(target, QBrush(self._checker))
        p.restore()

        # nearest-neighbour when magnified so texel edges stay crisp
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        p.drawImage(target, self.image)

        if self._stroke is not None:
            p.setOpacity(self.brush_opacity)
            p.drawImage(target, self._stroke)
            p.setOpacity(1.0)

        p.save()
        p.translate(self.offset)
        p.scale(self.zoom, self.zoom)

        # the floating picture sits above the texture but below the chrome
        if self.image_item is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.setOpacity(self.image_item.opacity)
            p.drawImage(self.image_item.rect(), self.image_item.image)
            p.setOpacity(1.0)

        if self._drag_start is not None and self._drag_now is not None:
            col = QColor(self.brush_color)
            col.setAlpha(max(1, int(round(self.brush_opacity * 255))))
            pen = self._pen(col)
            p.setPen(pen)
            p.setBrush(QBrush(col) if self.shape_filled else Qt.NoBrush)
            rect = QRectF(self._drag_start, self._drag_now).normalized()
            if self.tool == TOOL_RECT:
                p.drawRect(rect)
            elif self.tool == TOOL_ELLIPSE:
                p.drawEllipse(rect)
            else:
                p.drawLine(self._drag_start, self._drag_now)

        if self.text_item is not None:
            p.setRenderHint(QPainter.TextAntialiasing, True)
            p.setFont(self.text_item.font())
            p.setPen(QPen(self.text_item.color))
            p.drawText(self.text_item.pos, self.text_item.text)
        p.restore()

        # selection outline for the pending text, drawn unscaled so it stays
        # a hairline at any zoom level
        if self.text_item is not None:
            from PySide6.QtGui import QFontMetricsF
            fm = QFontMetricsF(self.text_item.font())
            r = fm.boundingRect(self.text_item.text or " ")
            tl = self.image_to_widget(QPointF(self.text_item.pos.x(),
                                              self.text_item.pos.y() - fm.ascent()))
            box = QRectF(tl, QPointF(tl.x() + r.width() * self.zoom,
                                     tl.y() + fm.height() * self.zoom))
            pen = QPen(QColor(90, 170, 255))
            pen.setStyle(Qt.DashLine)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(box.adjusted(-3, -3, 3, 3))

        # selection frame + corner grips for the floating picture, drawn
        # unscaled so the grips stay grabbable at any zoom level
        if self.image_item is not None:
            tl = self.image_to_widget(self.image_item.rect().topLeft())
            br = self.image_to_widget(self.image_item.rect().bottomRight())
            frame = QRectF(tl, br)
            pen = QPen(QColor(90, 170, 255))
            pen.setStyle(Qt.DashLine)
            pen.setWidth(1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(frame)

            p.setPen(QPen(QColor(20, 22, 26)))
            p.setBrush(QBrush(QColor(90, 170, 255)))
            for handle in ImageItem.HANDLES:
                c = self.image_to_widget(self.image_item.corner(handle))
                p.drawRect(QRectF(c.x() - 4, c.y() - 4, 8, 8))

        # 1px border around the texture
        p.setPen(QPen(QColor(70, 72, 78)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(target)
        p.end()

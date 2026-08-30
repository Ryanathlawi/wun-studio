"""
مساحة الرسم: التكبير والتحريك والفرشاة والممحاة والنص والأشكال والتراجع.

المبدأ الثابت: الكانفس يعمل دائمًا على الدقة الأصلية للتكستشر. التكبير يغيّر
طريقة العرض فقط ولا يمسّ البكسلات إطلاقًا، فتحتفظ الصورة بأبعادها بالضبط
حتى تعود إلى ملف الـ ytd.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QImage,
                           QPainter, QPen, QPixmap, QTransform)
from PySide6.QtWidgets import QWidget

from . import theme

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

_SELECT = QColor(theme.ACCENT)


# --------------------------------------------------------------------------
# التحويل بين numpy و QImage
# --------------------------------------------------------------------------

def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """مصفوفة RGBA بشكل (h, w, 4) إلى QImage تملك ذاكرتها الخاصة."""
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    img = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888)
    return img.copy()


def qimage_to_numpy(img: QImage) -> np.ndarray:
    """
    QImage إلى مصفوفة RGBA بشكل (h, w, 4).

    النتيجة نسخة مستقلة قابلة للكتابة دائمًا: `constBits` يعطي عرضًا للقراءة
    فقط على ذاكرة الصورة الحيّة، ولو أُعيد كما هو لتغيّرت التعديلات المخزّنة
    كلما رسم المستخدم على الكانفس بعدها.
    """
    if img.format() != QImage.Format_RGBA8888:
        img = img.convertToFormat(QImage.Format_RGBA8888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    buf = np.frombuffer(memoryview(ptr), dtype=np.uint8, count=img.sizeInBytes())
    buf = buf.reshape(h, img.bytesPerLine() // 4, 4)
    return np.array(buf[:, :w, :], dtype=np.uint8, copy=True)


# --------------------------------------------------------------------------
# الطبقات العائمة
# --------------------------------------------------------------------------

class TextItem:
    """نص عائم قابل للتحريك لم يُدمج بعد في بكسلات التكستشر."""

    def __init__(self, text, pos, family, size, color, bold=False, italic=False):
        self.text = text
        self.pos = QPointF(pos)          # إحداثيات الصورة، عند خط أساس النص
        self.family = family
        self.size = size
        self.color = QColor(color)
        self.bold = bold
        self.italic = italic

    def font(self) -> QFont:
        f = QFont(self.family)
        f.setPixelSize(max(1, int(self.size)))
        f.setBold(self.bold)
        f.setItalic(self.italic)
        return f


class ImageItem:
    """
    صورة مستوردة تطفو فوق التكستشر حتى تُثبَّت.

    مثل النص، تعيش خارج بيانات البكسل: تُحرَّك وتُحجَّم وتُلغى بحرية، ولا
    تصير جزءًا من التكستشر إلا عند تأكيد المستخدم.
    """

    HANDLES = ("tl", "tr", "bl", "br")

    def __init__(self, image: QImage, pos, width, height):
        self.image = image                    # الصورة المصدر كما هي
        self.pos = QPointF(pos)               # الزاوية العليا بإحداثيات الصورة
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
        """سحب زاوية مع تثبيت الزاوية المقابلة."""
        r = self.rect()
        left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()

        new_w = (img_pt.x() - left) if handle in ("br", "tr") else (right - img_pt.x())
        new_h = (img_pt.y() - top) if handle in ("br", "bl") else (bottom - img_pt.y())
        new_w = max(minimum, new_w)
        new_h = max(minimum, new_h)

        if keep_aspect:
            if new_w / max(1e-6, self.aspect) > new_h:
                new_h = new_w / max(1e-6, self.aspect)
            else:
                new_w = new_h * self.aspect

        if handle in ("tl", "bl"):
            left = right - new_w
        if handle in ("tl", "tr"):
            top = bottom - new_h

        self.pos = QPointF(left, top)
        self.width = new_w
        self.height = new_h


# --------------------------------------------------------------------------
# الكانفس
# --------------------------------------------------------------------------

class Canvas(QWidget):
    """مساحة العرض والتحرير."""

    zoomChanged = Signal(float)
    cursorMoved = Signal(int, int)
    imageChanged = Signal()
    historyChanged = Signal(bool, bool)      # يمكن التراجع، يمكن الإعادة
    textItemChanged = Signal(object)         # TextItem أو None
    imageItemChanged = Signal(object)        # ImageItem أو None
    imageItemMoved = Signal(object)          # أثناء السحب أو التحجيم
    colorPicked = Signal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(320, 240)
        # الكانفس يعمل بإحداثيات صورة، فلا يُعكس مع اتجاه الواجهة العربي
        self.setLayoutDirection(Qt.LeftToRight)

        self.image: QImage | None = None
        self.zoom = 1.0
        self.offset = QPointF(0, 0)          # زاوية الصورة العليا ببكسل الودجت

        self.tool = TOOL_BRUSH
        self.brush_size = 16
        self.brush_color = QColor(theme.ACCENT)
        self.brush_opacity = 1.0
        self.brush_hardness = True           # حواف ناعمة
        self.shape_filled = False

        self.text_item: TextItem | None = None
        self.image_item: ImageItem | None = None
        self.image_keep_aspect = True

        self._undo: list[QImage] = []
        self._redo: list[QImage] = []

        self._stroke: QImage | None = None   # طبقة الفرشاة، تُدمج عند الإفلات
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
        self._hover = QPointF(-999, -999)

        self._checker = self._make_checker()

    # ------------------------------------------------------------- مساعدات

    @staticmethod
    def _make_checker() -> QPixmap:
        """رقعة شطرنجية تُظهر مناطق الشفافية."""
        pm = QPixmap(16, 16)
        pm.fill(QColor("#2C3038"))
        p = QPainter(pm)
        p.fillRect(0, 0, 8, 8, QColor("#23272E"))
        p.fillRect(8, 8, 8, 8, QColor("#23272E"))
        p.end()
        return pm

    def has_image(self) -> bool:
        return self.image is not None

    def image_size(self):
        if self.image is None:
            return (0, 0)
        return (self.image.width(), self.image.height())

    # -------------------------------------------------------------- المستند

    def load_numpy(self, arr: np.ndarray):
        """استبدال المستند بالكامل (يمسح سجل التراجع)."""
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

    # --------------------------------------------------------------- السجل

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

    # --------------------------------------------------------------- العرض

    def fit_to_view(self):
        if self.image is None:
            return
        w, h = self.image.width(), self.image.height()
        if w == 0 or h == 0:
            return
        pad = 48
        sx = max(1, self.width() - pad) / w
        sy = max(1, self.height() - pad) / h
        self.set_zoom(min(sx, sy), center=True)

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
        # تثبيت النقطة الواقعة تحت المؤشر في مكانها
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

    # ----------------------------------------------------------------- النص

    def set_text_item(self, item):
        self.text_item = item
        self.textItemChanged.emit(item)
        self.update()

    def apply_text(self) -> bool:
        """دمج النص العائم داخل بيانات البكسل."""
        if self.image is None or self.text_item is None or not self.text_item.text:
            return False
        self.push_undo()
        p = QPainter(self.image)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setLayoutDirection(Qt.RightToLeft)
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

    # -------------------------------------------------------- الصورة العائمة

    def place_image(self, arr: np.ndarray, margin=0.85):
        """
        إسقاط صورة مستوردة على الكانفس كطبقة عائمة.

        تبدأ في المنتصف ومصغّرة لتدخل داخل التكستشر (ولا تُكبَّر أبدًا)، حتى
        لا تغطي صورة ضخمة كل شيء عند لصقها.
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

    def apply_image_item(self) -> bool:
        """دمج الصورة العائمة داخل بيانات البكسل."""
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
        """تمديد الصورة العائمة على كامل التكستشر."""
        if self.image_item is None or self.image is None:
            return
        self.image_item.pos = QPointF(0, 0)
        self.image_item.width = float(self.image.width())
        self.image_item.height = float(self.image.height())
        self.imageItemMoved.emit(self.image_item)
        self.update()

    def reset_image_item_size(self):
        """إعادة الصورة العائمة إلى أبعادها الأصلية."""
        if self.image_item is None:
            return
        w, h = self.image_item.source_size
        self.image_item.width = float(w)
        self.image_item.height = float(h)
        self.imageItemMoved.emit(self.image_item)
        self.update()

    def _image_handle_at(self, widget_pt: QPointF, tolerance=9.0):
        """أي مقبض زاوية يقع تحت المؤشر (بإحداثيات الودجت)."""
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

    # ------------------------------------------------- عمليات على كامل الصورة

    def clear_image(self, color: QColor | None = None):
        if self.image is None:
            return
        self.push_undo()
        self.image.fill(color if color is not None else Qt.transparent)
        self.imageChanged.emit()
        self.update()

    def rotate(self, degrees):
        """تدوير بمضاعفات 90 درجة (بلا فقد في البكسلات)."""
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
        تحجيم محتوى الصورة.

        مع keep_canvas (الوضع الافتراضي) يحتفظ الكانفس بأبعاد التكستشر الأصلية
        ويوضع المحتوى المحجَّم بداخله، لأن تكستشر الـ ytd لا بد أن يبقى بأبعاده
        الأصلية ليعود إلى الملف، فهذا هو الخيار الذي يبقى قابلًا للتصدير.
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
        قص إلى المستطيل المحدد.

        keep_size يعيد تمديد الاقتصاص إلى حجم الكانفس الأصلي، وهو المطلوب
        عادةً هنا لأن التكستشر لا بد أن يحافظ على أبعاده ليُكتب في مكانه.
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
        """لصق صورة أخرى فوق التكستشر الحالي."""
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

    # --------------------------------------------------------------- الرسم

    def _pen(self, color=None) -> QPen:
        pen = QPen(color if color is not None
                   else QColor(self.brush_color.rgb() | 0xFF000000))
        pen.setWidthF(max(1.0, float(self.brush_size)))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _begin_stroke(self, img_pt):
        self.push_undo()
        if self.tool == TOOL_ERASER:
            self._stroke = None
        else:
            self._stroke = QImage(self.image.size(), QImage.Format_RGBA8888)
            self._stroke.fill(Qt.transparent)
        self._last_pt = img_pt
        self._paint_segment(img_pt, img_pt)

    def _paint_segment(self, a: QPointF, b: QPointF):
        """رسم مقطع واحد: الفرشاة على الطبقة، والممحاة على الصورة مباشرة."""
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
        دمج طبقة الفرشاة بالشفافية المختارة.

        بناء الضربة على طبقة مستقلة - بدل رسم مقاطع نصف شفافة مباشرة على
        التكستشر - يبقي الشفافية منتظمة، فلا تتراكم المقاطع المتداخلة داخل
        الضربة الواحدة فتصير أغمق.
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
        p.setBrush(QBrush(col) if (self.shape_filled and
                                   self.tool in (TOOL_RECT, TOOL_ELLIPSE))
                   else Qt.NoBrush)
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
        fm = QFontMetricsF(self.text_item.font())
        rect = fm.boundingRect(self.text_item.text or " ")
        rect.moveTo(self.text_item.pos.x(), self.text_item.pos.y() - fm.ascent())
        rect.adjust(-4, -4, 4, 4)
        return rect.contains(img_pt)

    # -------------------------------------------------------------- الأحداث

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

        # الطبقة العائمة لها الأولوية على الرسم: المقابض الصغيرة أولًا،
        # ثم صندوق النص، ثم جسم الصورة.
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
            self.set_text_item(TextItem("نص جديد", img_pt, theme.FONT_FAMILY,
                                        48, QColor(self.brush_color)))
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
        self._hover = pos
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

    def leaveEvent(self, ev):
        self._hover = QPointF(-999, -999)
        self.update()
        super().leaveEvent(ev)

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

    # ---------------------------------------------------------------- الرسم

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BG_CANVAS))

        if self.image is None:
            p.end()
            return

        w = self.image.width() * self.zoom
        h = self.image.height() * self.zoom
        target = QRectF(self.offset.x(), self.offset.y(), w, h)

        # الرقعة الشطرنجية محصورة داخل مستطيل الصورة
        p.save()
        p.setClipRect(target)
        p.setBrushOrigin(target.topLeft().toPoint())
        p.fillRect(target, QBrush(self._checker))
        p.restore()

        # عند التكبير نستخدم أقرب جار حتى تبقى حواف التكسل حادة
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1.0)
        p.drawImage(target, self.image)

        if self._stroke is not None:
            p.setOpacity(self.brush_opacity)
            p.drawImage(target, self._stroke)
            p.setOpacity(1.0)

        p.save()
        p.translate(self.offset)
        p.scale(self.zoom, self.zoom)

        # الصورة العائمة فوق التكستشر وتحت عناصر الواجهة
        if self.image_item is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.setOpacity(self.image_item.opacity)
            p.drawImage(self.image_item.rect(), self.image_item.image)
            p.setOpacity(1.0)

        if self._drag_start is not None and self._drag_now is not None:
            col = QColor(self.brush_color)
            col.setAlpha(max(1, int(round(self.brush_opacity * 255))))
            p.setPen(self._pen(col))
            p.setBrush(QBrush(col) if (self.shape_filled and
                                       self.tool in (TOOL_RECT, TOOL_ELLIPSE))
                       else Qt.NoBrush)
            rect = QRectF(self._drag_start, self._drag_now).normalized()
            if self.tool == TOOL_RECT:
                p.drawRect(rect)
            elif self.tool == TOOL_ELLIPSE:
                p.drawEllipse(rect)
            else:
                p.drawLine(self._drag_start, self._drag_now)

        if self.text_item is not None:
            p.setRenderHint(QPainter.TextAntialiasing, True)
            p.setLayoutDirection(Qt.RightToLeft)
            p.setFont(self.text_item.font())
            p.setPen(QPen(self.text_item.color))
            p.drawText(self.text_item.pos, self.text_item.text)
        p.restore()

        # إطار اختيار النص، يُرسم بلا تكبير ليبقى شعرةً عند أي نسبة
        if self.text_item is not None:
            fm = QFontMetricsF(self.text_item.font())
            r = fm.boundingRect(self.text_item.text or " ")
            tl = self.image_to_widget(QPointF(self.text_item.pos.x(),
                                              self.text_item.pos.y() - fm.ascent()))
            box = QRectF(tl, QPointF(tl.x() + r.width() * self.zoom,
                                     tl.y() + fm.height() * self.zoom))
            pen = QPen(_SELECT)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(box.adjusted(-3, -3, 3, 3))

        # إطار ومقابض الصورة العائمة، بلا تكبير حتى تبقى قابلة للإمساك
        if self.image_item is not None:
            tl = self.image_to_widget(self.image_item.rect().topLeft())
            br = self.image_to_widget(self.image_item.rect().bottomRight())
            pen = QPen(_SELECT)
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(tl, br))

            p.setPen(QPen(QColor(theme.BG_APP)))
            p.setBrush(QBrush(_SELECT))
            for handle in ImageItem.HANDLES:
                c = self.image_to_widget(self.image_item.corner(handle))
                p.drawRoundedRect(QRectF(c.x() - 4.5, c.y() - 4.5, 9, 9), 2, 2)

        # حلقة تُظهر حجم الفرشاة الحقيقي تحت المؤشر
        if (self.tool in (TOOL_BRUSH, TOOL_ERASER)
                and self._hover.x() > -900 and not self._panning
                and self.image_item is None):
            radius = max(1.5, self.brush_size * self.zoom / 2)
            ring = QPen(QColor(255, 255, 255, 190))
            ring.setWidth(1)
            p.setPen(ring)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(self._hover, radius, radius)
            ring.setColor(QColor(0, 0, 0, 130))
            p.setPen(ring)
            p.drawEllipse(self._hover, radius + 1, radius + 1)

        # إطار رفيع حول التكستشر
        p.setPen(QPen(QColor(theme.BORDER_HI)))
        p.setBrush(Qt.NoBrush)
        p.drawRect(target)
        p.end()

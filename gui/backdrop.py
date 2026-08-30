"""
نقشة الخلفية: خطوط كنتور طوبوغرافية خفيفة.

تُولَّد مرة واحدة عند الإقلاع كبلاطة قابلة للتكرار، ثم تُرسم مكرّرة خلف
الأسطح. البلاطة قابلة للتكرار لأنها مجموع جيوب بترددات صحيحة، فحوافها
تتطابق بلا خط فاصل.

الشدّة منخفضة عمدًا: النقشة تُثري الخلفية ولا تنافس المحتوى، ولا تُرسم
خلف الكانفس إطلاقًا حتى لا تشوّش على معاينة التكستشر.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPixmap

from . import theme

TILE = 512
_CACHE: dict[tuple, QPixmap] = {}


def _field(size, seed):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xx = xx / size * 2 * np.pi
    yy = yy / size * 2 * np.pi

    field = np.zeros((size, size), dtype=np.float32)
    for frequency, weight in ((1, 1.0), (2, 0.55), (3, 0.32), (5, 0.18)):
        for _ in range(3):
            phase = rng.uniform(0, 2 * np.pi)
            angle = rng.uniform(0, 2 * np.pi)
            fx = frequency * np.cos(angle)
            fy = frequency * np.sin(angle)
            # الترددات تُقرّب لأعداد صحيحة حتى تبقى البلاطة قابلة للتكرار
            fx = np.round(fx)
            fy = np.round(fy)
            field += weight * np.sin(fx * xx + fy * yy + phase)

    field -= field.min()
    field /= max(1e-6, field.max())
    return field


def _lines(field, levels, thickness):
    scaled = field * levels
    distance = np.abs(scaled - np.round(scaled))
    alpha = np.clip(1.0 - distance / max(1e-6, thickness), 0.0, 1.0)
    return alpha ** 1.6


def tile(colour=None, seed=11, levels=15, thickness=0.11, strength=0.5):
    key = (colour or theme.CONTOUR, seed, levels, thickness, strength)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit

    alpha = _lines(_field(TILE, seed), levels, thickness) * strength
    base = QColor(colour or theme.CONTOUR)

    buffer = np.zeros((TILE, TILE, 4), dtype=np.uint8)
    buffer[..., 0] = base.red()
    buffer[..., 1] = base.green()
    buffer[..., 2] = base.blue()
    buffer[..., 3] = np.clip(alpha * 255, 0, 255).astype(np.uint8)

    image = QImage(buffer.data, TILE, TILE, TILE * 4, QImage.Format_RGBA8888)
    pixmap = QPixmap.fromImage(image.copy())
    _CACHE[key] = pixmap
    return pixmap


def paint(painter, rect, offset=None, **kwargs):
    """رسم النقشة مكرّرة داخل مستطيل."""
    painter.save()
    painter.setClipRect(rect)
    if offset is not None:
        painter.setBrushOrigin(offset)
    painter.fillRect(rect, tile(**kwargs))
    painter.restore()


def glow(painter, rect, colour=None, alpha=26):
    """
    توهّج علوي خفيف بلون التمييز.

    يعطي عمقًا للسطح بلا تدرّج ثقيل: دائرة كبيرة شبه شفافة أعلى المنطقة.
    """
    from PySide6.QtGui import QRadialGradient

    base = QColor(colour or theme.ACCENT)
    base.setAlpha(alpha)
    centre = rect.center()
    radius = max(rect.width(), rect.height()) * 0.75
    gradient = QRadialGradient(centre.x(), rect.top() - radius * 0.15, radius)
    gradient.setColorAt(0.0, base)
    transparent = QColor(base)
    transparent.setAlpha(0)
    gradient.setColorAt(1.0, transparent)

    painter.save()
    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRect(rect)
    painter.restore()

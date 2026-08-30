from __future__ import annotations

import numpy as np

NEUTRAL = {
    "brightness": 0,
    "contrast": 0,
    "saturation": 0,
    "hue": 0,
    "invert": False,
    "grayscale": False,
}

_LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def is_neutral(params) -> bool:
    for key, value in NEUTRAL.items():
        if params.get(key, value) != value:
            return False
    return True


def _hue_matrix(degrees: float) -> np.ndarray:
    angle = np.deg2rad(degrees)
    cos_a = float(np.cos(angle))
    sin_a = float(np.sin(angle))
    return np.array([
        [0.213 + cos_a * 0.787 - sin_a * 0.213,
         0.715 - cos_a * 0.715 - sin_a * 0.715,
         0.072 - cos_a * 0.072 + sin_a * 0.928],
        [0.213 - cos_a * 0.213 + sin_a * 0.143,
         0.715 + cos_a * 0.285 + sin_a * 0.140,
         0.072 - cos_a * 0.072 - sin_a * 0.283],
        [0.213 - cos_a * 0.213 - sin_a * 0.787,
         0.715 - cos_a * 0.715 + sin_a * 0.715,
         0.072 + cos_a * 0.928 + sin_a * 0.072],
    ], dtype=np.float32)


def apply(image: np.ndarray, params) -> np.ndarray:
    image = np.ascontiguousarray(image, dtype=np.uint8)
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("expected an (h, w, 4) RGBA array")
    if is_neutral(params):
        return image.copy()

    rgb = image[..., :3].astype(np.float32)
    alpha = image[..., 3]

    brightness = float(params.get("brightness", 0))
    if brightness:
        rgb += brightness * 2.55

    contrast = float(params.get("contrast", 0))
    if contrast:
        factor = (259.0 * (contrast + 255.0)) / (255.0 * (259.0 - contrast))
        rgb = factor * (rgb - 128.0) + 128.0

    hue = float(params.get("hue", 0))
    if hue:
        rgb = rgb @ _hue_matrix(hue).T

    saturation = float(params.get("saturation", 0))
    if saturation:
        gray = rgb @ _LUMA
        amount = 1.0 + saturation / 100.0
        rgb = gray[..., None] + (rgb - gray[..., None]) * amount

    if params.get("grayscale"):
        gray = rgb @ _LUMA
        rgb = np.repeat(gray[..., None], 3, axis=2)

    if params.get("invert"):
        rgb = 255.0 - rgb

    out = np.empty_like(image)
    np.clip(rgb, 0, 255, out=rgb)
    out[..., :3] = rgb.astype(np.uint8)
    out[..., 3] = alpha
    return out


def proxy(image: np.ndarray, longest=1024):
    h, w = image.shape[:2]
    step = max(1, int(max(w, h) / max(1, longest)))
    if step == 1:
        return image, 1
    return np.ascontiguousarray(image[::step, ::step]), step


def flood_fill(image: np.ndarray, x: int, y: int, colour, tolerance=32,
               region=None) -> np.ndarray:
    image = np.ascontiguousarray(image, dtype=np.uint8)
    h, w = image.shape[:2]
    if not (0 <= x < w and 0 <= y < h):
        return image.copy()

    x0, y0, x1, y1 = (0, 0, w, h) if region is None else region
    x0 = max(0, min(x0, w))
    y0 = max(0, min(y0, h))
    x1 = max(x0, min(x1, w))
    y1 = max(y0, min(y1, h))
    if not (x0 <= x < x1 and y0 <= y < y1):
        return image.copy()

    view = image[y0:y1, x0:x1]
    target = view[y - y0, x - x0].astype(np.int16)
    similar = np.abs(view.astype(np.int16) - target).max(axis=2) <= tolerance

    mask = _flood_mask(similar, y - y0, x - x0)
    out = image.copy()
    patch = out[y0:y1, x0:x1]
    patch[mask] = np.array(colour, dtype=np.uint8)
    return out


def _flood_mask(similar: np.ndarray, seed_row: int, seed_col: int) -> np.ndarray:
    height, width = similar.shape
    mask = np.zeros((height, width), dtype=bool)
    if not similar[seed_row, seed_col]:
        return mask

    stack = [(seed_row, seed_col)]
    while stack:
        row, col = stack.pop()
        open_row = similar[row] & ~mask[row]
        if not open_row[col]:
            continue

        blocked = np.flatnonzero(~open_row[:col])
        left = int(blocked[-1]) + 1 if blocked.size else 0
        blocked = np.flatnonzero(~open_row[col + 1:])
        right = col + int(blocked[0]) if blocked.size else width - 1
        mask[row, left:right + 1] = True

        for neighbour in (row - 1, row + 1):
            if not (0 <= neighbour < height):
                continue
            segment = (similar[neighbour, left:right + 1]
                       & ~mask[neighbour, left:right + 1])
            if not segment.any():
                continue
            found = np.flatnonzero(segment)
            starts = found[np.concatenate(([True], np.diff(found) > 1))]
            for start in starts:
                stack.append((neighbour, left + int(start)))
    return mask


def linear_gradient(shape, start, end, colour_a, colour_b) -> np.ndarray:
    h, w = shape
    x0, y0 = float(start[0]), float(start[1])
    x1, y1 = float(end[0]), float(end[1])
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-6:
        t = np.zeros((h, w), dtype=np.float32)
    else:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        t = ((xx - x0) * dx + (yy - y0) * dy) / length_sq
        np.clip(t, 0.0, 1.0, out=t)

    a = np.array(colour_a, dtype=np.float32)
    b = np.array(colour_b, dtype=np.float32)
    out = a[None, None, :] + (b - a)[None, None, :] * t[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)

from __future__ import annotations

import os

import numpy as np

from . import texture_handler as tex
from . import ytd_writer as writer
from .ytd_handler import YtdError, YtdFile

PRESETS = {
    "clothing": {"label": "ملابس", "max_size": 1024, "opaque_to_dxt1": True},
    "vehicles": {"label": "سيارات", "max_size": 2048, "opaque_to_dxt1": True},
    "maps": {"label": "خرائط", "max_size": 2048, "opaque_to_dxt1": False},
    "aggressive": {"label": "ضغط أقصى", "max_size": 512,
                   "opaque_to_dxt1": True},
    "formats_only": {"label": "الصيغ فقط", "max_size": 0,
                     "opaque_to_dxt1": True},
}

DEFAULT_RULES = {"max_size": 1024, "opaque_to_dxt1": True, "min_size": 64}

ALPHA_FORMATS = (tex.FMT_DXT3, tex.FMT_DXT5, tex.FMT_BC7,
                 tex.FMT_A8R8G8B8, tex.FMT_A8B8G8R8, tex.FMT_A1R5G5B5,
                 tex.FMT_A8)

CONVERTIBLE = (tex.FMT_DXT3, tex.FMT_DXT5)


def uses_alpha(ytd: YtdFile, entry) -> bool:
    if entry.format not in ALPHA_FORMATS:
        return False

    raw = ytd.raw_data(entry)
    level = tex.level_size(entry.format, entry.width, entry.height)
    blocks = memoryview(raw)[:level]

    if entry.format == tex.FMT_DXT5:
        for i in range(0, len(blocks) - 15, 16):
            if blocks[i] != 255 or blocks[i + 1] != 255:
                return True
        return False

    if entry.format == tex.FMT_DXT3:
        for i in range(0, len(blocks) - 15, 16):
            if any(blocks[i + j] != 255 for j in range(8)):
                return True
        return False

    decoded = ytd.decode(entry)
    return bool(decoded[..., 3].min() < 255)


def _target_size(width, height, max_size, min_size):
    if not max_size:
        return width, height
    while max(width, height) > max_size and min(width, height) > min_size:
        width = max(1, width // 2)
        height = max(1, height // 2)
    return width, height


def _natural_levels(width, height):
    count = 1
    while width > 4 and height > 4:
        width = max(1, width >> 1)
        height = max(1, height >> 1)
        count += 1
    return count


class TexturePlan:

    def __init__(self, entry, width, height, fmt, levels, reasons):
        self.entry = entry
        self.name = entry.name
        self.width = width
        self.height = height
        self.format = fmt
        self.levels = levels
        self.reasons = reasons
        self.old_bytes = entry.data_size
        self.new_bytes = tex.total_size(fmt, width, height, levels)

    @property
    def changed(self):
        return bool(self.reasons)

    @property
    def saved(self):
        return max(0, self.old_bytes - self.new_bytes)


class FilePlan:

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.textures = []
        self.error = None
        self.file_size = os.path.getsize(path) if os.path.exists(path) else 0

    @property
    def changed(self):
        return any(t.changed for t in self.textures)

    @property
    def old_bytes(self):
        return sum(t.old_bytes for t in self.textures)

    @property
    def new_bytes(self):
        return sum(t.new_bytes for t in self.textures)

    @property
    def saved(self):
        return max(0, self.old_bytes - self.new_bytes)


def plan_file(path, rules=None) -> FilePlan:
    rules = dict(DEFAULT_RULES, **(rules or {}))
    result = FilePlan(path)
    try:
        ytd = YtdFile.open(path)
    except YtdError as exc:
        result.error = str(exc)
        return result

    for entry in ytd.textures:
        if not entry.editable:
            continue
        reasons = []
        width, height = _target_size(entry.width, entry.height,
                                     rules["max_size"], rules["min_size"])
        if (width, height) != (entry.width, entry.height):
            reasons.append("تصغير %d→%d" % (max(entry.width, entry.height),
                                            max(width, height)))

        fmt = entry.format
        if rules["opaque_to_dxt1"] and fmt in CONVERTIBLE:
            try:
                if not uses_alpha(ytd, entry):
                    fmt = tex.FMT_DXT1
                    reasons.append("%s→DXT1" % tex.format_name(entry.format)
                                   .split(" ")[0])
            except Exception:
                pass

        if (width, height) == (entry.width, entry.height):
            levels = entry.levels
        else:
            levels = min(entry.levels, _natural_levels(width, height))
        result.textures.append(
            TexturePlan(entry, width, height, fmt, levels, reasons))

    return result


def scan(folder, rules=None, progress=None):
    plans = []
    targets = []
    for root, _dirs, names in os.walk(folder):
        for name in names:
            if name.lower().endswith(".ytd"):
                targets.append(os.path.join(root, name))
    targets.sort()

    for index, path in enumerate(targets):
        if progress is not None and not progress(index, len(targets), path):
            break
        plans.append(plan_file(path, rules))
    return plans


def _resize(image, width, height):
    if image.shape[1] == width and image.shape[0] == height:
        return image
    from PIL import Image
    surface = Image.fromarray(image, "RGBA")
    surface = surface.resize((width, height), Image.LANCZOS)
    return np.array(surface, dtype=np.uint8)


def rebuild(file_plan: FilePlan, out_path) -> int:
    ytd = YtdFile.open(file_plan.path)
    by_index = {t.index: t for t in ytd.textures}
    specs = []

    for item in file_plan.textures:
        entry = by_index.get(item.entry.index)
        if entry is None:
            continue
        unchanged = (not item.changed
                     and item.format == entry.format
                     and item.levels == entry.levels
                     and (item.width, item.height) == (entry.width,
                                                       entry.height))
        if unchanged:
            specs.append(writer.TextureSpec.from_raw(
                entry.name, ytd.raw_data(entry), entry.width, entry.height,
                entry.format, entry.levels))
            continue
        image = ytd.decode(entry)
        image = _resize(image, item.width, item.height)
        specs.append(writer.TextureSpec(entry.name, image, item.format,
                                        item.levels))

    if not specs:
        raise writer.WriteError("لا توجد تكستشرات قابلة للكتابة في %s"
                                % file_plan.name)
    return writer.write(specs, out_path)


def apply(plans, source_root, out_root, progress=None, only_changed=True):
    written, skipped, failed = [], [], []
    total = len(plans)

    for index, file_plan in enumerate(plans):
        if progress is not None and not progress(index, total, file_plan.name):
            break
        if file_plan.error:
            failed.append((file_plan.name, file_plan.error))
            continue

        relative = os.path.relpath(file_plan.path, source_root)
        target = os.path.join(out_root, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)

        if only_changed and not file_plan.changed:
            import shutil
            shutil.copy2(file_plan.path, target)
            skipped.append(file_plan.name)
            continue

        try:
            size = rebuild(file_plan, target)
            written.append((file_plan.name, file_plan.file_size, size))
        except Exception as exc:
            failed.append((file_plan.name, str(exc)))

    return written, skipped, failed


def summary(plans):
    changed = [p for p in plans if p.changed and not p.error]
    return {
        "files": len(plans),
        "readable": sum(1 for p in plans if not p.error),
        "changed": len(changed),
        "errors": sum(1 for p in plans if p.error),
        "old_bytes": sum(p.old_bytes for p in plans if not p.error),
        "new_bytes": sum(p.new_bytes for p in plans if not p.error),
        "saved": sum(p.saved for p in plans if not p.error),
        "downscaled": sum(1 for p in plans for t in p.textures
                          if any("تصغير" in r for r in t.reasons)),
        "reformatted": sum(1 for p in plans for t in p.textures
                           if any("DXT1" in r for r in t.reasons)),
    }

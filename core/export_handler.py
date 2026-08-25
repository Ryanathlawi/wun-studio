"""
Export / rebuild orchestration.

Applies pending edits to a loaded YtdFile, verifies the result, and writes a
new .ytd. Also handles single-texture PNG/DDS export and image import.
"""

from __future__ import annotations

import os
import struct

import numpy as np

from . import texture_handler as tex
from .ytd_handler import YtdError, YtdFile


class ExportError(Exception):
    """Raised when an export cannot be completed."""


def save_ytd_as(ytd: YtdFile, edits, out_path, allow_overwrite_source=False):
    """
    Write a new .ytd containing `edits`.

    `edits` maps a texture index to an RGBA numpy array. Only those textures
    are re-encoded; everything else in the resource is carried over untouched.

    Refuses to overwrite the file the dictionary was loaded from unless the
    caller explicitly opted in.
    """
    if ytd.path and not allow_overwrite_source:
        try:
            same = os.path.exists(out_path) and os.path.samefile(ytd.path, out_path)
        except OSError:
            same = os.path.abspath(ytd.path).lower() == os.path.abspath(out_path).lower()
        if same:
            raise ExportError(
                "That is the original file.\n\n"
                "Choose a different name, or confirm that you want to "
                "overwrite the source .ytd.")

    by_index = {t.index: t for t in ytd.textures}
    applied = []
    problems = []

    for index, image in edits.items():
        entry = by_index.get(index)
        if entry is None:
            problems.append("Texture #%d no longer exists in the dictionary." % index)
            continue
        try:
            ytd.replace(entry, image)
            applied.append(entry.name)
        except YtdError as exc:
            problems.append(str(exc))

    if problems and not applied:
        raise ExportError("No textures could be written:\n\n" + "\n\n".join(problems))

    try:
        ytd.verify()
    except YtdError as exc:
        raise ExportError(str(exc)) from exc

    tmp = out_path + ".tmp"
    try:
        ytd.save(tmp)
        if os.path.exists(out_path):
            os.remove(out_path)
        os.replace(tmp, out_path)
    except (OSError, YtdError) as exc:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise ExportError("Could not write '%s':\n%s" % (out_path, exc)) from exc

    return applied, problems


# --------------------------------------------------------------------------
# Single-texture export
# --------------------------------------------------------------------------

def export_png(image, path):
    """Save an RGBA array as a PNG."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ExportError("Exporting PNG requires Pillow (pip install Pillow)") from exc
    try:
        Image.fromarray(np.ascontiguousarray(image, dtype=np.uint8), "RGBA").save(path)
    except Exception as exc:
        raise ExportError("Could not write '%s':\n%s" % (path, exc)) from exc


_DDS_FOURCC = {
    tex.FMT_DXT1: b"DXT1",
    tex.FMT_DXT3: b"DXT3",
    tex.FMT_DXT5: b"DXT5",
    tex.FMT_ATI1: b"ATI1",
    tex.FMT_ATI2: b"ATI2",
    tex.FMT_BC7: b"DX10",
}


def export_dds(entry, raw, path):
    """
    Write a texture's raw surface data out as a standalone .dds file.

    Useful for round-tripping through an external editor; the pixel bytes are
    copied verbatim from the .ytd, so nothing is re-compressed.
    """
    fourcc = _DDS_FOURCC.get(entry.format)
    if fourcc is None:
        raise ExportError(
            "DDS export is only available for block-compressed textures.\n"
            "'%s' is %s - export it as PNG instead."
            % (entry.name, entry.format_name))

    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    if entry.levels > 1:
        flags |= 0x20000
    caps = 0x1000 | (0x400008 if entry.levels > 1 else 0)

    hdr = bytearray(b"DDS ")
    hdr += struct.pack("<7I", 124, flags, entry.height, entry.width,
                       tex.level_size(entry.format, entry.width, entry.height),
                       0, max(1, entry.levels))
    hdr += b"\x00" * 44
    hdr += struct.pack("<2I", 32, 0x4)
    hdr += fourcc
    hdr += struct.pack("<5I", 0, 0, 0, 0, 0)
    hdr += struct.pack("<5I", caps, 0, 0, 0, 0)
    if fourcc == b"DX10":
        hdr += struct.pack("<5I", 98, 3, 0, 1, 0)   # DXGI_FORMAT_BC7_UNORM

    try:
        with open(path, "wb") as fh:
            fh.write(bytes(hdr))
            fh.write(raw)
    except OSError as exc:
        raise ExportError("Could not write '%s':\n%s" % (path, exc)) from exc


def load_image(path):
    """Load any image file into an RGBA numpy array."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ExportError("Importing images requires Pillow "
                          "(pip install Pillow)") from exc
    try:
        with Image.open(path) as im:
            return np.array(im.convert("RGBA"), dtype=np.uint8)
    except Exception as exc:
        raise ExportError("Could not read '%s':\n%s" % (path, exc)) from exc

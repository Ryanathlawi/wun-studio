from __future__ import annotations

import struct
import zlib

import numpy as np

from . import texture_handler as tex
from .rsc7 import RSC7_MAGIC, size_from_flags

YTD_VERSION = 13

DICT_VFT = 0x650890B2
TEXTURE_VFT = 0xB6F0EE97
TEXTURE_UNKNOWN_30 = 0x00800001
TEXTURE_UNKNOWN_40 = 0x20016001

SYSTEM_BASE = 0x50000000
GRAPHICS_BASE = 0x60000000

SYSTEM_HIGH_BITS = 0x00000000
GRAPHICS_HIGH_BITS = 0xD0000000

TEX_STRUCT_SIZE = 0x90
DICT_SIZE = 0x40
PAGES_INFO_SIZE = 0x10

MAX_PAGE_SHIFT = 15
PAGE_MULTIPLIERS = ((8, 1, 256), (7, 3, 128), (6, 15, 64),
                    (5, 63, 32), (4, 127, 16),
                    (3, 1, 8), (2, 1, 4), (1, 1, 2), (0, 1, 1))
BIT_POSITION = {0: 27, 1: 26, 2: 25, 3: 24, 4: 17, 5: 11, 6: 7, 7: 5, 8: 4}


class WriteError(Exception):
    pass


def joaat(text: str) -> int:
    value = 0
    for char in text.lower():
        value = (value + ord(char)) & 0xFFFFFFFF
        value = (value + (value << 10)) & 0xFFFFFFFF
        value ^= value >> 6
    value = (value + (value << 3)) & 0xFFFFFFFF
    value ^= value >> 11
    return (value + (value << 15)) & 0xFFFFFFFF


def _align(value, boundary=16):
    return (value + boundary - 1) & ~(boundary - 1)


def _encode_pages(pages):
    bits = 0
    remaining = pages
    for index, limit, multiplier in PAGE_MULTIPLIERS:
        count = min(limit, remaining // multiplier)
        if count:
            bits |= count << BIT_POSITION[index]
            remaining -= count * multiplier
    if remaining:
        return None
    return bits


def flags_from_size(size, high_bits=0):
    for shift in range(MAX_PAGE_SHIFT + 1):
        base = 0x200 << shift
        allocated = base * 16
        if size <= allocated:
            bits = _encode_pages(16)
            return high_bits | bits | shift, allocated

    for shift in range(MAX_PAGE_SHIFT + 1):
        base = 0x200 << shift
        pages = -(-size // base)
        bits = _encode_pages(pages)
        if bits is not None:
            return high_bits | bits | shift, base * pages

    raise WriteError("الحجم %d أكبر من أن يُمثَّل في أعلام RSC7" % size)


class TextureSpec:

    def __init__(self, name, image, fmt=tex.FMT_DXT5, levels=None):
        image = np.ascontiguousarray(image, dtype=np.uint8)
        if image.ndim != 3 or image.shape[2] != 4:
            raise WriteError("التكستشر '%s' يجب أن يكون RGBA بشكل (h, w, 4)"
                             % name)
        if not tex.is_supported(fmt):
            raise WriteError("الصيغة %s غير مدعومة للكتابة"
                             % tex.format_name(fmt))

        self.name = name
        self.image = image
        self.format = fmt
        self.width = image.shape[1]
        self.height = image.shape[0]
        self.levels = levels if levels else self.natural_levels()
        self.data = tex.encode_mip_chain(fmt, image, self.levels)
        self.hash = joaat(name)

    @classmethod
    def from_raw(cls, name, data, width, height, fmt, levels):
        expected = tex.total_size(fmt, width, height, levels)
        if len(data) != expected:
            raise WriteError("حجم البيانات الخام لـ '%s' لا يطابق المتوقع "
                             "(%d مقابل %d)" % (name, len(data), expected))
        spec = cls.__new__(cls)
        spec.name = name
        spec.image = None
        spec.format = fmt
        spec.width = width
        spec.height = height
        spec.levels = levels
        spec.data = bytes(data)
        spec.hash = joaat(name)
        return spec

    def natural_levels(self):
        count = 1
        width, height = self.width, self.height
        while width > 4 and height > 4:
            width = max(1, width >> 1)
            height = max(1, height >> 1)
            count += 1
        return count

    @property
    def stride(self):
        if self.format in tex.BLOCK_BYTES:
            return max(1, (self.width + 3) // 4) * tex.BLOCK_BYTES[self.format]
        bits = tex.UNCOMPRESSED_BPP[self.format]
        return (self.width * bits + 7) // 8


def build(specs, version=YTD_VERSION) -> bytes:
    if not specs:
        raise WriteError("لا يمكن بناء قاموس بلا تكستشرات")
    if len(specs) > 0xFFFF:
        raise WriteError("عدد التكستشرات يتجاوز الحد")

    ordered = sorted(specs, key=lambda spec: spec.hash)
    seen = set()
    for spec in ordered:
        if spec.hash in seen:
            raise WriteError("اسمان يعطيان نفس الـ hash: %s" % spec.name)
        seen.add(spec.hash)

    count = len(ordered)

    struct_offsets = []
    cursor = DICT_SIZE
    for _spec in ordered:
        struct_offsets.append(cursor)
        cursor += TEX_STRUCT_SIZE

    cursor = _align(cursor)
    pages_info_offset = cursor
    cursor += PAGES_INFO_SIZE

    cursor = _align(cursor)
    name_offsets = []
    for spec in ordered:
        name_offsets.append(cursor)
        cursor += len(spec.name.encode("utf-8")) + 1
        cursor = _align(cursor)

    pointer_array_offset = cursor
    cursor += count * 8
    cursor = _align(cursor)

    hash_array_offset = cursor
    cursor += count * 4
    system_used = _align(cursor)

    data_offsets = []
    cursor = 0
    for spec in ordered:
        data_offsets.append(cursor)
        cursor += len(spec.data)
        cursor = _align(cursor)
    graphics_used = max(cursor, 16)

    system_flags, system_size = flags_from_size(system_used, SYSTEM_HIGH_BITS)
    graphics_flags, graphics_size = flags_from_size(graphics_used,
                                                    GRAPHICS_HIGH_BITS)

    system = bytearray(system_size)
    graphics = bytearray(graphics_size)

    struct.pack_into("<I", system, 0x00, DICT_VFT)
    struct.pack_into("<Q", system, 0x08, SYSTEM_BASE | pages_info_offset)
    struct.pack_into("<I", system, 0x18, 1)
    struct.pack_into("<Q", system, 0x20, SYSTEM_BASE | hash_array_offset)
    struct.pack_into("<HH", system, 0x28, count, count)
    struct.pack_into("<Q", system, 0x30, SYSTEM_BASE | pointer_array_offset)
    struct.pack_into("<HH", system, 0x38, count, count)

    system[pages_info_offset + 0x08] = 1
    system[pages_info_offset + 0x09] = 1

    for index, spec in enumerate(ordered):
        offset = struct_offsets[index]
        struct.pack_into("<I", system, offset + 0x00, TEXTURE_VFT)
        struct.pack_into("<Q", system, offset + 0x28,
                         SYSTEM_BASE | name_offsets[index])
        struct.pack_into("<I", system, offset + 0x30, TEXTURE_UNKNOWN_30)
        struct.pack_into("<I", system, offset + 0x40, TEXTURE_UNKNOWN_40)
        struct.pack_into("<HHHH", system, offset + 0x50,
                         spec.width, spec.height, 1, spec.stride)
        struct.pack_into("<I", system, offset + 0x58, spec.format)
        system[offset + 0x5D] = spec.levels
        struct.pack_into("<Q", system, offset + 0x70,
                         GRAPHICS_BASE | data_offsets[index])

        encoded = spec.name.encode("utf-8")
        start = name_offsets[index]
        system[start:start + len(encoded)] = encoded

        struct.pack_into("<Q", system, pointer_array_offset + index * 8,
                         SYSTEM_BASE | offset)
        struct.pack_into("<I", system, hash_array_offset + index * 4,
                         spec.hash)

        start = data_offsets[index]
        graphics[start:start + len(spec.data)] = spec.data

    body = bytes(system) + bytes(graphics)
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    payload = compressor.compress(body) + compressor.flush()
    header = struct.pack("<IIII", RSC7_MAGIC, version,
                         system_flags, graphics_flags)
    return header + payload


def write(specs, path, version=YTD_VERSION):
    data = build(specs, version)
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
        import os
        if os.path.exists(path):
            os.remove(path)
        os.replace(tmp, path)
    except OSError as exc:
        import os
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise WriteError("تعذّرت كتابة '%s':\n%s" % (path, exc)) from exc
    return len(data)


def from_images(named_images, fmt=tex.FMT_DXT5, levels=None):
    return [TextureSpec(name, image, fmt, levels)
            for name, image in named_images]

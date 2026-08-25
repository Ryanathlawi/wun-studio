"""
GTA V texture format decoding / encoding.

--------------------------------------------------------------------------
YTD-SPECIFIC LOGIC
--------------------------------------------------------------------------
Textures inside a .ytd are stored as raw, header-less surface data using
legacy D3D9 format codes (see the FMT_* constants below). The pixel bytes
for every mip level are packed back-to-back:

    level 0 (w x h), level 1 (w/2 x h/2), ... level N

There is no DDS header and no per-level offset table - the game recomputes
the layout from width/height/format/levels, so we must do exactly the same.

Everything here is implemented with NumPy so that a full mip chain can be
re-encoded quickly, and so that an edited texture always produces the *exact
same number of bytes* as the original. That byte-size equality is what makes
safe in-place patching possible.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import struct

import numpy as np


class TextureFormatError(Exception):
    """Raised for texture formats we cannot decode or re-encode."""


# --------------------------------------------------------------------------
# Format codes (D3DFORMAT values, as used by RAGE / CodeWalker)
# --------------------------------------------------------------------------

FMT_A8R8G8B8 = 21
FMT_X8R8G8B8 = 22
FMT_A1R5G5B5 = 25
FMT_A8 = 28
FMT_A8B8G8R8 = 32
FMT_L8 = 50
FMT_DXT1 = 0x31545844   # 'DXT1'
FMT_DXT3 = 0x33545844   # 'DXT3'
FMT_DXT5 = 0x35545844   # 'DXT5'
FMT_ATI1 = 0x31495441   # 'ATI1' == BC4
FMT_ATI2 = 0x32495441   # 'ATI2' == BC5
FMT_BC7 = 0x20374342    # 'BC7 '

FORMAT_NAMES = {
    FMT_A8R8G8B8: "A8R8G8B8",
    FMT_X8R8G8B8: "X8R8G8B8",
    FMT_A1R5G5B5: "A1R5G5B5",
    FMT_A8: "A8",
    FMT_A8B8G8R8: "A8B8G8R8",
    FMT_L8: "L8",
    FMT_DXT1: "DXT1 (BC1)",
    FMT_DXT3: "DXT3 (BC2)",
    FMT_DXT5: "DXT5 (BC3)",
    FMT_ATI1: "ATI1 (BC4)",
    FMT_ATI2: "ATI2 (BC5)",
    FMT_BC7: "BC7",
}

# bytes per 4x4 block for the block-compressed formats
BLOCK_BYTES = {
    FMT_DXT1: 8, FMT_ATI1: 8,
    FMT_DXT3: 16, FMT_DXT5: 16, FMT_ATI2: 16, FMT_BC7: 16,
}

# bits per pixel for the uncompressed formats
UNCOMPRESSED_BPP = {
    FMT_A8R8G8B8: 32, FMT_X8R8G8B8: 32, FMT_A8B8G8R8: 32,
    FMT_A1R5G5B5: 16, FMT_A8: 8, FMT_L8: 8,
}


def format_name(fmt: int) -> str:
    return FORMAT_NAMES.get(fmt, "Unknown (0x%08X)" % fmt)


def is_supported(fmt: int) -> bool:
    return fmt in BLOCK_BYTES or fmt in UNCOMPRESSED_BPP


def level_size(fmt: int, width: int, height: int) -> int:
    """Byte size of a single mip level - must match the game's own maths."""
    width = max(1, width)
    height = max(1, height)
    if fmt in BLOCK_BYTES:
        bw = max(1, (width + 3) // 4)
        bh = max(1, (height + 3) // 4)
        return bw * bh * BLOCK_BYTES[fmt]
    if fmt in UNCOMPRESSED_BPP:
        return (width * height * UNCOMPRESSED_BPP[fmt] + 7) // 8
    raise TextureFormatError("Cannot size unsupported format " + format_name(fmt))


def total_size(fmt: int, width: int, height: int, levels: int) -> int:
    """Byte size of a full mip chain."""
    total = 0
    for i in range(max(1, levels)):
        total += level_size(fmt, max(1, width >> i), max(1, height >> i))
    return total


# --------------------------------------------------------------------------
# Block <-> image helpers
# --------------------------------------------------------------------------

def _blocks_to_image(blocks: np.ndarray, bw: int, bh: int,
                     width: int, height: int) -> np.ndarray:
    """(nblocks, 16, 4) -> (height, width, 4), cropping the 4x4 padding."""
    img = blocks.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4)
    img = img.reshape(bh * 4, bw * 4, 4)
    return np.ascontiguousarray(img[:height, :width])


def _image_to_blocks(img: np.ndarray):
    """(h, w, 4) -> ((nblocks, 16, 4), bw, bh), edge-padding to a 4x4 grid."""
    h, w = img.shape[:2]
    bw = max(1, (w + 3) // 4)
    bh = max(1, (h + 3) // 4)
    padded = np.zeros((bh * 4, bw * 4, 4), dtype=np.uint8)
    padded[:h, :w] = img
    # replicate edges so padding does not drag block colours toward black
    if bw * 4 > w:
        padded[:h, w:] = img[:, w - 1:w]
    if bh * 4 > h:
        padded[h:, :] = padded[h - 1:h, :]
    blocks = padded.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4)
    return np.ascontiguousarray(blocks).reshape(bh * bw, 16, 4), bw, bh


def _expand565(c: np.ndarray) -> np.ndarray:
    """uint16 RGB565 -> (n, 3) uint8, with proper bit replication."""
    c = c.astype(np.uint16)
    r = ((c >> 11) & 0x1F).astype(np.uint16)
    g = ((c >> 5) & 0x3F).astype(np.uint16)
    b = (c & 0x1F).astype(np.uint16)
    r = (r << 3) | (r >> 2)
    g = (g << 2) | (g >> 4)
    b = (b << 3) | (b >> 2)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def _pack565(rgb: np.ndarray) -> np.ndarray:
    """(n, 3) uint8 -> uint16 RGB565."""
    rgb = rgb.astype(np.int32)
    r = (rgb[..., 0] * 31 + 127) // 255
    g = (rgb[..., 1] * 63 + 127) // 255
    b = (rgb[..., 2] * 31 + 127) // 255
    return ((r << 11) | (g << 5) | b).astype(np.uint16)


def _pack_bits(nblocks: int, fields) -> np.ndarray:
    """
    Pack LSB-first bitfields into bytes.

    `fields` is an ordered list of (values, bit_count); values may be shaped
    (nblocks,) or (nblocks, k) for k consecutive same-width fields.
    Returns (nblocks, total_bits // 8) uint8.
    """
    planes = []
    for values, nbits in fields:
        v = np.asarray(values).astype(np.uint64)
        if v.ndim == 1:
            v = v[:, None]
        shifts = np.arange(nbits, dtype=np.uint64)
        bits = ((v[..., None] >> shifts) & np.uint64(1)).astype(np.uint8)
        planes.append(bits.reshape(nblocks, -1))
    allbits = np.concatenate(planes, axis=1)
    # LSB-first within each byte -> reverse each group of 8 before packbits
    allbits = allbits.reshape(nblocks, -1, 8)[:, :, ::-1]
    return np.packbits(np.ascontiguousarray(allbits).reshape(nblocks, -1), axis=1)


def _unpack_le(data: np.ndarray, count: int) -> np.ndarray:
    """Combine `count` little-endian bytes per row into one uint64 column."""
    out = np.zeros(data.shape[0], dtype=np.uint64)
    for i in range(count):
        out |= data[:, i].astype(np.uint64) << np.uint64(8 * i)
    return out


# --------------------------------------------------------------------------
# Decoders
# --------------------------------------------------------------------------

def _decode_bc1_colour(d: np.ndarray, punchthrough: bool) -> np.ndarray:
    """Shared BC1 colour block decode -> (nblocks, 16, 4) uint8."""
    n = d.shape[0]
    c0 = _unpack_le(d[:, 0:2], 2).astype(np.uint16)
    c1 = _unpack_le(d[:, 2:4], 2).astype(np.uint16)
    bits = _unpack_le(d[:, 4:8], 4)

    p0 = _expand565(c0).astype(np.int32)
    p1 = _expand565(c1).astype(np.int32)

    pal = np.zeros((n, 4, 3), dtype=np.int32)
    pal[:, 0] = p0
    pal[:, 1] = p1
    alpha = np.full((n, 4), 255, dtype=np.uint8)

    four = (c0 > c1) if punchthrough else np.ones(n, dtype=bool)
    three = ~four
    pal[four, 2] = (2 * p0[four] + p1[four]) // 3
    pal[four, 3] = (p0[four] + 2 * p1[four]) // 3
    pal[three, 2] = (p0[three] + p1[three]) // 2
    pal[three, 3] = 0
    alpha[three, 3] = 0

    shifts = (2 * np.arange(16)).astype(np.uint64)
    idx = ((bits[:, None] >> shifts) & np.uint64(3)).astype(np.intp)

    rows = np.arange(n)[:, None]
    rgb = pal[rows, idx].astype(np.uint8)
    a = alpha[rows, idx]
    return np.concatenate([rgb, a[..., None]], axis=-1)


def _decode_bc4_block(d: np.ndarray) -> np.ndarray:
    """BC4 / DXT5-alpha 8-byte blocks -> (nblocks, 16) uint8."""
    n = d.shape[0]
    a0 = d[:, 0].astype(np.int32)
    a1 = d[:, 1].astype(np.int32)
    bits = _unpack_le(d[:, 2:8], 6)

    pal = np.zeros((n, 8), dtype=np.int32)
    pal[:, 0] = a0
    pal[:, 1] = a1
    eight = a0 > a1
    six = ~eight
    for i in range(1, 7):
        pal[eight, i + 1] = ((7 - i) * a0[eight] + i * a1[eight]) // 7
    for i in range(1, 5):
        pal[six, i + 1] = ((5 - i) * a0[six] + i * a1[six]) // 5
    pal[six, 6] = 0
    pal[six, 7] = 255

    shifts = (3 * np.arange(16)).astype(np.uint64)
    idx = ((bits[:, None] >> shifts) & np.uint64(7)).astype(np.intp)
    return pal[np.arange(n)[:, None], idx].astype(np.uint8)


def _decode_block_format(fmt: int, data: bytes, width: int, height: int) -> np.ndarray:
    bw = max(1, (width + 3) // 4)
    bh = max(1, (height + 3) // 4)
    bsize = BLOCK_BYTES[fmt]
    need = bw * bh * bsize
    if len(data) < need:
        data = bytes(data) + b"\x00" * (need - len(data))
    d = np.frombuffer(data[:need], dtype=np.uint8).reshape(bw * bh, bsize)

    if fmt == FMT_DXT1:
        px = _decode_bc1_colour(d, punchthrough=True)
    elif fmt == FMT_DXT3:
        px = _decode_bc1_colour(d[:, 8:16], punchthrough=False)
        abits = _unpack_le(d[:, 0:8], 8)
        shifts = (4 * np.arange(16)).astype(np.uint64)
        a4 = ((abits[:, None] >> shifts) & np.uint64(0xF)).astype(np.uint8)
        px[..., 3] = (a4 << 4) | a4
    elif fmt == FMT_DXT5:
        px = _decode_bc1_colour(d[:, 8:16], punchthrough=False)
        px[..., 3] = _decode_bc4_block(d[:, 0:8])
    elif fmt == FMT_ATI1:
        r = _decode_bc4_block(d)
        px = np.empty((d.shape[0], 16, 4), dtype=np.uint8)
        px[..., 0] = r
        px[..., 1] = r
        px[..., 2] = r
        px[..., 3] = 255
    elif fmt == FMT_ATI2:
        r = _decode_bc4_block(d[:, 0:8])
        g = _decode_bc4_block(d[:, 8:16])
        px = np.zeros((d.shape[0], 16, 4), dtype=np.uint8)
        px[..., 0] = r
        px[..., 1] = g
        px[..., 2] = 255
        px[..., 3] = 255
    else:
        raise TextureFormatError("No decoder for " + format_name(fmt))

    return _blocks_to_image(px, bw, bh, width, height)


# ---- BC7 decode: delegated to Pillow via a synthetic DX10 DDS header -------

def _dds_header(fourcc: bytes, width: int, height: int, linear_size: int,
                dxgi=None) -> bytes:
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    hdr = bytearray(b"DDS ")
    hdr += struct.pack("<7I", 124, flags, height, width, linear_size, 0, 1)
    hdr += b"\x00" * 44                                   # reserved[11]
    hdr += struct.pack("<2I", 32, 0x4)                    # pixelformat, FOURCC
    hdr += fourcc
    hdr += struct.pack("<5I", 0, 0, 0, 0, 0)              # bit counts / masks
    hdr += struct.pack("<5I", 0x1000, 0, 0, 0, 0)         # caps
    if dxgi is not None:
        hdr += struct.pack("<5I", dxgi, 3, 0, 1, 0)       # DDS_HEADER_DXT10
    return bytes(hdr)


def _decode_bc7(data: bytes, width: int, height: int) -> np.ndarray:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise TextureFormatError(
            "Decoding BC7 textures requires Pillow. Install it with:\n"
            "    pip install Pillow"
        ) from exc

    need = level_size(FMT_BC7, width, height)
    payload = bytes(data[:need]).ljust(need, b"\x00")
    blob = _dds_header(b"DX10", width, height, need, dxgi=98) + payload
    try:
        with Image.open(io.BytesIO(blob)) as im:
            return np.array(im.convert("RGBA"), dtype=np.uint8)
    except Exception as exc:
        raise TextureFormatError(
            "Failed to decode a BC7 texture. Your Pillow version may be too "
            "old - BC7 support needs Pillow 9.4 or newer.\n"
            "Underlying error: " + str(exc)
        ) from exc


def _decode_uncompressed(fmt: int, data: bytes, width: int, height: int) -> np.ndarray:
    need = level_size(fmt, width, height)
    data = bytes(data[:need]).ljust(need, b"\x00")
    out = np.zeros((height, width, 4), dtype=np.uint8)

    if fmt in (FMT_A8R8G8B8, FMT_X8R8G8B8, FMT_A8B8G8R8):
        raw = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 4)
        if fmt == FMT_A8B8G8R8:
            out[:] = raw                       # RGBA in memory
        else:
            out[..., 0] = raw[..., 2]          # BGRA in memory
            out[..., 1] = raw[..., 1]
            out[..., 2] = raw[..., 0]
            out[..., 3] = raw[..., 3] if fmt == FMT_A8R8G8B8 else 255
    elif fmt == FMT_L8:
        raw = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
        out[..., 0] = raw
        out[..., 1] = raw
        out[..., 2] = raw
        out[..., 3] = 255
    elif fmt == FMT_A8:
        raw = np.frombuffer(data, dtype=np.uint8).reshape(height, width)
        out[..., 0] = 255
        out[..., 1] = 255
        out[..., 2] = 255
        out[..., 3] = raw
    elif fmt == FMT_A1R5G5B5:
        raw = np.frombuffer(data, dtype="<u2").reshape(height, width).astype(np.uint32)
        r = (raw >> 10) & 0x1F
        g = (raw >> 5) & 0x1F
        b = raw & 0x1F
        out[..., 0] = ((r << 3) | (r >> 2)).astype(np.uint8)
        out[..., 1] = ((g << 3) | (g >> 2)).astype(np.uint8)
        out[..., 2] = ((b << 3) | (b >> 2)).astype(np.uint8)
        out[..., 3] = np.where((raw >> 15) & 1, 255, 0).astype(np.uint8)
    else:
        raise TextureFormatError("No decoder for " + format_name(fmt))
    return out


def decode_preview(fmt: int, data: bytes, width: int, height: int,
                   max_size: int) -> np.ndarray:
    """
    Decode a cheap, small preview of a surface.

    For block-compressed formats we keep only every Nth 4x4 block instead of
    decoding the whole surface. Textures without a mip chain are often huge
    (map tiles are commonly 3072x3072 with a single level), and decoding one
    in full just to draw a 56px list icon is wasted work.
    """
    if fmt in BLOCK_BYTES and max(width, height) > max_size:
        bw = max(1, (width + 3) // 4)
        bh = max(1, (height + 3) // 4)
        bsize = BLOCK_BYTES[fmt]
        need = bw * bh * bsize
        if len(data) >= need:
            step = max(1, int(max(width, height) / max(1, max_size)))
            d = np.frombuffer(data[:need], dtype=np.uint8).reshape(bh, bw, bsize)
            sub = np.ascontiguousarray(d[::step, ::step])
            nbh, nbw = sub.shape[0], sub.shape[1]
            return decode_surface(fmt, sub.tobytes(), nbw * 4, nbh * 4)
    return decode_surface(fmt, data, width, height)


def decode_surface(fmt: int, data: bytes, width: int, height: int) -> np.ndarray:
    """Decode one mip level into an (h, w, 4) RGBA uint8 array."""
    if fmt == FMT_BC7:
        return _decode_bc7(data, width, height)
    if fmt in BLOCK_BYTES:
        return _decode_block_format(fmt, data, width, height)
    if fmt in UNCOMPRESSED_BPP:
        return _decode_uncompressed(fmt, data, width, height)
    raise TextureFormatError(
        "Unsupported texture format: " + format_name(fmt) + ".\n"
        "This texture cannot be displayed or edited."
    )


# --------------------------------------------------------------------------
# Encoders
# --------------------------------------------------------------------------

def _encode_bc1_colour(blocks: np.ndarray, allow_punchthrough: bool) -> np.ndarray:
    """(nblocks, 16, 4) -> (nblocks, 8) uint8 BC1 colour blocks."""
    n = blocks.shape[0]
    rgb = blocks[..., :3].astype(np.int32)
    alpha = blocks[..., 3]

    transparent = alpha < 128
    has_alpha = transparent.any(axis=1) & bool(allow_punchthrough)
    opaque_px = ~transparent

    # bounding box over the *opaque* pixels only (fall back to all pixels)
    safe = np.where(opaque_px.any(axis=1)[:, None], opaque_px, True)
    big = np.where(safe[..., None], rgb, 255)
    small = np.where(safe[..., None], rgb, 0)
    mn = big.min(axis=1)
    mx = small.max(axis=1)

    c_hi = _pack565(mx).astype(np.int32)
    c_lo = _pack565(mn).astype(np.int32)

    # 4-colour mode needs c0 > c1; 3-colour (punch-through) needs c0 <= c1
    c0 = np.where(has_alpha, np.minimum(c_hi, c_lo), np.maximum(c_hi, c_lo))
    c1 = np.where(has_alpha, np.maximum(c_hi, c_lo), np.minimum(c_hi, c_lo))

    p0 = _expand565(c0.astype(np.uint16)).astype(np.int32)
    p1 = _expand565(c1.astype(np.uint16)).astype(np.int32)

    pal = np.zeros((n, 4, 3), dtype=np.int32)
    pal[:, 0] = p0
    pal[:, 1] = p1
    four = ~has_alpha
    pal[four, 2] = (2 * p0[four] + p1[four]) // 3
    pal[four, 3] = (p0[four] + 2 * p1[four]) // 3
    pal[has_alpha, 2] = (p0[has_alpha] + p1[has_alpha]) // 2
    pal[has_alpha, 3] = 0

    # pick the closest palette entry for every pixel
    diff = rgb[:, :, None, :] - pal[:, None, :, :]
    dist = (diff * diff).sum(axis=-1)
    if allow_punchthrough:
        # index 3 is reserved for transparency in 3-colour blocks
        dist[has_alpha, :, 3] = np.iinfo(np.int32).max
    idx = dist.argmin(axis=-1).astype(np.uint64)

    # A degenerate block (c0 == c1) always decodes in 3-colour mode, where
    # entry 3 means "transparent". Opaque blocks must therefore avoid it -
    # but blocks that *are* using punch-through still need entry 3, so the
    # guard only applies to the opaque ones.
    degenerate = (c0 == c1) & ~has_alpha
    idx[np.repeat(degenerate[:, None], 16, axis=1)] = 0

    if allow_punchthrough:
        idx[transparent & has_alpha[:, None]] = 3

    return _pack_bits(n, [
        (c0.astype(np.uint64), 16),
        (c1.astype(np.uint64), 16),
        (idx, 2),
    ])


def _encode_bc4_block(values: np.ndarray) -> np.ndarray:
    """(nblocks, 16) uint8 -> (nblocks, 8) uint8 BC4 blocks."""
    n = values.shape[0]
    v = values.astype(np.int32)
    a0 = v.max(axis=1)
    a1 = v.min(axis=1)

    pal = np.zeros((n, 8), dtype=np.int32)
    pal[:, 0] = a0
    pal[:, 1] = a1
    for i in range(1, 7):
        pal[:, i + 1] = ((7 - i) * a0 + i * a1) // 7

    diff = v[:, :, None] - pal[:, None, :]
    idx = (diff * diff).argmin(axis=-1).astype(np.uint64)
    idx[np.repeat((a0 == a1)[:, None], 16, axis=1)] = 0

    return _pack_bits(n, [
        (a0.astype(np.uint64), 8),
        (a1.astype(np.uint64), 8),
        (idx, 3),
    ])


def _encode_bc7_mode6(blocks: np.ndarray) -> np.ndarray:
    """
    (nblocks, 16, 4) -> (nblocks, 16) uint8 BC7 blocks, all using mode 6.

    Mode 6 is the single-subset, full-RGBA, 4-bit-index BC7 mode. It is the
    only BC7 mode that can be encoded reliably without an expensive partition
    search, and it carries alpha natively - which matters because GTA V uses
    BC7 for high-quality textures where losing alpha precision would show.

    Bit layout (LSB first): 7 mode bits (0b1000000), then R0 R1 G0 G1 B0 B1
    A0 A1 as 7 bits each, 2 shared p-bits, then 16 indices (the first is only
    3 bits because the anchor pixel's high bit is implicitly zero).
    """
    n = blocks.shape[0]
    px = blocks.astype(np.int32)

    e0 = px.min(axis=1)          # (n, 4)
    e1 = px.max(axis=1)

    # Mode 6 endpoints are 7 bits plus one p-bit shared by all four channels,
    # so the reconstructed 8-bit value is ((v << 1) | p). Try both p-bits and
    # keep whichever reproduces the endpoint's four channels most closely -
    # a majority-LSB guess costs a level of alpha on fully opaque blocks.
    # Alpha is weighted heavily in that choice so that a fully opaque block
    # reconstructs as exactly 255 rather than 254; one level of RGB is a much
    # cheaper thing to give up than an unexpectedly translucent texture.
    weights = np.array([1, 1, 1, 8], dtype=np.int32)

    def _fit(e):
        best_v = None
        best_p = None
        best_err = None
        for p in (0, 1):
            v = np.clip((e - p + 1) >> 1, 0, 127)
            err = (((v << 1) | p) - e)
            err = (err * err * weights).sum(axis=1)
            if best_err is None:
                best_v, best_p, best_err = v, np.full(e.shape[0], p, np.int32), err
            else:
                take = err < best_err
                best_v = np.where(take[:, None], v, best_v)
                best_p = np.where(take, p, best_p)
                best_err = np.where(take, err, best_err)
        return best_v, best_p.astype(bool)

    v0, p0 = _fit(e0)
    v1, p1 = _fit(e1)
    d0 = (v0 << 1) | p0[:, None].astype(np.int32)
    d1 = (v1 << 1) | p1[:, None].astype(np.int32)

    # project every pixel onto the endpoint line to get a 4-bit index
    axis = (d1 - d0).astype(np.float32)
    denom = (axis * axis).sum(axis=1)
    denom = np.where(denom < 1e-6, 1.0, denom)
    t = ((px - d0[:, None, :]).astype(np.float32)
         * axis[:, None, :]).sum(axis=-1) / denom[:, None]
    idx = np.clip(np.rint(t * 15.0), 0, 15).astype(np.int64)

    # the anchor index (pixel 0) must have its high bit clear; if it does not,
    # swap the endpoints and invert every index
    swap = idx[:, 0] > 7
    if swap.any():
        tmp0 = v0[swap].copy()
        v0[swap] = v1[swap]
        v1[swap] = tmp0
        tp0 = p0[swap].copy()
        p0[swap] = p1[swap]
        p1[swap] = tp0
        idx[swap] = 15 - idx[swap]

    return _pack_bits(n, [
        (np.full(n, 0b1000000, dtype=np.uint64), 7),
        (v0[:, 0].astype(np.uint64), 7), (v1[:, 0].astype(np.uint64), 7),
        (v0[:, 1].astype(np.uint64), 7), (v1[:, 1].astype(np.uint64), 7),
        (v0[:, 2].astype(np.uint64), 7), (v1[:, 2].astype(np.uint64), 7),
        (v0[:, 3].astype(np.uint64), 7), (v1[:, 3].astype(np.uint64), 7),
        (p0.astype(np.uint64), 1), (p1.astype(np.uint64), 1),
        (idx[:, 0].astype(np.uint64), 3),
        (idx[:, 1:].astype(np.uint64), 4),
    ])


def _encode_uncompressed(fmt: int, img: np.ndarray) -> bytes:
    h, w = img.shape[:2]
    if fmt in (FMT_A8R8G8B8, FMT_X8R8G8B8):
        out = np.empty((h, w, 4), dtype=np.uint8)
        out[..., 0] = img[..., 2]
        out[..., 1] = img[..., 1]
        out[..., 2] = img[..., 0]
        out[..., 3] = img[..., 3] if fmt == FMT_A8R8G8B8 else 255
        return out.tobytes()
    if fmt == FMT_A8B8G8R8:
        return np.ascontiguousarray(img).tobytes()
    if fmt == FMT_L8:
        lum = (img[..., :3].astype(np.uint32)
               @ np.array([77, 150, 29], dtype=np.uint32)) >> 8
        return lum.astype(np.uint8).tobytes()
    if fmt == FMT_A8:
        return np.ascontiguousarray(img[..., 3]).tobytes()
    if fmt == FMT_A1R5G5B5:
        c = img.astype(np.uint32)
        r = (c[..., 0] * 31 + 127) // 255
        g = (c[..., 1] * 31 + 127) // 255
        b = (c[..., 2] * 31 + 127) // 255
        a = (c[..., 3] >= 128).astype(np.uint32)
        return ((a << 15) | (r << 10) | (g << 5) | b).astype("<u2").tobytes()
    raise TextureFormatError("No encoder for " + format_name(fmt))


def encode_surface(fmt: int, img: np.ndarray) -> bytes:
    """Encode one RGBA (h, w, 4) uint8 level into raw surface bytes."""
    img = np.ascontiguousarray(img, dtype=np.uint8)
    if fmt in UNCOMPRESSED_BPP:
        return _encode_uncompressed(fmt, img)

    blocks, bw, bh = _image_to_blocks(img)
    if fmt == FMT_DXT1:
        out = _encode_bc1_colour(blocks, allow_punchthrough=True)
    elif fmt == FMT_DXT3:
        colour = _encode_bc1_colour(blocks, allow_punchthrough=False)
        a4 = blocks[..., 3].astype(np.uint64) >> np.uint64(4)
        alpha = _pack_bits(blocks.shape[0], [(a4, 4)])
        out = np.concatenate([alpha, colour], axis=1)
    elif fmt == FMT_DXT5:
        colour = _encode_bc1_colour(blocks, allow_punchthrough=False)
        alpha = _encode_bc4_block(blocks[..., 3])
        out = np.concatenate([alpha, colour], axis=1)
    elif fmt == FMT_ATI1:
        out = _encode_bc4_block(blocks[..., 0])
    elif fmt == FMT_ATI2:
        out = np.concatenate([_encode_bc4_block(blocks[..., 0]),
                              _encode_bc4_block(blocks[..., 1])], axis=1)
    elif fmt == FMT_BC7:
        out = _encode_bc7_mode6(blocks)
    else:
        raise TextureFormatError(
            "Cannot re-encode " + format_name(fmt) + " - the texture would "
            "become invalid. Saving this texture is not supported."
        )

    expected = level_size(fmt, img.shape[1], img.shape[0])
    data = out.tobytes()
    if len(data) != expected:  # pragma: no cover - consistency guard
        raise TextureFormatError(
            "Internal encoder error: produced %d bytes, expected %d for %s."
            % (len(data), expected, format_name(fmt))
        )
    return data


# --------------------------------------------------------------------------
# Mip chain
# --------------------------------------------------------------------------

def downsample(img: np.ndarray) -> np.ndarray:
    """Halve an RGBA image with an alpha-weighted 2x2 box filter."""
    h, w = img.shape[:2]
    nh, nw = max(1, h // 2), max(1, w // 2)
    if h < 2 or w < 2:
        return np.ascontiguousarray(img[:nh, :nw])

    src = img[:nh * 2, :nw * 2].astype(np.float32).reshape(nh, 2, nw, 2, 4)
    a = src[..., 3]
    wsum = a.sum(axis=(1, 3))
    safe = np.where(wsum <= 0, 1.0, wsum)
    rgb = (src[..., :3] * a[..., None]).sum(axis=(1, 3)) / safe[..., None]
    # fully transparent areas keep a plain average so colour does not go black
    plain = src[..., :3].mean(axis=(1, 3))
    rgb = np.where((wsum <= 0)[..., None], plain, rgb)
    out = np.empty((nh, nw, 4), dtype=np.float32)
    out[..., :3] = rgb
    out[..., 3] = a.mean(axis=(1, 3))
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)


def encode_mip_chain(fmt: int, img: np.ndarray, levels: int) -> bytes:
    """
    Encode a full mip chain, matching the original level count exactly.

    Regenerating the mips (instead of keeping the originals) is required: the
    game samples lower mips at distance, so an edit that only touched level 0
    would visibly "pop back" to the unedited artwork further away.
    """
    chunks = []
    current = np.ascontiguousarray(img, dtype=np.uint8)
    for i in range(max(1, levels)):
        if i > 0:
            current = downsample(current)
        chunks.append(encode_surface(fmt, current))
    return b"".join(chunks)

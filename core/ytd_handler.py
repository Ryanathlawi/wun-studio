"""
YTD (texture dictionary) parsing and in-place patching.

--------------------------------------------------------------------------
YTD-SPECIFIC LOGIC
--------------------------------------------------------------------------
A .ytd is an RSC7 resource whose system segment starts with a
`pgDictionary<grcTexture>`. Layout (64-bit, GTA V), verified against
CodeWalker's TextureDictionary.cs:

    TextureDictionary            (0x40 bytes, at system offset 0)
      0x00  u32   FileVFT
      0x04  u32   FileUnknown            (= 1)
      0x08  u64   FilePagesInfoPointer
      0x10  u32 x 4                      unknown / flags
      0x20  u64   TextureNameHashes ptr  (u32 jenkins hashes, sorted)
      0x28  u16   hash count, u16 capacity
      0x30  u64   Textures ptr           (array of u64 texture pointers)
      0x38  u16   texture count, u16 capacity

    grcTexturePC                 (0x90 bytes)   [TextureBase is the first 0x50]
      0x28  u64   NamePointer            -> ASCII texture name
      0x50  u16   Width
      0x52  u16   Height
      0x54  u16   Depth
      0x56  u16   Stride
      0x58  u32   Format                 (D3DFORMAT code)
      0x5D  u8    Levels                 (mip count)
      0x60  u64   DataPointer            -> pixel data in the graphics segment

We deliberately do NOT rebuild the dictionary when saving. Instead we patch
pixel bytes directly inside the decompressed segments. That guarantees:

  * every texture name, hash and pointer stays exactly as Rockstar wrote it
  * untouched textures are preserved byte-for-byte
  * the page/segment layout (and therefore the RSC7 header flags) stays valid

The price is that an edited texture must re-encode to the same byte count,
i.e. same dimensions, same format, same mip count. The editor enforces this.
--------------------------------------------------------------------------
"""

from __future__ import annotations

import struct

import numpy as np

from . import texture_handler as tex
from .rsc7 import GRAPHICS_BASE, SYSTEM_BASE, Rsc7Error, Rsc7Resource

# --- structure offsets ----------------------------------------------------

DICT_HASHES_PTR = 0x20
DICT_HASHES_COUNT = 0x28
DICT_TEXTURES_PTR = 0x30
DICT_TEXTURES_COUNT = 0x38

TEX_NAME_PTR = 0x28
TEX_WIDTH = 0x50
TEX_HEIGHT = 0x52
TEX_DEPTH = 0x54
TEX_STRIDE = 0x56
TEX_FORMAT = 0x58
TEX_LEVELS = 0x5D
# The pixel-data pointer sits at 0x70 in the GTA V build (0x18 past Format).
# Some tool-written dictionaries put it at 0x60 instead, so both are tried and
# then, as a last resort, any graphics-segment pointer in the struct is used.
TEX_DATA_PTR_CANDIDATES = (0x70, 0x60, 0x68, 0x78)
TEX_STRUCT_SIZE = 0x90

MAX_TEXTURES = 8192


class YtdError(Exception):
    """Raised when a .ytd cannot be parsed or patched."""


class TextureEntry:
    """
    One texture inside the dictionary.

    Holds both the parsed description and the physical locations needed to
    patch it back into the resource.
    """

    def __init__(self, index, name, width, height, depth, stride, fmt, levels,
                 struct_offset, data_pointer):
        self.index = index
        self.name = name
        self.width = width
        self.height = height
        self.depth = depth
        self.stride = stride
        self.format = fmt
        self.levels = levels
        self.struct_offset = struct_offset      # offset in the system segment
        self.data_pointer = data_pointer        # raw resource pointer

        self.data_size = 0                      # computed mip-chain size
        self.available = 0                      # bytes we may safely write
        self.error = None                       # why this texture is unusable

    # -- derived -----------------------------------------------------------

    @property
    def format_name(self):
        return tex.format_name(self.format)

    @property
    def editable(self):
        return self.error is None

    def describe(self):
        return "%s  %dx%d  %s  %d mip(s)" % (
            self.name, self.width, self.height, self.format_name, self.levels)


def _looks_like_name(raw):
    """A texture name is short printable ASCII."""
    if not raw:
        return False
    return all(32 <= ord(ch) < 127 for ch in raw)


class YtdFile:
    """
    A loaded .ytd, ready for inspection and patching.

    Typical use:
        ytd = YtdFile.open("mytex.ytd")
        img = ytd.decode(ytd.textures[0])       # -> (h, w, 4) uint8 RGBA
        ytd.replace(ytd.textures[0], edited)    # re-encode + patch in place
        ytd.save("mytex_edited.ytd")
    """

    def __init__(self, resource: Rsc7Resource, path=None):
        self.res = resource
        self.path = path
        self.textures = []
        self._parse()

    # ---------------------------------------------------------------- load

    @classmethod
    def open(cls, path):
        try:
            res = Rsc7Resource.from_file(path)
        except Rsc7Error as exc:
            raise YtdError(str(exc)) from exc
        if res.version not in (13, 0):
            # Version 13 is the .ytd resource version; warn rather than fail,
            # since some tools re-write the field.
            pass
        return cls(res, path)

    # --------------------------------------------------------------- parse

    def _parse(self):
        res = self.res
        if len(res.system) < 0x40:
            raise YtdError("System segment is too small to hold a texture "
                           "dictionary. The file is not a valid .ytd.")

        count = res.u16(DICT_TEXTURES_COUNT)
        ptr = res.u64(DICT_TEXTURES_PTR)

        if count == 0:
            raise YtdError("This .ytd contains no textures.")
        if count > MAX_TEXTURES:
            raise YtdError(
                "Texture count looks corrupted (%d). The file may not be a "
                ".ytd, or it may be a Gen9 / RDR2 variant that this editor "
                "does not support." % count)

        table = res.resolve(ptr)
        if table is None:
            raise YtdError("The texture pointer table is missing or points "
                           "outside the resource (corrupted .ytd).")
        buf, base = table
        if base + count * 8 > len(buf):
            raise YtdError("The texture pointer table runs past the end of "
                           "the resource (corrupted .ytd).")

        for i in range(count):
            tex_ptr = struct.unpack_from("<Q", buf, base + i * 8)[0]
            entry = self._parse_texture(i, tex_ptr)
            if entry is not None:
                self.textures.append(entry)

        if not self.textures:
            raise YtdError("No readable textures were found in this .ytd.")

        self._compute_spans()

    def _parse_texture(self, index, tex_ptr):
        res = self.res
        loc = res.resolve(tex_ptr)
        if loc is None or (tex_ptr & 0xF0000000) != SYSTEM_BASE:
            return None
        _, off = loc
        if off + TEX_STRUCT_SIZE > len(res.system):
            return None

        fields = self._read_texture_fields(off)
        if fields is None:
            fields = self._scan_texture_fields(off)
        if fields is None:
            return None

        name_ptr, w, h, d, stride, fmt, levels, data_ptr = fields

        name = res.cstring(name_ptr, 128) if name_ptr else ""
        if not _looks_like_name(name):
            name = "texture_%d" % index

        entry = TextureEntry(index, name, w, h, d, stride, fmt, levels,
                             off, data_ptr)

        if not tex.is_supported(fmt):
            entry.error = ("Unsupported texture format %s - this texture "
                           "cannot be decoded or edited." % tex.format_name(fmt))
            return entry

        try:
            entry.data_size = tex.total_size(fmt, w, h, levels)
        except tex.TextureFormatError as exc:
            entry.error = str(exc)
            return entry

        loc = res.resolve(data_ptr)
        if loc is None:
            entry.error = "Pixel data pointer is invalid (corrupted texture)."
        else:
            buf, doff = loc
            if doff + entry.data_size > len(buf):
                entry.error = ("Pixel data runs past the end of the resource "
                               "(corrupted texture).")
        return entry

    def _find_data_pointer(self, off, base):
        """
        Locate a texture's pixel-data pointer.

        `base` is the struct offset of the Format field; the data pointer lives
        a fixed distance past it, but that distance differs slightly between
        game builds, so the known candidates are probed first and a scan of the
        struct's tail is used as a fallback.
        """
        res = self.res
        for delta in TEX_DATA_PTR_CANDIDATES:
            cand = res.u64(off + delta)
            if (cand & 0xF0000000) == GRAPHICS_BASE:
                return cand
        # last resort: any qword in the struct that addresses graphics memory
        for pos in range(base + 8, TEX_STRUCT_SIZE - 8, 8):
            cand = res.u64(off + pos)
            if (cand & 0xF0000000) == GRAPHICS_BASE:
                return cand
        # very small textures are occasionally kept in the system segment
        for delta in TEX_DATA_PTR_CANDIDATES:
            cand = res.u64(off + delta)
            if (cand & 0xF0000000) == SYSTEM_BASE:
                return cand
        return 0

    def _read_texture_fields(self, off):
        """Read the canonical grcTexturePC layout and validate it."""
        res = self.res
        name_ptr = res.u64(off + TEX_NAME_PTR)
        w = res.u16(off + TEX_WIDTH)
        h = res.u16(off + TEX_HEIGHT)
        d = res.u16(off + TEX_DEPTH)
        stride = res.u16(off + TEX_STRIDE)
        fmt = res.u32(off + TEX_FORMAT)
        levels = res.u8(off + TEX_LEVELS)

        if not (1 <= w <= 16384 and 1 <= h <= 16384):
            return None
        if not (1 <= levels <= 16):
            return None
        if not tex.is_supported(fmt):
            return None

        data_ptr = self._find_data_pointer(off, TEX_FORMAT)
        if data_ptr == 0:
            return None
        return name_ptr, w, h, d, stride, fmt, levels, data_ptr

    def _scan_texture_fields(self, off):
        """
        Fallback for unusual builds.

        The absolute struct offsets can shift between game versions, but the
        *relative* layout around the format field is stable:

            format-8 = width, format-6 = height, format-4 = depth,
            format-2 = stride, format+5 = levels, format+8 = data pointer

        So we search the struct for a recognised format code and rebuild
        everything relative to it, then look for the name pointer separately.
        """
        res = self.res
        block = res.system[off:off + TEX_STRUCT_SIZE]
        for f in range(8, TEX_STRUCT_SIZE - 16, 4):
            fmt = struct.unpack_from("<I", block, f)[0]
            if not tex.is_supported(fmt):
                continue
            w, h, d, stride = struct.unpack_from("<HHHH", block, f - 8)
            levels = block[f + 5]
            if not (1 <= w <= 16384 and 1 <= h <= 16384 and 1 <= levels <= 16):
                continue
            data_ptr = self._find_data_pointer(off, f)
            if data_ptr == 0:
                continue

            name_ptr = 0
            for n in range(0, TEX_STRUCT_SIZE - 8, 8):
                cand = struct.unpack_from("<Q", block, n)[0]
                if (cand & 0xF0000000) != SYSTEM_BASE:
                    continue
                if _looks_like_name(res.cstring(cand, 64)):
                    name_ptr = cand
                    break
            return name_ptr, w, h, d, stride, fmt, levels, data_ptr
        return None

    def _compute_spans(self):
        """
        Work out how many bytes each texture may safely occupy.

        Pixel blocks are laid out consecutively in the graphics segment, so a
        texture's span ends where the next one begins. We never write past
        that boundary, which makes a miscalculated mip chain fail loudly
        instead of corrupting a neighbouring texture.
        """
        res = self.res
        by_buffer = {}
        for entry in self.textures:
            loc = res.resolve(entry.data_pointer)
            if loc is None:
                continue
            buf, off = loc
            by_buffer.setdefault(id(buf), (buf, []))[1].append((off, entry))

        for buf, items in by_buffer.values():
            items.sort(key=lambda it: it[0])
            for i, (off, entry) in enumerate(items):
                if i + 1 < len(items):
                    end = items[i + 1][0]
                else:
                    end = len(buf)
                entry.available = max(0, end - off)
                if entry.error is None and entry.data_size > entry.available:
                    entry.error = (
                        "Computed pixel data size (%d bytes) exceeds the space "
                        "reserved in the file (%d bytes). This texture will "
                        "not be modified." % (entry.data_size, entry.available))

    # -------------------------------------------------------------- access

    def raw_data(self, entry):
        """Raw bytes of a texture's full mip chain."""
        loc = self.res.resolve(entry.data_pointer)
        if loc is None:
            raise YtdError("Texture '%s' has an invalid data pointer." % entry.name)
        buf, off = loc
        return bytes(buf[off:off + entry.data_size])

    def decode(self, entry):
        """Decode a texture's top mip level to an (h, w, 4) uint8 RGBA array."""
        if entry.error:
            raise YtdError("Cannot open '%s':\n%s" % (entry.name, entry.error))
        try:
            return tex.decode_surface(entry.format, self.raw_data(entry),
                                      entry.width, entry.height)
        except tex.TextureFormatError as exc:
            raise YtdError("Failed to decode '%s':\n%s" % (entry.name, exc)) from exc

    def decode_level(self, entry, level):
        """
        Decode one specific mip level.

        Levels are packed consecutively, so the offset of level N is the sum of
        the sizes of levels 0..N-1.
        """
        if entry.error:
            raise YtdError("Cannot open '%s':\n%s" % (entry.name, entry.error))
        level = max(0, min(level, entry.levels - 1))
        loc = self.res.resolve(entry.data_pointer)
        if loc is None:
            raise YtdError("Texture '%s' has an invalid data pointer." % entry.name)
        buf, off = loc

        w, h = entry.width, entry.height
        for _ in range(level):
            off += tex.level_size(entry.format, w, h)
            w = max(1, w >> 1)
            h = max(1, h >> 1)
        size = tex.level_size(entry.format, w, h)
        try:
            return tex.decode_surface(entry.format, bytes(buf[off:off + size]), w, h)
        except tex.TextureFormatError as exc:
            raise YtdError("Failed to decode '%s':\n%s" % (entry.name, exc)) from exc

    def thumbnail(self, entry, max_size=96):
        """
        Cheap preview: decode the smallest mip that is still >= max_size.

        Decoding a 64x64 mip instead of a 2048x2048 top level keeps the
        texture list responsive even on large vehicle/clothing dictionaries.
        """
        best = 0
        for level in range(entry.levels):
            w = max(1, entry.width >> level)
            h = max(1, entry.height >> level)
            if max(w, h) >= max_size:
                best = level
            else:
                break

        if entry.error:
            raise YtdError("Cannot open '%s':\n%s" % (entry.name, entry.error))
        loc = self.res.resolve(entry.data_pointer)
        if loc is None:
            raise YtdError("Texture '%s' has an invalid data pointer." % entry.name)
        buf, off = loc

        w, h = entry.width, entry.height
        for _ in range(best):
            off += tex.level_size(entry.format, w, h)
            w = max(1, w >> 1)
            h = max(1, h >> 1)
        size = tex.level_size(entry.format, w, h)
        try:
            # decode_preview subsamples blocks, so a single-mip 3072x3072 map
            # tile still produces its list icon almost instantly
            return tex.decode_preview(entry.format, bytes(buf[off:off + size]),
                                      w, h, max_size)
        except tex.TextureFormatError as exc:
            raise YtdError("Failed to decode '%s':\n%s" % (entry.name, exc)) from exc

    def replace(self, entry, image):
        """
        Re-encode `image` and patch it over the texture's pixel data.

        `image` must be (height, width, 4) uint8 RGBA at the texture's original
        dimensions - the whole in-place strategy depends on the encoded size
        being identical to the original.
        """
        if entry.error:
            raise YtdError("Cannot save '%s':\n%s" % (entry.name, entry.error))

        image = np.ascontiguousarray(image, dtype=np.uint8)
        if image.ndim != 3 or image.shape[2] != 4:
            raise YtdError("Internal error: expected an RGBA image for '%s'."
                           % entry.name)
        if image.shape[0] != entry.height or image.shape[1] != entry.width:
            raise YtdError(
                "Texture '%s' must stay %dx%d to be written back into the "
                ".ytd, but the edited image is %dx%d.\n"
                "Resize it back to the original dimensions before saving."
                % (entry.name, entry.width, entry.height,
                   image.shape[1], image.shape[0]))

        try:
            data = tex.encode_mip_chain(entry.format, image, entry.levels)
        except tex.TextureFormatError as exc:
            raise YtdError("Failed to encode '%s':\n%s" % (entry.name, exc)) from exc

        if len(data) != entry.data_size:
            raise YtdError(
                "Encoded size mismatch for '%s' (%d vs %d bytes). Aborting to "
                "avoid corrupting the file."
                % (entry.name, len(data), entry.data_size))
        if len(data) > entry.available:
            raise YtdError(
                "Encoded data for '%s' does not fit in the reserved space. "
                "Aborting to avoid corrupting the file." % entry.name)

        loc = self.res.resolve(entry.data_pointer)
        if loc is None:
            raise YtdError("Texture '%s' has an invalid data pointer." % entry.name)
        buf, off = loc
        buf[off:off + len(data)] = data

    # ---------------------------------------------------------------- save

    def save(self, path):
        try:
            self.res.to_file(path)
        except OSError as exc:
            raise YtdError("Could not write the .ytd file:\n%s" % exc) from exc

    def verify(self):
        """
        Re-parse the bytes we are about to write.

        Cheap insurance: if patching somehow produced something unreadable we
        find out here rather than in-game.
        """
        try:
            data = self.res.to_bytes()
            YtdFile(Rsc7Resource.from_bytes(data))
        except (Rsc7Error, YtdError) as exc:
            raise YtdError("The rebuilt .ytd failed verification:\n%s" % exc) from exc
        return True

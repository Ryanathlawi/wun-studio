from __future__ import annotations

import struct
import zlib

RSC7_MAGIC = 0x37435352
RSC8_MAGIC = 0x38435352
YTD_VERSION = 13

SYSTEM_BASE = 0x50000000
GRAPHICS_BASE = 0x60000000
SEGMENT_MASK = 0x0FFFFFFF


class Rsc7Error(Exception):
    pass


def size_from_flags(flags: int) -> int:
    s0 = ((flags >> 27) & 0x1) << 0
    s1 = ((flags >> 26) & 0x1) << 1
    s2 = ((flags >> 25) & 0x1) << 2
    s3 = ((flags >> 24) & 0x1) << 3
    s4 = ((flags >> 17) & 0x7F) << 4
    s5 = ((flags >> 11) & 0x3F) << 5
    s6 = ((flags >> 7) & 0xF) << 6
    s7 = ((flags >> 5) & 0x3) << 7
    s8 = ((flags >> 4) & 0x1) << 8
    ss = (flags >> 0) & 0xF
    base_size = 0x200 << ss
    return base_size * (s0 + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8)


class Rsc7Resource:

    def __init__(self, version: int, system_flags: int, graphics_flags: int,
                 system: bytearray, graphics: bytearray):
        self.version = version
        self.system_flags = system_flags
        self.graphics_flags = graphics_flags
        self.system = system
        self.graphics = graphics

    @classmethod
    def from_file(cls, path: str) -> "Rsc7Resource":
        try:
            with open(path, "rb") as fh:
                raw = fh.read()
        except OSError as exc:
            raise Rsc7Error(f"Could not read file:\n{exc}") from exc
        return cls.from_bytes(raw)

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Rsc7Resource":
        if len(raw) < 16:
            raise Rsc7Error("File is too small to be a resource (< 16 bytes).")

        magic, version, sys_flags, gfx_flags = struct.unpack_from("<IIII", raw, 0)

        if magic == RSC8_MAGIC:
            raise Rsc7Error(
                "This is an RSC8 resource (Red Dead Redemption 2).\n"
                "Only GTA V / FiveM RSC7 .ytd files are supported."
            )
        if magic != RSC7_MAGIC:
            raise Rsc7Error(
                "Not a valid GTA V resource file: missing 'RSC7' magic.\n"
                "The file may be corrupted, or it may still be packed inside "
                "an .rpf archive (extract it with OpenIV/CodeWalker first)."
            )

        system_size = size_from_flags(sys_flags)
        graphics_size = size_from_flags(gfx_flags)
        total = system_size + graphics_size
        if total == 0:
            raise Rsc7Error("Resource declares a zero-byte size (corrupted header).")

        try:
            body = zlib.decompressobj(-15).decompress(raw[16:], total)
        except zlib.error as exc:
            raise Rsc7Error(
                f"Failed to decompress the resource body (corrupted file?):\n{exc}"
            ) from exc

        if len(body) < total:
            body = body + b"\x00" * (total - len(body))

        return cls(
            version=version,
            system_flags=sys_flags,
            graphics_flags=gfx_flags,
            system=bytearray(body[:system_size]),
            graphics=bytearray(body[system_size:total]),
        )

    def to_bytes(self) -> bytes:
        body = bytes(self.system) + bytes(self.graphics)
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        payload = comp.compress(body) + comp.flush()
        header = struct.pack("<IIII", RSC7_MAGIC, self.version,
                             self.system_flags, self.graphics_flags)
        return header + payload

    def to_file(self, path: str) -> None:
        data = self.to_bytes()
        with open(path, "wb") as fh:
            fh.write(data)

    def resolve(self, pointer: int) -> tuple[bytearray, int] | None:
        if pointer == 0:
            return None
        base = pointer & 0xF0000000
        offset = pointer & SEGMENT_MASK
        if base == SYSTEM_BASE:
            buf = self.system
        elif base == GRAPHICS_BASE:
            buf = self.graphics
        else:
            return None
        if offset >= len(buf):
            return None
        return buf, offset

    def u8(self, off: int) -> int:
        return self.system[off]

    def u16(self, off: int) -> int:
        return struct.unpack_from("<H", self.system, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from("<I", self.system, off)[0]

    def u64(self, off: int) -> int:
        return struct.unpack_from("<Q", self.system, off)[0]

    def cstring(self, pointer: int, limit: int = 256) -> str:
        res = self.resolve(pointer)
        if res is None:
            return ""
        buf, off = res
        end = buf.find(b"\x00", off, min(off + limit, len(buf)))
        if end < 0:
            end = min(off + limit, len(buf))
        return buf[off:end].decode("utf-8", errors="replace")

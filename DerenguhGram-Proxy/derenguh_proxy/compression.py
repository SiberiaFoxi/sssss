"""Streaming compression codecs for DerenguhProto.

The relay is a *byte stream*, not a message queue, so we use a single persistent
zlib/brotli stream per direction and flush on every write (Z_SYNC_FLUSH for zlib,
``flush()`` for brotli). Each flushed block is self-delimiting, which keeps the two
peers synchronised without buffering whole MTProto messages. State per stream is a
few hundred KB at most, so this is safe inside a 128 MB container.

Only ``zlib`` is required (stdlib). ``brotli`` is optional; if it is missing the
server transparently downgrades a brotli request to zlib during negotiation.
"""
from __future__ import annotations

import zlib
from typing import Protocol

from .constants import CODEC_NONE, CODEC_ZLIB, CODEC_BROTLI

try:  # optional dependency
    import brotli  # type: ignore
    HAVE_BROTLI = True
except Exception:  # pragma: no cover - depends on environment
    brotli = None
    HAVE_BROTLI = False


class Compressor(Protocol):
    def compress(self, data: bytes) -> bytes: ...
    def reset(self) -> None: ...


class Decompressor(Protocol):
    def decompress(self, data: bytes) -> bytes: ...
    def reset(self) -> None: ...


class _NoneCompressor:
    __slots__ = ()
    def compress(self, data: bytes) -> bytes:
        return data
    def reset(self) -> None:
        pass


class _NoneDecompressor:
    __slots__ = ()
    def decompress(self, data: bytes) -> bytes:
        return data
    def reset(self) -> None:
        pass


class ZlibCompressor:
    """Persistent deflate stream; every call returns a sync-flushed block.

    Memory note: we use a 4 KB window (wbits=12) and memLevel=5 so each compressor
    costs ~25 KB instead of ~256 KB. The zlib header advertises the window size, so a
    standard decompressor (MAX_WBITS=15) — including Java's Inflater and the C++/Kotlin
    clients — decodes it without any special configuration. Compressors on either side
    may use any window <= 15; decompressors always accept up to 15.
    """
    __slots__ = ("_co", "_level")

    def __init__(self, level: int = 6):
        self._level = level
        self._co = zlib.compressobj(level, zlib.DEFLATED, 12, 5)

    def compress(self, data: bytes) -> bytes:
        # compress() may return b"" if it is still accumulating; flush() forces a
        # decodable boundary (00 00 ff ff) so the peer can decode immediately.
        return self._co.compress(data) + self._co.flush(zlib.Z_SYNC_FLUSH)

    def reset(self) -> None:
        self._co = zlib.compressobj(self._level, zlib.DEFLATED, 12, 5)


class ZlibDecompressor:
    __slots__ = ("_do",)

    def __init__(self):
        self._do = zlib.decompressobj()

    def decompress(self, data: bytes) -> bytes:
        return self._do.decompress(data)

    def reset(self) -> None:
        self._do = zlib.decompressobj()


class BrotliCompressor:
    __slots__ = ("_co", "_quality")

    def __init__(self, quality: int = 5):
        if not HAVE_BROTLI:
            raise RuntimeError("brotli is not installed")
        self._quality = quality
        self._co = brotli.Compressor(quality=quality)

    def compress(self, data: bytes) -> bytes:
        return self._co.process(data) + self._co.flush()

    def reset(self) -> None:
        self._co = brotli.Compressor(quality=self._quality)


class BrotliDecompressor:
    __slots__ = ("_do",)

    def __init__(self):
        if not HAVE_BROTLI:
            raise RuntimeError("brotli is not installed")
        self._do = brotli.Decompressor()

    def decompress(self, data: bytes) -> bytes:
        return self._do.process(data)

    def reset(self) -> None:
        self._do = brotli.Decompressor()


def available_codecs() -> list[int]:
    codecs = [CODEC_NONE, CODEC_ZLIB]
    if HAVE_BROTLI:
        codecs.append(CODEC_BROTLI)
    return codecs


def negotiate(requested: int) -> int:
    """Return the codec the server will actually use for a client request."""
    if requested in available_codecs():
        return requested
    # Unknown or unavailable (e.g. brotli requested but not installed) -> zlib.
    return CODEC_ZLIB


def make_compressor(codec: int) -> Compressor:
    if codec == CODEC_NONE:
        return _NoneCompressor()
    if codec == CODEC_ZLIB:
        return ZlibCompressor()
    if codec == CODEC_BROTLI:
        return BrotliCompressor()
    raise ValueError(f"unknown codec {codec}")


def make_decompressor(codec: int) -> Decompressor:
    if codec == CODEC_NONE:
        return _NoneDecompressor()
    if codec == CODEC_ZLIB:
        return ZlibDecompressor()
    if codec == CODEC_BROTLI:
        return BrotliDecompressor()
    raise ValueError(f"unknown codec {codec}")

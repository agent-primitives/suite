"""Private bounded gzip framing over raw DEFLATE; never owns the input stream."""
from __future__ import annotations

import struct
import zlib
from typing import BinaryIO


class GzipReader:
    def __init__(self, source: BinaryIO) -> None:
        self._source = source
        self._buffer = b""
        self._inflater = zlib.decompressobj(-15)
        self._header_pending = True
        self._started = False
        self._done = False
        self._crc = 0
        self._size = 0

    def _take(self, size: int, allow_eof: bool = False) -> bytes:
        result = bytearray()
        while len(result) < size:
            if not self._buffer:
                self._buffer = self._source.read(65536)
                if not self._buffer:
                    if allow_eof and not result:
                        return b""
                    raise ValueError("truncated gzip header or trailer")
            count = min(size - len(result), len(self._buffer))
            result.extend(self._buffer[:count])
            self._buffer = self._buffer[count:]
        return bytes(result)

    def _header(self) -> bool:
        header = self._take(10, allow_eof=self._started)
        if not header:
            self._done = True
            return False
        if header[:3] != b"\x1f\x8b\x08":
            raise ValueError("invalid gzip header")
        if not self._started and header[4:8] != b"\x00" * 4:
            raise ValueError("initial gzip MTIME must be zero")
        flags = header[3]
        crc = zlib.crc32(header)
        # Go ignores reserved flags, XFL and OS, and bounds each string at
        # 512 bytes including its NUL. FHCRC covers all optional bytes too.
        if flags & 4:
            length = self._take(2)
            crc = zlib.crc32(length, crc)
            crc = zlib.crc32(self._take(int.from_bytes(length, "little")), crc)
        for flag in (8, 16):
            if flags & flag:
                for _ in range(512):
                    char = self._take(1)
                    crc = zlib.crc32(char, crc)
                    if char == b"\x00":
                        break
                else:
                    raise ValueError("gzip header string exceeds 512 bytes")
        if flags & 2 and int.from_bytes(self._take(2), "little") != crc & 0xffff:
            raise ValueError("invalid gzip header CRC")
        if self._started:
            self._inflater = zlib.decompressobj(-15)
        self._header_pending = False
        self._crc = self._size = 0
        self._started = True
        return True

    def read(self, size: int) -> bytes:
        if size < 0:
            raise ValueError("gzip read size must be nonnegative")
        if size == 0:
            return b""
        while not self._done:
            if self._header_pending and not self._header():
                break
            inflater = self._inflater
            try:
                # Even with no compressed input, max_length may have left
                # output inside zlib. Drain that before declaring truncation.
                output = inflater.decompress(self._buffer, size)
            except zlib.error as error:
                raise ValueError(f"invalid gzip deflate stream: {error}") from error
            self._buffer = inflater.unused_data if inflater.eof else inflater.unconsumed_tail
            self._crc = zlib.crc32(output, self._crc)
            self._size = (self._size + len(output)) & 0xffffffff
            if inflater.eof:
                crc, length = struct.unpack("<II", self._take(8))
                if crc != self._crc or length != self._size:
                    raise ValueError("invalid gzip member checksum or size")
                self._header_pending = True
            if output:
                return output
            if not self._header_pending and not self._buffer:
                self._buffer = self._source.read(65536)
                if not self._buffer:
                    raise ValueError("truncated gzip deflate stream")
        return b""

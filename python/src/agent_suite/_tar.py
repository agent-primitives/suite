"""Go-compatible read-only tar framing for private content layers."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ._content import Entry
from ._gzip import GzipReader

_SPECIAL = 1 << 20
_ZERO_TIME = -62135596800 * 10**9
_HEADER_ONLY = (b"1", b"2", b"3", b"4", b"5", b"6")
_KINDS = {b"0": "file", b"1": "hardlink", b"2": "symlink", b"5": "directory"}


def _decimal(value: str) -> int:
    if not re.fullmatch(r"[+-]?[0-9]+", value):
        raise ValueError("invalid tar decimal integer")
    digits = value.lstrip("+-").lstrip("0") or "0"
    if len(digits) > 19:
        raise ValueError("tar integer overflow")
    number = int(digits) * (-1 if value.startswith("-") else 1)
    if not -(1 << 63) <= number < 1 << 63:
        raise ValueError("tar integer overflow")
    return number


def _octal(raw: bytes) -> int:
    raw = raw.strip(b" \0").split(b"\0", 1)[0]
    if raw and not re.fullmatch(rb"[0-7]+", raw):
        raise ValueError("invalid tar octal integer")
    return int(raw or b"0", 8)


def _number(raw: bytes) -> int:
    if not raw[0] & 0x80:
        return _octal(raw)
    bits = len(raw) * 8 - 1
    number = int.from_bytes(raw, "big") & ((1 << bits) - 1)
    if raw[0] & 0x40:
        number -= 1 << bits
    if not -(1 << 63) <= number < 1 << 63:
        raise ValueError("tar binary integer overflow")
    return number


def _text(raw: bytes) -> str:
    # Ignored extension values may be arbitrary bytes; content paths are checked later.
    return raw.split(b"\0", 1)[0].decode("utf-8", "surrogateescape")


def _time(value: str) -> int:
    seconds, dot, fraction = value.partition(".")
    whole = _decimal(seconds)
    if fraction and not re.fullmatch(r"[0-9]+", fraction):
        raise ValueError("invalid tar timestamp")
    nanos = int((fraction[:9] + "000000000")[:9]) if dot else 0
    return whole * 10**9 + (-nanos if seconds.startswith("-") else nanos)


@dataclass
class _Header:
    name: str
    kind: bytes
    mode: int
    uid: int
    gid: int
    size: int
    link: str
    mtime: int
    atime: int = _ZERO_TIME
    ctime: int = _ZERO_TIME


def _header(raw: bytes) -> _Header:
    if len(raw) != 512:
        raise ValueError("truncated tar header")
    checksum = raw[:148] + b" " * 8 + raw[156:]
    if _octal(raw[148:156]) not in (sum(checksum), sum(b if b < 128 else b - 256 for b in checksum)):
        raise ValueError("invalid tar checksum")
    h = _Header(_text(raw[:100]), raw[156:157], _number(raw[100:108]),
                _number(raw[108:116]), _number(raw[116:124]), _number(raw[124:136]),
                _text(raw[157:257]), _number(raw[136:148]) * 10**9)
    prefix = ""
    if raw[257:263] == b"ustar\0" or raw[257:265] == b"ustar  \0":
        _number(raw[329:337])
        _number(raw[337:345])
        if raw[257:263] == b"ustar\0":
            if raw[508:512] == b"tar\0":
                prefix = _text(raw[345:476])
                h.atime = _number(raw[476:488]) * 10**9
                h.ctime = _number(raw[488:500]) * 10**9
            else:
                prefix = _text(raw[345:500])
        else:
            try:
                if raw[345]:
                    h.atime = _number(raw[345:357]) * 10**9
                if raw[357]:
                    h.ctime = _number(raw[357:369]) * 10**9
            except ValueError:
                # Match Go's compatibility fallback for pre-Go1.8 GNU prefixes.
                h.atime = h.ctime = _ZERO_TIME
                candidate = _text(raw[345:500])
                prefix = candidate if candidate.isascii() else ""
    if prefix:
        h.name = prefix + "/" + h.name
    if h.size < 0 and h.kind not in _HEADER_ONLY:
        raise ValueError("negative tar body size")
    return h


def _pax(raw: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    sparse: list[str] = []
    position = 0
    while position < len(raw):
        space = raw.find(b" ", position)
        length = raw[position:space] if space >= 0 else b""
        size = _decimal(length.decode("ascii")) if space >= 0 else 0
        end = position + size
        if size < 5 or end > len(raw) or end <= space + 1 or raw[end - 1] != 10:
            raise ValueError("invalid PAX record length")
        key, equals, value = raw[space + 1:end - 1].partition(b"=")
        if not key or not equals or b"\0" in key:
            raise ValueError("invalid PAX key")
        if key in (b"path", b"linkpath", b"uname", b"gname") and b"\0" in value:
            raise ValueError("invalid PAX string")
        k = key.decode("utf-8", "surrogateescape")
        v = value.decode("utf-8", "surrogateescape")
        if k in ("GNU.sparse.offset", "GNU.sparse.numbytes"):
            expected = "GNU.sparse.offset" if len(sparse) % 2 == 0 else "GNU.sparse.numbytes"
            if k != expected or "," in v:
                raise ValueError("invalid PAX sparse record order")
            sparse.append(v)
        else:
            result[k] = v
        position = end
    if sparse:
        result["GNU.sparse.map"] = ",".join(sparse)
    return result


def _merge(h: _Header, pax: dict[str, str]) -> None:
    for key, field in (("path", "name"), ("linkpath", "link"), ("uid", "uid"),
                       ("gid", "gid"), ("size", "size"), ("mtime", "mtime"),
                       ("atime", "atime"), ("ctime", "ctime")):
        value = pax.get(key, "")
        if value:
            if key in ("uid", "gid", "size"):
                setattr(h, field, _decimal(value))
            elif key in ("mtime", "atime", "ctime"):
                setattr(h, field, _time(value))
            else:
                setattr(h, field, value)


class TarReader:
    def __init__(self, source: GzipReader):
        self.source = source
        self.left = self.padding = self.size = self.position = self.index = 0
        self.spans: list[tuple[int, int]] | None = None

    def _take(self, size: int) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = self.source.read(size - len(data))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data)

    def _physical(self, size: int) -> bytes:
        size = min(size, self.left)
        data = self._take(size)
        if len(data) != size:
            raise ValueError("truncated tar body")
        self.left -= len(data)
        return data

    def read(self, size: int) -> bytes:
        size = min(size, self.size - self.position)
        if self.spans is None:
            data = self._physical(size)
        else:
            while self.index < len(self.spans) and self.position >= sum(self.spans[self.index]):
                self.index += 1
            offset, length = self.spans[self.index] if self.index < len(self.spans) else (self.size, 0)
            if self.position < offset:
                data = b"\0" * min(size, offset - self.position)
            else:
                count = min(size, offset + length - self.position)
                data = self._physical(count)
                if len(data) != count:
                    raise ValueError("sparse file is missing data")
        self.position += len(data)
        if self.spans is not None and self.position == self.size and self.left:
            raise ValueError("sparse file contains unreferenced data")
        return data

    def _sparse(self, h: _Header, pax: dict[str, str]) -> None:
        major, minor = pax.get("GNU.sparse.major", ""), pax.get("GNU.sparse.minor", "")
        if (major, minor) not in (("0", "0"), ("0", "1"), ("1", "0")):
            if major or minor or not pax.get("GNU.sparse.map"):
                return
        name = pax.get("GNU.sparse.name", "")
        if name:
            h.name = name
        logical = pax.get("GNU.sparse.size") or pax.get("GNU.sparse.realsize")
        if logical:
            h.size = _decimal(logical)
        if (major, minor) == ("1", "0"):
            tokens: list[bytes] = []
            pending = b""
            consumed = 0
            needed = 1
            while len(tokens) < needed:
                if consumed >= _SPECIAL:
                    raise ValueError("sparse map exceeds byte limit")
                block = self._physical(512)
                if len(block) != 512:
                    raise ValueError("truncated sparse map")
                consumed += 512
                parts = (pending + block).split(b"\n")
                tokens.extend(parts[:-1])
                pending = parts[-1]
                if needed == 1 and tokens:
                    count = _decimal(tokens[0].decode("ascii"))
                    if count < 0 or count > _SPECIAL:
                        raise ValueError("invalid sparse map population")
                    needed = 1 + count * 2
            values = [token.decode("ascii") for token in tokens[1:needed]]
        else:
            count = _decimal(pax.get("GNU.sparse.numblocks", ""))
            values = pax.get("GNU.sparse.map", "").split(",")
            if values == [""]:
                values = []
            if count < 0 or count > _SPECIAL or len(values) != count * 2:
                raise ValueError("invalid sparse map population")
        self.spans = []
        end = 0
        if h.kind in _HEADER_ONLY or h.size < 0:
            raise ValueError("invalid sparse file type or size")
        for i in range(0, len(values), 2):
            offset, length = _decimal(values[i]), _decimal(values[i + 1])
            if offset < end or length < 0 or offset + length > h.size:
                raise ValueError("invalid sparse extent")
            self.spans.append((offset, length))
            end = offset + length

    def next(self) -> Entry | None:
        pax: dict[str, str] = {}
        long_name = long_link = ""
        while True:
            while self.left:
                self._physical(min(self.left, 128 << 10))
            if len(self._take(self.padding)) != self.padding:
                return None  # Go permits EOF within final entry padding.
            self.padding = 0
            raw = self._take(512)
            if not raw:
                return None
            if raw == b"\0" * 512:
                second = self._take(512)
                if second not in (b"", b"\0" * 512):
                    raise ValueError("invalid tar end marker")
                return None
            h = _header(raw)
            self.left = 0 if h.kind in _HEADER_ONLY else h.size
            self.padding = -self.left % 512
            if h.kind in (b"x", b"L", b"K"):
                if self.left > _SPECIAL:
                    raise ValueError("tar extension exceeds byte limit")
                data = self._physical(self.left)
                if h.kind == b"x":
                    pax = _pax(data)
                elif h.kind == b"L":
                    long_name = _text(data)
                else:
                    long_link = _text(data)
                continue
            _merge(h, pax)
            h.name, h.link = long_name or h.name, long_link or h.link
            if h.kind == b"\0":
                h.kind = b"5" if h.name.endswith("/") else b"0"
            if h.size < 0 and h.kind not in _HEADER_ONLY:
                raise ValueError("negative tar body size")
            self.left = 0 if h.kind in _HEADER_ONLY else h.size
            self.padding = -self.left % 512
            self.spans = None
            self._sparse(h, pax)
            self.size, self.position, self.index = h.size, 0, 0
            if h.mtime != 0 or h.atime != _ZERO_TIME or h.ctime != _ZERO_TIME:
                raise ValueError("tar modification time must be epoch; access/change times unset")
            if h.kind not in _KINDS:
                raise ValueError("unsupported tar entry type")
            if h.mode & 0o7000 or h.kind in (b"0", b"1") and h.mode & 0o022:
                raise ValueError("unsafe tar entry mode")
            name = h.name[:-1] if h.kind == b"5" and h.name.endswith("/") else h.name
            return Entry(name, _KINDS[h.kind], h.mode & 0o777,
                         h.size if h.kind == b"0" else 0,
                         link_target=h.link if h.kind in (b"1", b"2") else "", uid=h.uid, gid=h.gid)

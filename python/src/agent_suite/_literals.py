"""Private, explicitly owned literal snapshots; never a validated package."""
from __future__ import annotations

import codecs
import hashlib
import tempfile
import threading
from collections.abc import Iterable, Iterator
from contextlib import suppress
from dataclasses import dataclass, field

from ._records import FileRef

CHUNK_BYTES = 128 << 10
SPOOL_MEMORY_BYTES = 1 << 20  # Aggregate spill threshold, not an input-size limit.


@dataclass(frozen=True)
class _Range:
    size: int
    digest: str
    offset: int = 0
    data: bytes | None = None


def _check(ref: FileRef, size: int, digest: str) -> None:
    if ref.descriptor.size != size or ref.descriptor.digest != digest:
        raise ValueError(f'{ref.path}: literal pin mismatch')


class LiteralSnapshot:
    def __init__(self) -> None:
        self._file: tempfile.SpooledTemporaryFile[bytes] | None = None
        self._ranges: dict[str, _Range] = {}
        self._sealed = self._closed = False
        self._lock = threading.Lock()

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def _open(self) -> None:
        if self._closed:
            raise ValueError('literal snapshot is closed')

    def _writable(self, ref: FileRef) -> None:
        self._open()
        if self._sealed:
            raise ValueError('literal snapshot is sealed')
        if ref.path in self._ranges:
            raise ValueError(f'{ref.path}: duplicate literal capture')

    def _close(self) -> None:
        self._closed = True
        file, self._file = self._file, None
        try:
            if file is not None:
                file.close()
        finally:
            self._ranges.clear()

    def close(self) -> None:
        with self._lock:
            self._close()

    def __enter__(self) -> LiteralSnapshot:
        with self._lock:
            self._open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _write(self, chunk: bytes) -> None:
        if self._file is None:
            self._file = tempfile.SpooledTemporaryFile(max_size=SPOOL_MEMORY_BYTES, mode='w+b')
        view = memoryview(chunk)
        while view:
            count = self._file.write(view[:CHUNK_BYTES])
            if count is None or count <= 0 or count > min(len(view), CHUNK_BYTES):
                raise OSError('literal snapshot short write')
            view = view[count:]

    def add(self, ref: FileRef, chunks: Iterable[bytes]) -> None:
        with self._lock:
            self._writable(ref)
            try:
                offset = self._file.tell() if self._file is not None else 0
                digest = hashlib.sha256()
                size = 0
                for chunk in chunks:
                    size += len(chunk)
                    if size > ref.descriptor.size:
                        raise ValueError(f'{ref.path}: literal size exceeds pin')
                    digest.update(chunk)
                    if chunk:
                        self._write(chunk)
                actual = 'sha256:' + digest.hexdigest()
                _check(ref, size, actual)
                self._ranges[ref.path] = _Range(size, actual, offset)
            except BaseException:
                with suppress(OSError):
                    self._close()
                raise

    def reuse(self, ref: FileRef, data: bytes) -> None:
        with self._lock:
            self._writable(ref)
            try:
                _check(ref, len(data), 'sha256:' + hashlib.sha256(data).hexdigest())
                self._ranges[ref.path] = _Range(len(data), ref.descriptor.digest, data=data)
            except BaseException:
                with suppress(OSError):
                    self._close()
                raise

    def seal(self) -> None:
        with self._lock:
            self._open()
            try:
                if self._file is not None:
                    self._file.flush()
                self._sealed = True
            except BaseException:
                with suppress(OSError):
                    self._close()
                raise

    def _range(self, ref: FileRef) -> _Range:
        self._open()
        if not self._sealed:
            raise ValueError('literal snapshot is not sealed')
        if ref.path not in self._ranges:
            raise ValueError(f'{ref.path}: literal was not captured')
        item = self._ranges[ref.path]
        _check(ref, item.size, item.digest)
        return item

    def get(self, ref: FileRef) -> LiteralContent:
        with self._lock:
            self._range(ref)
        return LiteralContent(ref, self)

    def _iter(self, ref: FileRef) -> Iterator[bytes]:
        position = 0
        while True:
            with self._lock:
                item = self._range(ref)
                if position >= item.size:
                    return
                size = min(CHUNK_BYTES, item.size - position)
                if item.data is not None:
                    chunk = item.data[position:position+size]
                else:
                    assert self._file is not None
                    self._file.seek(item.offset + position)
                    chunk = self._file.read(size)
                if not chunk:
                    raise OSError(f'{ref.path}: literal snapshot was truncated')
            position += len(chunk)
            # A suspended iterator must not retain a whole reused payload on close.
            del item
            yield chunk


@dataclass(frozen=True)
class LiteralContent:
    reference: FileRef
    _snapshot: LiteralSnapshot = field(repr=False, compare=False)

    def iter_bytes(self) -> Iterator[bytes]:
        yield from self._snapshot._iter(self.reference)

    def iter_text(self, errors: str = 'strict') -> Iterator[str]:
        decoder = codecs.getincrementaldecoder('utf-8')(errors)
        for chunk in self.iter_bytes():
            text = decoder.decode(chunk)
            if text:
                yield text
        final = decoder.decode(b'', final=True)
        if final:
            yield final

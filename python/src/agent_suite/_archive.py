"""Private bounded gzip/tar content loading, not package validation."""
from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from dataclasses import replace
from typing import BinaryIO

from . import _content as c
from ._gzip import GzipReader
from ._literals import LiteralSnapshot
from ._records import FileRef
from ._paths import validate_link, validate_path
from ._tar import TarReader


def load_layer(source: BinaryIO, *, literals: LiteralSnapshot | None = None,
               references: Mapping[str, FileRef] | None = None) -> c.Content:
    gzip = GzipReader(source)
    reader = TarReader(gzip)
    content = c.Content()
    content.source_type = ""
    total = retained = 0
    regular: set[str] = set()
    while True:
        entry = reader.next()
        if entry is None:
            break
        if len(content.entries) >= c.MAX_ENTRIES:
            raise ValueError("content exceeds entry limit")
        name = validate_path(entry.path)
        if entry.kind == "file":
            if entry.size < 0 or entry.size > c.MAX_CONTENT_BYTES - total:
                raise ValueError("content exceeds regular bytes limit")
            total += entry.size
            keep = literals is None and c.retains(name, entry.size)
            if keep:
                retained = c.add_retained(retained, entry.size)
            digest = hashlib.sha256()
            data = bytearray() if keep else None
            entry_size = entry.size
            def chunks() -> Iterator[bytes]:
                remaining = entry_size + int(keep)
                count = 0
                while remaining:
                    chunk = reader.read(min(128 << 10, remaining))
                    if not chunk:
                        break
                    digest.update(chunk)
                    count += len(chunk)
                    remaining -= len(chunk)
                    if data is not None:
                        data.extend(chunk)
                    yield chunk
                if count != entry_size:
                    raise ValueError("file size does not match tar header")
            if literals is not None and references is not None and name in references:
                literals.add(references[name], chunks())
            else:
                for _ in chunks():
                    pass
            entry = replace(entry, digest="sha256:" + digest.hexdigest(),
                            data=bytes(data) if data is not None else None)
            regular.add(name)
        elif entry.kind == "symlink":
            validate_link(name, entry.link_target)
        elif entry.kind == "hardlink":
            target = validate_path(entry.link_target)
            if target not in regular:
                raise ValueError("hardlink target is not an earlier regular file")
        content.add(entry)
    if gzip.read(1):
        raise ValueError("content gzip contains data after the tar archive")
    return content

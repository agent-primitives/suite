"""Private bounded directory snapshots, not schema or graph validation."""
from __future__ import annotations

import hashlib
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager

from . import _content as c
from ._paths import validate_link, validate_path

if sys.platform == "win32":
    from ._directory_windows import Native as Native
else:
    from ._directory_posix import Native as Native

_READ_SIZE = 128 << 10


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


@contextmanager
def _fd(fd: int) -> Iterator[int]:
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _parent(native: Native, root: int, path: str, identities: dict[str, tuple[int, int]]) -> Iterator[int]:
    # Reopen once per directory, not per entry. Keep fd use independent of depth.
    fd = os.dup(root)
    current = ""
    try:
        for part in path.split("/") if path else ():
            previous, fd = fd, native.open_child(fd, part, True)
            os.close(previous)
            current = current + "/" + part if current else part
            if _identity(native.check(fd)) != identities[current]:
                raise ValueError("directory changed while opening")
        yield fd
    finally:
        os.close(fd)


def _read(fd: int, size: int, retained: bool) -> tuple[str, bytes | None]:
    digest = hashlib.sha256()
    data = bytearray() if retained else None
    remaining = size + 1
    count = 0
    while remaining:
        chunk = os.read(fd, min(_READ_SIZE, remaining))
        if not chunk:
            break
        digest.update(chunk)
        count += len(chunk)
        remaining -= len(chunk)
        if data is not None:
            data.extend(chunk)
    if count != size:
        raise ValueError("file size changed while reading")
    return "sha256:" + digest.hexdigest(), bytes(data) if data is not None else None


def load_directory(path: str | os.PathLike[str]) -> c.Content:
    native = Native()
    content = c.Content()
    count = total = retained = 0
    with _fd(native.open_root(path)) as root:
        native.check(root, root=True)
        identities: dict[str, tuple[int, int]] = {}
        pending = [""]
        while pending:
            prefix = pending.pop()
            with _parent(native, root, prefix, identities) as parent:
                names = native.names(parent, c.MAX_ENTRIES - count)
                count += len(names)
                directories = []
                for name in sorted(names):
                    relative = validate_path(prefix + "/" + name if prefix else name)
                    before = native.stat(parent, name)
                    if before.st_mode & 0o7000:
                        raise ValueError("content has setid or sticky mode")
                    if stat.S_ISDIR(before.st_mode):
                        with _fd(native.open_child(parent, name, True)) as fd:
                            opened = native.check(fd)
                            if not stat.S_ISDIR(opened.st_mode) or _identity(before) != _identity(opened):
                                raise ValueError("directory changed while opening")
                            identities[relative] = _identity(opened)
                        content.add(c.Entry(relative, kind="directory", mode=0o755))
                        directories.append(relative)
                    elif stat.S_ISREG(before.st_mode):
                        with _fd(native.open_child(parent, name, False)) as fd:
                            opened = native.check(fd)
                            if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
                                raise ValueError("file changed while opening")
                            size = opened.st_size
                            if size < 0 or size > c.MAX_CONTENT_BYTES - total:
                                raise ValueError("content exceeds regular bytes limit")
                            total += size
                            keep = c.retains(relative, size)
                            if keep:
                                retained = c.add_retained(retained, size)
                            digest, data = _read(fd, size, keep)
                        content.add(c.Entry(relative, size=size, digest=digest, data=data))
                    elif stat.S_ISLNK(before.st_mode):
                        target = native.readlink(parent, name)
                        validate_link(relative, target)
                        content.add(c.Entry(relative, kind="symlink", mode=0o777, link_target=target))
                    else:
                        raise ValueError("content has unsupported file type")
                pending.extend(reversed(directories))
    return content

"""Private Go-compatible OCI regular-file checks, not loose-content ACL policy."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from typing import BinaryIO


def is_regular(info: os.stat_result) -> bool:
    from ._oci_windows import regular_attributes
    return stat.S_ISREG(info.st_mode) and regular_attributes(
        getattr(info, "st_file_attributes", 0), getattr(info, "st_reparse_tag", 0),
    )


def open_regular(path: Path) -> BinaryIO:
    before = path.lstat()
    if not is_regular(before):
        raise ValueError(f"OCI entry must be a regular file: {path}")
    if sys.platform == "win32":
        from ._oci_windows import open_file
        fd = open_file(path)
    else:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        after = os.fstat(fd)
        if not stat.S_ISREG(after.st_mode) or not os.path.samestat(before, after):
            raise ValueError(f"OCI entry changed while opening: {path}")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def read_regular(path: Path, limit: int) -> bytes:
    with open_regular(path) as file:
        size = os.fstat(file.fileno()).st_size
        if not 0 <= size <= limit:
            raise ValueError(f"OCI JSON file exceeds {limit} bytes: {path}")
        data = file.read(limit + 1)
        if len(data) != size:
            raise ValueError(f"OCI file size changed while reading: {path}")
        return data

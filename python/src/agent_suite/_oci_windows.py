"""Private policy-free Windows OCI file open, with CRT handle ownership."""
from __future__ import annotations

import ctypes as c
import importlib
import os
from pathlib import Path
from typing import Any

from ._directory_windows import _bind


def regular_attributes(attributes: int, tag: int) -> bool:
    # Go treats only DEDUP reparse files as regular; other tags are irregular.
    return not attributes & (0x40 | 0x10) and (not attributes & 0x400 or tag == 0x80000013)


def open_file(path: Path) -> int:
    dll = getattr(c, "WinDLL")
    kernel = dll("kernel32", use_last_error=True, winmode=0x800)
    create = _bind(kernel, "CreateFileW", c.c_void_p,
                   [c.c_wchar_p, c.c_uint32, c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32, c.c_void_p])
    close = _bind(kernel, "CloseHandle", c.c_int, [c.c_void_p])
    file_type = _bind(kernel, "GetFileType", c.c_uint32, [c.c_void_p])
    info = _bind(kernel, "GetFileInformationByHandleEx", c.c_int,
                 [c.c_void_p, c.c_int, c.c_void_p, c.c_uint32])
    raw = os.path.abspath(path)
    if not raw.startswith("\\\\?\\"):
        raw = "\\\\?\\UNC\\" + raw[2:] if raw.startswith("\\\\") else "\\\\?\\" + raw
    # Same sharing and reparse-point behavior as Go syscall.Open + O_NOFOLLOW.
    handle = create(raw, 0x80000000, 3, None, 3, 0x02200000, None)
    if handle == c.c_void_p(-1).value:
        raise OSError(getattr(c, "get_last_error")(), "open OCI regular file", str(path))
    try:
        attributes = (c.c_uint32 * 2)()  # FILE_ATTRIBUTE_TAG_INFO.
        if (file_type(handle) != 1 or not info(handle, 9, attributes, c.sizeof(attributes))
                or not regular_attributes(attributes[0], attributes[1])):
            raise OSError("OCI entry is not a regular disk file")
        crt: Any = importlib.import_module("msvcrt")
        fd = int(crt.open_osfhandle(handle, os.O_RDONLY | int(getattr(os, "O_BINARY")) | int(getattr(os, "O_NOINHERIT"))))
    except BaseException:
        close(handle)
        raise
    return fd

"""Create private output nodes; never repair an existing node's owner or ACL."""
from __future__ import annotations

import ctypes as c
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from ._directory_windows import Native


class _SecurityAttributes(c.Structure):
    _fields_ = [('length', c.c_uint32), ('descriptor', c.c_void_p), ('inherit', c.c_int)]


@contextmanager
def _security(parent: int) -> Iterator[tuple[Native, _SecurityAttributes]]:
    native = Native()
    native.check(parent, root=True)
    owner, acl, descriptor = c.c_void_p(), c.c_void_p(), c.c_void_p()
    error = native._security(native._handle(parent), 1, 5, c.byref(owner), None,
                             c.byref(acl), None, c.byref(descriptor))
    try:
        if error:
            raise OSError(error, 'query trusted output parent security')
        if not descriptor.value:
            raise OSError('trusted output parent has no security descriptor')
        # Inheritance alone does not preserve the owner: an elevated token may
        # default to Builtin Administrators. Clone the checked owner and DACL.
        yield native, _SecurityAttributes(c.sizeof(_SecurityAttributes), descriptor, 0)
    finally:
        if descriptor.value:
            native._free(descriptor)


def _long_path(path: Path) -> str:
    raw = str(path)
    if not raw.startswith('\\\\?\\'):
        raw = '\\\\?\\UNC\\' + raw[2:] if raw.startswith('\\\\') else '\\\\?\\' + raw
    return raw


def create_directory(path: Path, parent: int) -> None:
    with _security(parent) as (native, attributes):
        kernel = getattr(c, 'WinDLL')('kernel32', use_last_error=True, winmode=0x800)
        create = kernel.CreateDirectoryW
        create.argtypes = [c.c_wchar_p, c.POINTER(_SecurityAttributes)]
        create.restype = c.c_int
        native._require(create(_long_path(path), c.byref(attributes)), 'create private output directory')


def create_file(path: Path, parent: int) -> int:
    with _security(parent) as (native, attributes):
        # GENERIC_WRITE | READ_CONTROL | FILE_READ_ATTRIBUTES | SYNCHRONIZE;
        # exclusive CREATE_NEW, no sharing, NORMAL | OPEN_REPARSE_POINT.
        handle = native._create(_long_path(path), 0x40120080, 0, c.byref(attributes),
                                1, 0x00200080, None)
        if handle == c.c_void_p(-1).value:
            native._require(False, 'create private output file')
        try:
            flags = os.O_WRONLY | int(getattr(os, 'O_BINARY')) | int(getattr(os, 'O_NOINHERIT'))
            fd = int(native._crt.open_osfhandle(int(handle), flags))
        except BaseException:
            native._close(handle)
            raise
        try:
            native.check(fd)
            return fd
        except BaseException:
            os.close(fd)
            raise

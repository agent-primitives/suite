"""Create a new protected output root; never repair an existing directory ACL."""
from __future__ import annotations

import ctypes as c
from pathlib import Path

from ._directory_windows import Native


class _SecurityAttributes(c.Structure):
    _fields_ = [('length', c.c_uint32), ('descriptor', c.c_void_p), ('inherit', c.c_int)]


def create_root(path: Path, parent: int) -> None:
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
        # Native already checked the owner's identity, owner-only ACEs and
        # SE_DACL_PROTECTED. Supply that descriptor at creation, not after it.
        attributes = _SecurityAttributes(c.sizeof(_SecurityAttributes), descriptor, 0)
        kernel = getattr(c, 'WinDLL')('kernel32', use_last_error=True, winmode=0x800)
        create = kernel.CreateDirectoryW
        create.argtypes = [c.c_wchar_p, c.POINTER(_SecurityAttributes)]
        create.restype = c.c_int
        raw = str(path)
        if not raw.startswith('\\\\?\\'):
            raw = '\\\\?\\UNC\\' + raw[2:] if raw.startswith('\\\\') else '\\\\?\\' + raw
        native._require(create(raw, c.byref(attributes)), 'create private output root')
    finally:
        if descriptor.value:
            native._free(descriptor)

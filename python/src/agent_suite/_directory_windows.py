"""Private rooted Windows reads; CRT fds own every returned native handle.

Semantics follow Go os/root_windows.go, internal/syscall/windows/at_windows.go,
os/dir_windows.go and internal/artifact/directory_security_windows.go. Layouts:
https://learn.microsoft.com/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile
https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_full_dir_info
"""
from __future__ import annotations

import ctypes as c
import importlib
import os
import stat
import struct
import sys
from pathlib import Path
from typing import Any

_U32 = c.c_uint32
_P = c.c_void_p
_PP = c.POINTER(_P)
_BOOL = c.c_int
_WINDOWS = sys.platform == "win32"
_ASCII_UPPER = str.maketrans("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class _Unicode(c.Structure):
    _fields_ = [("length", c.c_uint16), ("maximum", c.c_uint16), ("buffer", _P)]


class _Attributes(c.Structure):
    _fields_ = [
        ("length", _U32), ("root", _P), ("name", c.POINTER(_Unicode)),
        ("attributes", _U32), ("security", _P), ("quality", _P),
    ]


class _Status(c.Structure):
    _fields_ = [("status", _P), ("information", c.c_size_t)]


def _bind(dll: Any, name: str, result: Any, args: list[Any]) -> Any:
    function = getattr(dll, name)
    function.restype = result
    function.argtypes = args
    return function


class Native:
    def __init__(self) -> None:
        if not _WINDOWS:
            raise OSError("Windows directory adapter is unavailable")
        self._crt: Any = importlib.import_module("msvcrt")
        # These ctypes members exist only on Windows; getattr keeps the guarded
        # module importable and type-checkable on every supported host.
        self._last_error = getattr(c, "get_last_error")
        self._format_error = getattr(c, "FormatError")
        dll = getattr(c, "WinDLL")
        # LOAD_LIBRARY_SEARCH_SYSTEM32 prevents current-directory DLL loading.
        kernel = dll("kernel32", use_last_error=True, winmode=0x800)
        adv = dll("advapi32", use_last_error=True, winmode=0x800)
        nt = dll("ntdll", use_last_error=True, winmode=0x800)
        self._close = _bind(kernel, "CloseHandle", _BOOL, [_P])
        self._free = _bind(kernel, "LocalFree", _P, [_P])
        self._process = _bind(kernel, "GetCurrentProcess", _P, [])
        self._create = _bind(
            kernel, "CreateFileW", _P,
            [c.c_wchar_p, _U32, _U32, _P, _U32, _U32, _P],
        )
        self._full = _bind(
            kernel, "GetFullPathNameW", _U32, [c.c_wchar_p, _U32, c.c_wchar_p, _P],
        )
        self._type = _bind(kernel, "GetFileType", _U32, [_P])
        self._info = _bind(kernel, "GetFileInformationByHandle", _BOOL, [_P, _P])
        self._volume = _bind(
            kernel, "GetVolumeInformationByHandleW", _BOOL,
            [_P, _P, _U32, _P, _P, c.POINTER(_U32), _P, _U32],
        )
        self._enumerate = _bind(
            kernel, "GetFileInformationByHandleEx", _BOOL, [_P, c.c_int, _P, _U32],
        )
        self._nt_create = _bind(
            nt, "NtCreateFile", c.c_int32,
            [_PP, _U32, c.POINTER(_Attributes), c.POINTER(_Status),
             _P, _U32, _U32, _U32, _U32, _P, _U32],
        )
        self._nt_error = _bind(nt, "RtlNtStatusToDosError", _U32, [c.c_int32])
        self._device = _bind(nt, "RtlIsDosDeviceName_U", _U32, [c.c_wchar_p])
        self._token = _bind(adv, "OpenProcessToken", _BOOL, [_P, _U32, _PP])
        self._token_info = _bind(
            adv, "GetTokenInformation", _BOOL, [_P, c.c_int, _P, _U32, c.POINTER(_U32)],
        )
        self._security = _bind(
            adv, "GetSecurityInfo", _U32, [_P, c.c_int, _U32, _PP, _PP, _PP, _PP, _PP],
        )
        self._valid_sd = _bind(adv, "IsValidSecurityDescriptor", _BOOL, [_P])
        self._control = _bind(
            adv, "GetSecurityDescriptorControl", _BOOL,
            [_P, c.POINTER(c.c_uint16), c.POINTER(_U32)],
        )
        self._dacl = _bind(
            adv, "GetSecurityDescriptorDacl", _BOOL,
            [_P, c.POINTER(_BOOL), _PP, c.POINTER(_BOOL)],
        )
        self._ace = _bind(adv, "GetAce", _BOOL, [_P, _U32, _PP])
        self._valid_sid = _bind(adv, "IsValidSid", _BOOL, [_P])
        self._sid_len = _bind(adv, "GetLengthSid", _U32, [_P])
        self._equal = _bind(adv, "EqualSid", _BOOL, [_P, _P])
        self._user = self._current_user()

    def _require(self, ok: Any, operation: str) -> None:
        if not ok:
            error = self._last_error()
            raise OSError(error, f"{operation}: {self._format_error(error)}")

    def _current_user(self) -> c.Array[c.c_char]:
        token = _P()
        self._require(self._token(self._process(), 8, c.byref(token)), "open process token")
        try:
            size = _U32()
            self._token_info(token, 1, None, 0, c.byref(size))
            if self._last_error() != 122 or not size.value:
                raise OSError("query current user token size")
            buffer = c.create_string_buffer(size.value)
            self._require(self._token_info(token, 1, buffer, size, c.byref(size)), "query current user")
            sid = _P.from_buffer(buffer)
            if not sid.value or not self._valid_sid(sid):
                raise OSError("invalid current user SID")
            return c.create_string_buffer(c.string_at(sid, self._sid_len(sid)))
        finally:
            self._close(token)

    def _handle(self, fd: int) -> int:
        return int(self._crt.get_osfhandle(fd))

    def _adopt(self, handle: int, root: bool, directory: bool | None) -> int:
        try:
            flags = os.O_RDONLY | int(getattr(os, "O_BINARY")) | int(getattr(os, "O_NOINHERIT"))
            fd = self._crt.open_osfhandle(handle, flags)
        except BaseException:
            self._close(handle)
            raise
        try:
            info = self.check(fd, root=root)
            if directory is not None and stat.S_ISDIR(info.st_mode) != directory:
                raise OSError("directory input has the wrong file type")
            return int(fd)
        except BaseException:
            os.close(fd)
            raise

    def open_root(self, path: str | os.PathLike[str]) -> int:
        raw = os.fspath(path)
        if not raw or "\x00" in raw:
            raise OSError("invalid directory input root")
        raw.encode("utf-16-le", "strict")
        # Only the root may resolve aliases. Descendants use rooted NT opens.
        resolved = str(Path(raw).resolve(strict=True))
        if not resolved.startswith("\\\\?\\"):
            if resolved.startswith("\\\\"):
                resolved = "\\\\?\\UNC\\" + resolved[2:]
            else:
                resolved = "\\\\?\\" + resolved
        handle = self._create(resolved, 0x120089, 7, None, 3, 0x02200000, None)
        if handle == _P(-1).value:
            self._require(False, "open directory input root")
        return self._adopt(int(handle), True, True)

    def _clean_name(self, name: str) -> str:
        if not name or any(ch in name for ch in "\x00:?") or "/" in name or "\\" in name:
            raise OSError("invalid directory input basename")
        name.encode("utf-16-le", "strict")
        # Match Go rootCleanPath's OS lexical cleaning, not a path-prefix
        # security check. Actual authority is the parent handle below.
        prefix = "\\\\?\\?\\"
        buffer = c.create_unicode_buffer(32768)
        length = self._full(prefix + name, len(buffer), buffer, None)
        if not length or length >= len(buffer):
            raise OSError("clean directory input basename")
        cleaned = buffer.value
        if not cleaned.startswith(prefix):
            raise OSError("directory input path escapes root")
        cleaned = cleaned[len(prefix):]
        if not cleaned or cleaned in (".", "..") or "\\" in cleaned or "/" in cleaned or ":" in cleaned:
            raise OSError("invalid cleaned directory input basename")
        base = cleaned.split(".", 1)[0].rstrip(" ")
        upper = base.translate(_ASCII_UPPER)
        reserved = upper in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
        reserved |= (
            len(upper) == 4 and upper[:3] in {"COM", "LPT"}
            and upper[3] in "123456789\u00b9\u00b2\u00b3"
        )
        if reserved and (base == cleaned or self._device(cleaned)):
            raise OSError("reserved directory input device name")
        return cleaned

    def _open(self, parent: int, name: str, directory: bool | None) -> int:
        name = self._clean_name(name)
        encoded = name.encode("utf-16-le", "strict")
        if len(encoded) > 65532:
            raise OSError("directory input basename is too long")
        buffer = c.create_string_buffer(encoded + b"\x00\x00")
        unicode = _Unicode(len(encoded), len(encoded) + 2, c.cast(buffer, _P))
        attrs = _Attributes(
            c.sizeof(_Attributes), self._handle(parent), c.pointer(unicode), 0x1040, None, None,
        )
        handle = _P()
        options = 0x200000 | 0x20 | 0x4000
        if directory is not None:
            options |= 1 if directory else 0x40
        status = self._nt_create(
            c.byref(handle), 0x120089, c.byref(attrs), c.byref(_Status()),
            None, 0x80, 7, 1, options, None, 0,
        )
        if status < 0:
            if handle.value:
                self._close(handle)
            error = int(self._nt_error(status))
            raise OSError(error, f"open directory input child: {self._format_error(error)}", name)
        return self._adopt(int(handle.value or 0), False, directory)

    def open_child(self, parent: int, name: str, directory: bool) -> int:
        return self._open(parent, name, directory)

    def stat(self, parent: int, name: str) -> os.stat_result:
        fd = self._open(parent, name, None)
        try:
            return os.fstat(fd)
        finally:
            os.close(fd)

    def check(self, fd: int, root: bool = False) -> os.stat_result:
        handle = self._handle(fd)
        if self._type(handle) != 1:
            raise OSError("directory input is not a disk file or directory")
        # BY_HANDLE_FILE_INFORMATION: 13 DWORDs, 52 bytes, including FILETIMEs.
        info = (_U32 * 13)()
        self._require(self._info(handle, info), "query directory input attributes")
        if info[0] & (0x400 | 0x40):
            raise OSError("directory input is a reparse point or device")
        if root and not info[0] & 0x10:
            raise OSError("directory input root is not a directory")
        flags = _U32()
        self._require(
            self._volume(handle, None, 0, None, None, c.byref(flags), None, 0),
            "query directory input filesystem",
        )
        if not flags.value & 8:
            raise OSError("directory input filesystem does not enforce persistent ACLs")
        self._check_security(handle, root)
        result = os.fstat(fd)
        if not (stat.S_ISDIR(result.st_mode) or stat.S_ISREG(result.st_mode)):
            raise OSError("directory input is not a regular file or directory")
        return result

    def _check_security(self, handle: int, root: bool) -> None:
        owner, acl, sd = _P(), _P(), _P()
        error = self._security(handle, 1, 5, c.byref(owner), None, c.byref(acl), None, c.byref(sd))
        try:
            if error:
                raise OSError(error, f"query directory input security: {self._format_error(error)}")
            if not sd.value or not self._valid_sd(sd):
                raise OSError("directory input has an invalid security descriptor")
            if not owner.value or not self._valid_sid(owner) or not self._equal(owner, self._user):
                raise OSError("directory input owner is not the current user")
            control, revision = c.c_uint16(), _U32()
            self._require(
                self._control(sd, c.byref(control), c.byref(revision)),
                "query directory input DACL control",
            )
            if root and not control.value & 0x1000:
                raise OSError("directory input root DACL is not protected")
            present, defaulted = _BOOL(), _BOOL()
            self._require(
                self._dacl(sd, c.byref(present), c.byref(acl), c.byref(defaulted)),
                "query directory input DACL",
            )
            if not control.value & 4 or not present.value or not acl.value:
                raise OSError("directory input has a missing or null DACL")
            self._check_aces(acl.value, owner)
        finally:
            if sd.value:
                self._free(sd)

    def _check_aces(self, acl: int, owner: _P) -> None:
        _, _, size, count, _ = struct.unpack("<BBHHH", c.string_at(acl, 8))
        if size < 8:
            raise OSError("directory input has an invalid DACL")
        for index in range(count):
            ace = _P()
            self._require(self._ace(acl, index, c.byref(ace)), "query directory input ACE")
            address = ace.value or 0
            if address < acl + 8 or address + 4 > acl + size:
                raise OSError("directory input has an invalid ACE")
            kind, flags, length = struct.unpack("<BBH", c.string_at(address, 4))
            if kind != 0 or flags & ~0x1F or length < 16 or address + length > acl + size:
                raise OSError("directory input has an unsupported ACE")
            sid = address + 8
            # Bound the variable SID before calling native SID routines.
            sid_length = 8 + 4 * c.c_ubyte.from_address(sid + 1).value
            if (
                8 + sid_length > length or not self._valid_sid(sid)
                or not self._equal(sid, owner)
            ):
                raise OSError("directory input has an invalid or non-owner grant")

    def names(self, fd: int, limit: int) -> list[str]:
        if limit < 0:
            raise OSError("negative directory input entry limit")
        handle = self._handle(fd)
        buffer = c.create_string_buffer(65536)
        names: list[str] = []
        info_class = 15  # FileFullDirectoryRestartInfo, then FileFullDirectoryInfo.
        while True:
            c.memset(buffer, 0, len(buffer))
            if not self._enumerate(handle, info_class, buffer, len(buffer)):
                error = self._last_error()
                if error == 18 or (error == 2 and info_class == 15):
                    return names
                self._require(False, "enumerate directory input")
            info_class = 14
            data = buffer.raw
            offset = 0
            while True:
                if offset + 68 > len(data):
                    raise OSError("invalid directory input enumeration header")
                next_offset = struct.unpack_from("<I", data, offset)[0]
                name_length = struct.unpack_from("<I", data, offset + 60)[0]
                end = offset + next_offset if next_offset else len(data)
                if (next_offset and (next_offset < 68 or next_offset % 8)) or end > len(data):
                    raise OSError("invalid directory input enumeration offset")
                if name_length % 2 or offset + 68 + name_length > end:
                    raise OSError("invalid directory input enumeration name")
                name = data[offset + 68:offset + 68 + name_length].decode("utf-16-le", "strict")
                if name not in (".", ".."):
                    if len(names) >= limit:
                        raise OSError("directory input entry limit exceeded")
                    if not name or "\x00" in name:
                        raise OSError("invalid directory input enumeration name")
                    names.append(name)
                if not next_offset:
                    break
                offset = end

    def readlink(self, parent: int, name: str) -> str:
        raise OSError("directory input symlinks and reparse points are not supported on Windows")

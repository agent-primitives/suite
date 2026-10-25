"""Permission repair and junction creation belong only in owned test fixtures."""
import ctypes as c
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    _adv = c.WinDLL("advapi32", use_last_error=True, winmode=0x800)
    _kernel = c.WinDLL("kernel32", use_last_error=True, winmode=0x800)

    def _bind(dll: Any, name: str, result: Any, args: list[Any]) -> Any:
        function = getattr(dll, name)
        function.restype = result
        function.argtypes = args
        return function

    _ptr = c.c_void_p
    _dword = c.c_uint32
    _pp = c.POINTER(_ptr)
    _process = _bind(_kernel, "GetCurrentProcess", _ptr, [])
    _close = _bind(_kernel, "CloseHandle", c.c_int, [_ptr])
    _free = _bind(_kernel, "LocalFree", _ptr, [_ptr])
    _open_token = _bind(_adv, "OpenProcessToken", c.c_int, [_ptr, _dword, _pp])
    _token_info = _bind(_adv, "GetTokenInformation", c.c_int, [_ptr, c.c_int, _ptr, _dword, c.POINTER(_dword)])
    _sid_string = _bind(_adv, "ConvertSidToStringSidW", c.c_int, [_ptr, _pp])
    _convert = _bind(_adv, "ConvertStringSecurityDescriptorToSecurityDescriptorW", c.c_int, [c.c_wchar_p, _dword, _pp, c.POINTER(_dword)])
    _owner = _bind(_adv, "GetSecurityDescriptorOwner", c.c_int, [_ptr, _pp, c.POINTER(c.c_int)])
    _dacl = _bind(_adv, "GetSecurityDescriptorDacl", c.c_int, [_ptr, c.POINTER(c.c_int), _pp, c.POINTER(c.c_int)])
    _set = _bind(_adv, "SetNamedSecurityInfoW", _dword, [c.c_wchar_p, c.c_int, _dword, _ptr, _ptr, _ptr, _ptr])

    def _require(ok: Any) -> None:
        if not ok:
            raise c.WinError(c.get_last_error())

    def _current_owner() -> str:
        token = _ptr()
        _require(_open_token(_process(), 8, c.byref(token)))
        try:
            size = _dword()
            _token_info(token, 1, None, 0, c.byref(size))
            buffer = c.create_string_buffer(size.value)
            _require(_token_info(token, 1, buffer, size, c.byref(size)))
            text = _ptr()
            _require(_sid_string(_ptr.from_buffer(buffer), c.byref(text)))
            try:
                return c.wstring_at(text)
            finally:
                _free(text)
        finally:
            _close(token)

    def _apply(path: Path, dacl: str | None, protected: bool) -> None:
        owner = _current_owner()
        text = "O:" + owner
        if dacl is not None:
            text += "D:" + dacl.replace("{owner}", owner)
        sd = _ptr()
        _require(_convert(text, 1, c.byref(sd), None))
        try:
            sid = _ptr()
            defaulted = c.c_int()
            _require(_owner(sd, c.byref(sid), c.byref(defaulted)))
            flags = 1
            acl = _ptr()
            if dacl is not None:
                present = c.c_int()
                _require(_dacl(sd, c.byref(present), c.byref(acl), c.byref(defaulted)))
                flags |= 4 | (0x80000000 if protected else 0x20000000)
            error = _set(str(path), 1, flags, sid, None, acl, None)
            if error:
                raise c.WinError(error)
        finally:
            _free(sd)

    def set_acl(path: Path, dacl: str, protected: bool = True) -> None:
        _apply(path, dacl, protected)

    def set_owner(path: Path) -> None:
        _apply(path, None, False)

    def secure_fixture(root: Path) -> None:
        for parent, directories, files in os.walk(root, followlinks=False):
            for path in [Path(parent), *(Path(parent) / n for n in directories + files)]:
                if path.is_symlink() or path.lstat().st_file_attributes & 0x400:
                    raise AssertionError(f"fixture contains a reparse point: {path}")
                set_acl(path, "P(A;OICI;FA;;;{owner})")

    def junction(path: Path, target: Path) -> None:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)], check=True, capture_output=True)

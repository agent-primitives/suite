"""Native Windows behavior; definitions are absent on other platforms, not skipped."""
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import ctypes as c
    import stat

    import pytest

    from agent_suite._directory_windows import Native
    from _directory_windows_fixture import junction, secure_fixture, set_acl, set_owner

    def test_windows_directory_acl(tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "payload").write_bytes(b"fixture\n")
        secure_fixture(tmp_path)
        native = Native()
        fd = native.open_root(root)
        try:
            assert stat.S_ISDIR(native.check(fd, root=True).st_mode)
            child = native.open_child(fd, "payload", False)
            os.close(child)
        finally:
            os.close(fd)
        cases = [
            ("P(A;;FA;;;{owner})(A;;FR;;;WD)", True),
            ("NO_ACCESS_CONTROL", True),
            ("(A;;FA;;;{owner})", False),
            ("P(A;;FA;;;{owner})(OA;;FR;00112233-4455-6677-8899-aabbccddeeff;;WD)", True),
        ]
        for dacl, protected in cases:
            set_acl(root, dacl, protected)
            with pytest.raises(OSError):
                native.open_root(root)
        set_acl(root, "P(A;OICI;FA;;;{owner})")
        inherited = root / "inherited"
        inherited.mkdir()
        set_owner(inherited)
        fd = native.open_root(root)
        try:
            child = native.open_child(fd, "inherited", True)
            try:
                assert stat.S_ISDIR(native.check(child).st_mode)
                with pytest.raises(OSError):
                    native.check(child, root=True)
            finally:
                os.close(child)
        finally:
            os.close(fd)
        fd = native.open_root(root)
        try:
            set_acl(root, "P(A;OICI;FA;;;{owner})(A;OICI;FR;;;WD)")
            broad = root / "broad-inherited"
            broad.mkdir()
            set_owner(broad)
            with pytest.raises(OSError, match="non-owner grant"):
                native.open_child(fd, "broad-inherited", True)
        finally:
            os.close(fd)
        read, write = os.pipe()
        try:
            with pytest.raises(OSError):
                native.check(read)
        finally:
            os.close(read)
            os.close(write)
        with pytest.raises(OSError):
            native.check(-1)

    def test_windows_directory_io(tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        name = "payload-\U0001f680.bin"
        payload = b"a\r\nb\x1ac\x00\xff"
        (root / name).write_bytes(payload)
        (root / "empty").mkdir()
        secure_fixture(tmp_path)
        native = Native()
        fd = native.open_root(root)
        moved = tmp_path / "moved"
        try:
            assert set(native.names(fd, 2)) == {name, "empty"}
            with pytest.raises(OSError):
                native.names(fd, 1)
            assert set(native.names(fd, 2)) == {name, "empty"}
            child = native.open_child(fd, name, False)
            try:
                assert not os.get_inheritable(child)
                assert os.read(child, 100) == payload
                assert native.stat(fd, name).st_size == len(payload)
            finally:
                os.close(child)
            empty = native.open_child(fd, "empty", True)
            try:
                assert native.names(empty, 0) == []
            finally:
                os.close(empty)
            for wrong, directory in [(name, True), ("empty", False)]:
                with pytest.raises(OSError):
                    native.open_child(fd, wrong, directory)
            for bad in [
                "../outside", "a/b", "a\\b", "C:payload", "a?b", "NUL",
                "COM\u00b9", "CONIN$", "..", "", "x\x00y", "\ud800",
            ]:
                with pytest.raises((OSError, UnicodeError)):
                    native.open_child(fd, bad, False)
            with pytest.raises(OSError):
                native.readlink(fd, name)
            original = native.open_child(fd, name, False)
            try:
                before = os.fstat(original)
                assert os.read(original, 100) == payload
            finally:
                os.close(original)
            # Classic Win32 replacement does not promise POSIX semantics for
            # an open destination; the loader race test replaces after lstat.
            replacement = root / "replacement"
            replacement.write_bytes(b"new")
            set_acl(replacement, "P(A;;FA;;;{owner})")
            replacement.replace(root / name)
            after = native.stat(fd, name)
            assert after.st_size == 3
            assert (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            with pytest.raises(OSError):
                root.rename(moved)
        finally:
            os.close(fd)
        root.rename(moved)
        alias = tmp_path / "alias"
        junction(alias, moved)
        fd = native.open_root(alias)
        os.close(fd)
        fd = native.open_root(tmp_path)
        try:
            with pytest.raises(OSError):
                native.open_child(fd, "alias", True)
            with pytest.raises(OSError):
                native.stat(fd, "alias")
        finally:
            os.close(fd)
        extended = "\\\\?\\" + str(moved.resolve())
        fd = native.open_root(extended)
        os.close(fd)
        long_root = moved
        for _ in range(6):
            long_root /= "long-segment-" + "x" * 35
        long_root.mkdir(parents=True)
        secure_fixture(moved)
        fd = native.open_root(long_root)
        os.close(fd)

    def test_windows_directory_cleanup(tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        (root / "file").write_bytes(b"data")
        (root / "bad").write_bytes(b"denied")
        secure_fixture(tmp_path)
        set_acl(root / "bad", "P(A;;FA;;;{owner})(A;;FR;;;WD)")
        kernel = c.WinDLL("kernel32", use_last_error=True, winmode=0x800)
        kernel.GetCurrentProcess.argtypes = []
        kernel.GetCurrentProcess.restype = c.c_void_p
        kernel.GetProcessHandleCount.argtypes = [c.c_void_p, c.POINTER(c.c_uint32)]
        kernel.GetProcessHandleCount.restype = c.c_int

        def count() -> int:
            value = c.c_uint32()
            assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), c.byref(value))
            return value.value

        native = Native()
        fd = native.open_root(root)
        os.close(fd)
        before = count()
        for _ in range(60):
            native = Native()
            fd = native.open_root(root)
            try:
                child = native.open_child(fd, "file", False)
                os.close(child)
                assert native.stat(fd, "file").st_size == 4
                for name, directory in [("bad", False), ("missing", True), ("file", True)]:
                    with pytest.raises(OSError):
                        native.open_child(fd, name, directory)
                with pytest.raises(OSError):
                    native.names(fd, 0)
            finally:
                os.close(fd)
            with pytest.raises(OSError):
                native.open_root(root / "file")
        assert count() <= before + 2

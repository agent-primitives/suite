"""Native OCI access differs from loose-directory ownership/ACL policy."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_oci import materialize


def test_oci_reparse_types(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import stat
    from agent_suite import _oci_io
    from agent_suite import _oci_windows
    for attributes, tag, regular in [(0, 0, True), (0x400, 0x80000013, True),
                                      (0x400, 0xA000000C, False),
                                      (0x400, 0x8000001B, False), (0x10, 0, False)]:
        info = SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=attributes, st_reparse_tag=tag)
        assert _oci_io.is_regular(info) == regular
        assert _oci_windows.regular_attributes(attributes, tag) == regular
    from agent_suite._oci import load_oci_layout
    root = tmp_path / 'layout'
    materialize(root, {'layout': 'minimal-0644'})
    original = Path.lstat

    def reparse(path):
        info = original(path)
        return SimpleNamespace(st_mode=info.st_mode, st_dev=info.st_dev, st_ino=info.st_ino,
                               st_file_attributes=0x400,
                               st_reparse_tag=0x8000001B if path.is_dir() else 0x80000013)

    monkeypatch.setattr(Path, 'lstat', reparse)
    # Non-name-surrogate directories and DEDUP files preserve Go acceptance.
    assert load_oci_layout(root).artifact_digest


def test_oci_native_io(tmp_path):
    from agent_suite._oci import load_oci_layout
    from agent_suite._oci_io import open_regular
    from agent_suite._archive import load_layer
    from agent_suite._directory import load_directory
    import gzip
    import io
    root = tmp_path / 'layout'
    materialize(root, {'layout': 'minimal-0644'})
    before = {p: p.stat().st_mode for p in root.rglob('*')}
    content = load_oci_layout(root)
    assert content.artifact_digest
    assert {p: p.stat().st_mode for p in before} == before
    assert load_layer(io.BytesIO(gzip.compress(b'', mtime=0))).artifact_digest == ''
    loose = tmp_path / 'loose'
    loose.mkdir()
    if os.name != 'nt':
        assert load_directory(loose).artifact_digest == ''
    payload = root / 'binary'
    payload.write_bytes(b'a\r\nb\x1ac\x00\xff')
    with open_regular(payload) as file:
        assert not os.get_inheritable(file.fileno())
        assert file.read() == payload.read_bytes()
    for target in [root, root / 'missing']:
        with pytest.raises((ValueError, OSError)):
            open_regular(target)
    if os.name == 'nt':
        from _directory_windows_fixture import junction, set_acl
        # A broad inherited ACL is legal for OCI, unlike loose content.
        set_acl(root, 'P(A;OICI;FA;;;{owner})(A;OICI;FR;;;WD)')
        alias = tmp_path / 'alias'
        junction(alias, root)
    else:
        for path in root.rglob('*'):
            path.chmod(0o777 if path.is_dir() else 0o666)
        root.chmod(0o777)
        alias = tmp_path / 'alias'
        alias.symlink_to(root, target_is_directory=True)
    assert load_oci_layout(alias).artifact_digest == content.artifact_digest
    # Blob directories are envelope storage, not aliases.
    (root / 'blobs').rename(root / 'real-blobs')
    if os.name == 'nt':
        junction(root / 'blobs', root / 'real-blobs')
    else:
        (root / 'blobs').symlink_to(root / 'real-blobs', target_is_directory=True)
    with pytest.raises(ValueError, match='blob storage'):
        load_oci_layout(root)


def test_oci_stream_bounds(tmp_path, monkeypatch):
    from agent_suite import _oci, _oci_io
    from agent_suite._oci_json import Descriptor
    from agent_suite._json import digest_bytes
    root = tmp_path / 'layout'
    materialize(root, {'layout': 'minimal-0644'})
    original = _oci.open_regular
    counts, closed = [], []

    class Counted:
        def __init__(self, file):
            self.file = file
        def read(self, size):
            assert size >= 0
            counts.append(size)
            return self.file.read(size)
        def __getattr__(self, name):
            return getattr(self.file, name)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()
        def close(self):
            self.file.close()
            closed.append(self.file.closed)

    monkeypatch.setattr(_oci, 'open_regular', lambda path: Counted(original(path)))
    # Index budget is not a compressed-layer budget. Metadata has its own cap.
    monkeypatch.setattr(_oci, '_MAX_INDEXED_BYTES', 1)
    with pytest.raises(ValueError, match='too many bytes'):
        _oci.load_oci_layout(root)
    monkeypatch.setattr(_oci, '_MAX_INDEXED_BYTES', 1 << 30)
    monkeypatch.setattr(_oci, 'MAX_BYTES', 1)
    data = b'not-json' * 30000
    d = Descriptor(digest=digest_bytes(data), size=len(data))
    (root / 'blobs/sha256' / d.digest[7:]).write_bytes(data)
    with _oci._open_blob(root, d) as file:
        assert file.read(1) == b'n'
    assert max(counts) <= _oci._CHUNK and closed and all(closed)
    (root / 'blobs/sha256' / d.digest[7:]).write_bytes(b'X' * len(data))
    previous = len(closed)
    with pytest.raises(ValueError, match='digest'):
        _oci._open_blob(root, d)
    assert len(closed) == previous + 1 and all(closed)
    with pytest.raises(ValueError, match='JSON blob'):
        _oci._read_blob(root, d)
    path = tmp_path / 'changing'
    path.write_bytes(b'old')
    real_fstat = _oci_io.os.fstat

    stats = []

    def change(fd):
        info = real_fstat(fd)
        stats.append(info.st_size)
        if len(stats) == 2:  # After open_regular's identity check.
            path.write_bytes(b'new-size')
        return info

    monkeypatch.setattr(_oci_io.os, 'fstat', change)
    with pytest.raises(ValueError, match='size changed'):
        _oci_io.read_regular(path, 100)


if os.name == 'nt':
    def test_oci_windows_io(tmp_path, monkeypatch):
        import ctypes as c
        from agent_suite import _oci_io
        from agent_suite._directory_windows import _bind
        path = tmp_path
        for _ in range(6):
            path /= 'long-segment-' + 'x' * 35
        path.mkdir(parents=True)
        target = path / 'payload-\U0001f680.bin'
        target.write_bytes(b'\x00\xff\r\n\x1a')
        with _oci_io.open_regular(target) as file:
            assert file.read() == target.read_bytes()
        # Observe handle ownership across both successful and failed opens.
        kernel = c.WinDLL('kernel32', use_last_error=True, winmode=0x800)
        process = _bind(kernel, 'GetCurrentProcess', c.c_void_p, [])
        count = _bind(kernel, 'GetProcessHandleCount', c.c_int, [c.c_void_p, c.POINTER(c.c_uint32)])

        def handles():
            value = c.c_uint32()
            assert count(process(), c.byref(value))
            return value.value

        before = handles()
        from agent_suite import _oci_windows
        original = _oci_windows.open_file
        link = path / 'link'
        link.symlink_to(target)
        with pytest.raises((ValueError, OSError)):
            _oci_io.open_regular(link)
        # Exercise the handle-level no-follow guard, not only the lstat guard.
        with pytest.raises(OSError):
            original(link)

        def replace(name):
            other = name.with_name('replacement')
            other.write_bytes(b'new')
            other.replace(name)
            return original(name)

        for _ in range(30):
            with _oci_io.open_regular(target) as file:
                assert file.read()
            with monkeypatch.context() as patch:
                patch.setattr(_oci_windows, 'open_file', replace)
                with pytest.raises(ValueError, match='changed while opening'):
                    _oci_io.open_regular(target)
        assert handles() <= before + 2


if os.name == 'posix':
    def test_oci_posix_special_files(tmp_path):
        # Killable child: a broken FIFO race guard must not hang the test process.
        code = '''
import os,socket,sys
from pathlib import Path
from agent_suite import _oci_io
root=Path(sys.argv[1]); target=root/'entry'; outside=root/'outside'
outside.write_bytes(b'x')
for kind in ['fifo','socket','link','dangling','swap-fifo','swap-file','swap-link']:
 if target.exists() or target.is_symlink(): target.unlink()
 original=_oci_io.os.open
 server=None
 if kind=='fifo': os.mkfifo(target)
 elif kind=='socket':
  server=socket.socket(socket.AF_UNIX); server.bind(str(target))
 elif kind in ['link','dangling']: target.symlink_to(outside if kind=='link' else root/'missing')
 else:
  target.write_bytes(b'old')
  def replace(path,flags):
   # Keep the observed inode alive so replacement cannot reuse its number.
   target.rename(root/'old-entry')
   if kind=='swap-fifo': os.mkfifo(target)
   elif kind=='swap-link': target.symlink_to(outside)
   else: target.write_bytes(b'new')
   return original(path,flags)
  _oci_io.os.open=replace
 try:
  try: _oci_io.open_regular(target)
  except (OSError,ValueError): pass
  else: raise AssertionError(kind+' accepted')
 finally:
  _oci_io.os.open=original
  if server: server.close()
  if (root/'old-entry').exists(): (root/'old-entry').unlink()
print('OCI_SPECIAL_FILES_OK')
'''
        result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], capture_output=True, timeout=10, check=True)
        assert b'OCI_SPECIAL_FILES_OK' in result.stdout

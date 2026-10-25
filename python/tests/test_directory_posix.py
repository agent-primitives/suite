"""POSIX-specific refusal/race and descriptor-budget tests; no skipped cells."""
import os
import sys

if os.name == "posix":
    import subprocess
    import pytest

    def test_posix_directory_races(tmp_path, monkeypatch):
        from agent_suite import _directory
        root = tmp_path / "root"
        root.mkdir()
        (root / "file").write_bytes(b"fixture")
        outside = tmp_path / "outside"
        outside.write_bytes(b"not input")
        original = _directory.Native.stat

        def replace(self, parent, name):
            info = original(self, parent, name)
            (root / name).unlink()
            (root / name).symlink_to(outside)
            return info

        monkeypatch.setattr(_directory.Native, "stat", replace)
        with pytest.raises(OSError):
            _directory.load_directory(root)

    def test_posix_directory_ancestor_replacement(tmp_path, monkeypatch):
        from agent_suite import _directory
        root = tmp_path / "root"
        root.mkdir()
        (root / "child").mkdir()
        (root / "child" / "old.json").write_bytes(b"{}")
        original_add = _directory.c.Content.add
        replaced = False

        def replace(self, entry):
            nonlocal replaced
            original_add(self, entry)
            if entry.path == "child" and not replaced:
                replaced = True
                (root / "child").rename(tmp_path / "observed-child")
                (root / "child").mkdir()
                (root / "child" / "new.json").write_bytes(b"{}")

        monkeypatch.setattr(_directory.c.Content, "add", replace)
        with pytest.raises(ValueError, match="^directory changed while opening$"):
            _directory.load_directory(root)
        assert replaced

    def test_posix_directory_streams(tmp_path, monkeypatch):
        from agent_suite import _directory
        (tmp_path / "payload").write_bytes(b"fixture")
        original = os.read
        calls = []

        def read(fd, count):
            calls.append(count)
            return original(fd, count)

        with monkeypatch.context() as patch:
            patch.setattr(os, "read", read)
            _directory.load_directory(tmp_path)
        assert calls and max(calls) <= _directory._READ_SIZE
        for replacement in (b"x", b"fixture-more"):
            real_check = _directory.Native.check
            changed = False

            def check(self, fd, root=False):
                nonlocal changed
                info = real_check(self, fd, root)
                if not root and not changed and info.st_size == 7:
                    changed = True
                    (tmp_path / "payload").write_bytes(replacement)
                return info

            (tmp_path / "payload").write_bytes(b"fixture")
            with monkeypatch.context() as patch:
                patch.setattr(_directory.Native, "check", check)
                with pytest.raises(ValueError, match="size changed"):
                    _directory.load_directory(tmp_path)

    def test_posix_directory_fd_bound(tmp_path):
        code = '''
import os,resource,sys
from agent_suite._directory import load_directory
root=sys.argv[1]
current=root
for _ in range(80):
 current=os.path.join(current,"a")
 os.mkdir(current)
with open(os.path.join(current,"leaf.json"),"wb") as file: file.write(b"{}")
before=resource.getrlimit(resource.RLIMIT_NOFILE)
try:
 resource.setrlimit(resource.RLIMIT_NOFILE,(32,before[1]))
 content=load_directory(root)
 assert len(content.entries)==81
finally:
 resource.setrlimit(resource.RLIMIT_NOFILE,before)
'''
        subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True, capture_output=True, timeout=20)

    def test_posix_directory_fifo_swap(tmp_path):
        # A missing O_NONBLOCK must fail this bounded subprocess, not hang pytest.
        code = '''
import os,sys
from pathlib import Path
from agent_suite import _directory
root=Path(sys.argv[1]); (root/"file").write_bytes(b"fixture")
original=_directory.Native.stat
def replace(self,parent,name):
 info=original(self,parent,name)
 (root/name).unlink(); os.mkfifo(root/name,0o600)
 return info
_directory.Native.stat=replace
try:
 _directory.load_directory(root)
except (OSError,ValueError): pass
else: raise AssertionError("FIFO replacement accepted")
'''
        subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True, capture_output=True, timeout=10)

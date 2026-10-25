"""Private descriptor-relative POSIX directory access."""
from __future__ import annotations

import os
import stat
from pathlib import Path


class Native:
    def __init__(self) -> None:
        if os.name != "posix" or os.open not in os.supports_dir_fd or os.scandir not in os.supports_fd:
            raise OSError("directory security checks are unsupported on this platform")
        self.flags = os.O_RDONLY
        for name in ("O_NOFOLLOW", "O_NONBLOCK", "O_CLOEXEC"):
            if not hasattr(os, name):
                raise OSError("directory no-follow checks are unsupported")
            self.flags |= int(getattr(os, name))

    def open_root(self, path: str | os.PathLike[str]) -> int:
        return os.open(Path(path).resolve(strict=True), self.flags | int(getattr(os, "O_DIRECTORY")))

    def open_child(self, parent: int, name: str, directory: bool) -> int:
        flags = self.flags | (int(getattr(os, "O_DIRECTORY")) if directory else 0)
        return os.open(name, flags, dir_fd=parent)

    def stat(self, parent: int, name: str) -> os.stat_result:
        return os.stat(name, dir_fd=parent, follow_symlinks=False)

    def check(self, fd: int, root: bool = False) -> os.stat_result:
        info = os.fstat(fd)
        mode = info.st_mode
        if mode & 0o7000 or (stat.S_ISREG(mode) or stat.S_ISDIR(mode)) and mode & 0o022:
            raise ValueError("content has unsafe file mode")
        if root and not stat.S_ISDIR(mode):
            raise ValueError("directory input root is not a directory")
        return info

    def names(self, fd: int, limit: int) -> list[str]:
        names: list[str] = []
        with os.scandir(fd) as items:
            for item in items:
                if len(names) >= limit:
                    raise ValueError("directory input entry limit exceeded")
                names.append(item.name)
        return names

    def readlink(self, parent: int, name: str) -> str:
        return os.readlink(name, dir_fd=parent)

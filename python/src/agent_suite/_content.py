"""Private loaded content; neither construction nor loading validates a package."""
from __future__ import annotations

from dataclasses import dataclass, field

from ._casefold import fold_case
from ._json import MAX_BYTES as MAX_JSON_BYTES
from ._paths import validate_path

MAX_ENTRIES = 100_000
MAX_CONTENT_BYTES = 4 << 30
MAX_RETAINED_BYTES = 256 << 20


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str = "file"
    mode: int = 0o644
    size: int = 0
    digest: str = ""
    link_target: str = ""
    data: bytes | None = None
    uid: int = 0
    gid: int = 0


@dataclass
class Content:
    entries: dict[str, Entry] = field(default_factory=dict)
    source_type: str = field(default="directory", init=False)
    artifact_digest: str = field(default="", init=False)
    _folded: dict[str, str] = field(default_factory=dict, init=False, repr=False)

    def add(self, entry: Entry) -> None:
        if entry.path in self.entries:
            raise ValueError(f"duplicate content path: {entry.path}")
        folded = fold_case(entry.path)
        if folded in self._folded:
            raise ValueError(f"case-folding path collision: {entry.path}")
        self.entries[entry.path] = entry
        self._folded[folded] = entry.path

    def data(self, path: str) -> bytes:
        path = validate_path(path)
        if path not in self.entries:
            raise ValueError(f"required file is missing: {path}")
        entry = self.entries[path]
        if entry.kind != "file":
            raise ValueError(f"not a regular file: {path}")
        if entry.data is None:
            raise ValueError(f"not retained metadata: {path}")
        return entry.data


def retains(path: str, size: int) -> bool:
    return path.endswith(".json") and 0 <= size <= MAX_JSON_BYTES


def add_retained(current: int, size: int) -> int:
    if current < 0 or size < 0 or size > MAX_RETAINED_BYTES - current:
        raise ValueError("retained metadata exceeds byte limit")
    return current + size

"""Portable path checks shared by private content readers."""
import posixpath

MAX_PATH_BYTES = 1024


def _text(value: str) -> bool:
    try:
        return bool(value) and len(value.encode("utf-8")) <= MAX_PATH_BYTES and "\x00" not in value
    except UnicodeError:
        return False


def validate_path(value: str) -> str:
    if not _text(value) or "\\" in value or value.startswith("/"):
        raise ValueError("unsafe content path")
    clean = posixpath.normpath(value)
    if clean != value or clean in (".", "..") or clean.startswith("../"):
        raise ValueError("content path is not normalized below root")
    return clean


def validate_link(name: str, target: str) -> None:
    if not _text(target) or "\\" in target or target.startswith("/"):
        raise ValueError("unsafe link target")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    if resolved in (".", "..") or resolved.startswith("../"):
        raise ValueError("link target escapes content root")

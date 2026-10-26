"""Private local OCI layout loading; not Suite graph validation or a public API."""
from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import BinaryIO

from . import _oci_json as j
from ._archive import load_layer
from ._content import Content
from ._json import MAX_BYTES, digest_bytes
from ._literals import LiteralSnapshot
from ._records import FileRef
from ._oci_io import open_regular, read_regular

_MAX_INDEX_ENTRIES = 1000
_MAX_INDEXED_BYTES = 1 << 30
_CHUNK = 128 << 10


def _open_blob(root: Path, descriptor: j.Descriptor) -> BinaryIO:
    descriptor.validate()
    # Match Go's path checks; this is not rooted-handle ancestor containment.
    for directory in (root / "blobs", root / "blobs/sha256"):
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_reparse_tag", 0) & 0x20000000:
            raise ValueError("OCI blob storage must use directories, not links")
    file = open_regular(root / "blobs/sha256" / descriptor.digest[7:])
    try:
        if os.fstat(file.fileno()).st_size != descriptor.size:
            raise ValueError("blob size does not match descriptor")
        digest = hashlib.sha256()
        while chunk := file.read(_CHUNK):
            digest.update(chunk)
        if "sha256:" + digest.hexdigest() != descriptor.digest:
            raise ValueError("blob digest does not match descriptor")
        if descriptor.data is not None:
            file.seek(0)
            if file.read(descriptor.size + 1) != descriptor.data:
                raise ValueError("descriptor data does not match local blob")
        file.seek(0)
        return file
    except BaseException:
        file.close()
        raise


def _read_blob(root: Path, descriptor: j.Descriptor) -> bytes:
    if descriptor.size > MAX_BYTES:
        raise ValueError("OCI JSON blob exceeds byte limit")
    with _open_blob(root, descriptor) as file:
        data = file.read(descriptor.size + 1)
    if len(data) != descriptor.size or digest_bytes(data) != descriptor.digest:
        raise ValueError("blob size or digest does not match descriptor")
    return data


def load_oci_layout(path: str | os.PathLike[str], *, literals: LiteralSnapshot | None = None,
                    references: Mapping[str, FileRef] | None = None, artifact_digest: str = '') -> Content:
    raw = os.fspath(path)
    if not raw:
        raise ValueError("OCI layout root must not be empty")
    root = Path(raw)
    if not stat.S_ISDIR(root.stat().st_mode):
        raise ValueError("OCI layout root must be a directory")
    try:
        j.layout(read_regular(root / "oci-layout", MAX_BYTES))
        descriptors = j.index(read_regular(root / "index.json", MAX_BYTES))
        if len(descriptors) > _MAX_INDEX_ENTRIES or len(descriptors) != 1:
            raise ValueError("index.json must contain exactly one manifest descriptor")
        selected = descriptors[0]
        selected.validate()
        if artifact_digest and selected.digest != artifact_digest:
            raise ValueError('OCI artifact changed before literal capture')
        if selected.size > _MAX_INDEXED_BYTES:
            raise ValueError("index.json references too many bytes")
        with _open_blob(root, selected):
            pass
        if selected.media_type != j.MANIFEST or selected.artifact_type not in ("", j.ARTIFACT):
            raise ValueError("index.json must contain one AgentSuite manifest descriptor")
        config, layer = j.manifest(_read_blob(root, selected))
        config.validate()
        layer.validate()
        if _read_blob(root, config) != b"{}":
            raise ValueError("AgentSuite config blob must be the exact bytes {}")
        # Hash and parse the same handle, as Go does. Not an immutable snapshot:
        # an in-place concurrent rewrite between those passes is not prevented.
        with _open_blob(root, layer) as file:
            content = load_layer(file, literals=literals, references=references)
    except (ValueError, OSError) as error:
        if literals is not None and isinstance(error, OSError):
            raise  # Backing-store I/O failure is not a malformed-package refusal.
        raise ValueError(f"OCI layout {root}: {error}") from error
    content.source_type = "oci-layout"
    content.artifact_digest = selected.digest
    return content

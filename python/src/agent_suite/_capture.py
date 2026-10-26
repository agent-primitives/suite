"""Private literal capture from pinned metadata, not whole-package validation."""
from __future__ import annotations

import os
import stat
from collections.abc import Generator
from contextlib import closing, suppress

from ._content import Content
from ._directory import Native, _fd, _identity
from ._documents import Documents, pin_literal
from ._literals import CHUNK_BYTES, LiteralSnapshot
from ._oci import load_oci_layout
from ._records import FileRef


def _targets(content: Content, documents: Documents) -> dict[str, FileRef]:
    refs = [(agent.record.instructions, 'text/markdown; charset=utf-8') for agent in documents.agents]
    for provider in documents.providers:
        for tool in provider.record.tools:
            refs.append((tool.input_schema, 'application/schema+json'))
            if tool.output_schema is not None:
                refs.append((tool.output_schema, 'application/schema+json'))
    targets: dict[str, FileRef] = {}
    for ref, media in refs:
        pin_literal(content, ref, media)  # Every incoming reference precedes reuse.
        targets.setdefault(ref.path, ref)
    return targets


def _reuse(snapshot: LiteralSnapshot, content: Content, targets: dict[str, FileRef]) -> dict[str, FileRef]:
    missing = {}
    for path, ref in targets.items():
        data = content.entries[path].data
        if data is None:
            missing[path] = ref
        else:
            snapshot.reuse(ref, data)
    return missing


def _directory_chunks(native: Native, root: int, ref: FileRef) -> Generator[bytes, None, None]:
    parent = os.dup(root)
    try:
        parts = ref.path.split('/')
        for i, name in enumerate(parts):
            directory = i < len(parts)-1
            before = native.stat(parent, name)
            if not (stat.S_ISDIR(before.st_mode) if directory else stat.S_ISREG(before.st_mode)):
                raise ValueError(f'{ref.path}: literal path is not a regular file beneath directories')
            child = native.open_child(parent, name, directory)
            try:
                opened = native.check(child)
                right_kind = stat.S_ISDIR(opened.st_mode) if directory else stat.S_ISREG(opened.st_mode)
                if not right_kind or _identity(before) != _identity(opened):
                    raise ValueError(f'{ref.path}: literal path changed while opening')
            except BaseException:
                os.close(child)
                raise
            os.close(parent)
            parent = child
        if opened.st_size != ref.descriptor.size:
            raise ValueError(f'{ref.path}: literal size changed')
        remaining = ref.descriptor.size + 1
        while remaining:
            chunk = os.read(parent, min(CHUNK_BYTES, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        os.close(parent)


def capture_directory(path: str | os.PathLike[str], content: Content, documents: Documents) -> LiteralSnapshot:
    targets = _targets(content, documents)
    snapshot = LiteralSnapshot()
    try:
        missing = _reuse(snapshot, content, targets)
        if missing:
            native = Native()
            with _fd(native.open_root(path)) as root:
                native.check(root, root=True)
                for ref in missing.values():
                    with closing(_directory_chunks(native, root, ref)) as chunks:
                        snapshot.add(ref, chunks)
        snapshot.seal()
        for ref in targets.values():
            snapshot.get(ref)
        return snapshot
    except BaseException:
        with suppress(OSError):
            snapshot.close()
        raise


def capture_oci_layout(path: str | os.PathLike[str], content: Content, documents: Documents) -> LiteralSnapshot:
    targets = _targets(content, documents)
    snapshot = LiteralSnapshot()
    try:
        missing = _reuse(snapshot, content, targets)
        if missing:
            if not content.artifact_digest:
                raise ValueError('literal capture requires the original OCI artifact digest')
            load_oci_layout(path, literals=snapshot, references=missing, artifact_digest=content.artifact_digest)
        snapshot.seal()
        for ref in targets.values():
            snapshot.get(ref)
        return snapshot
    except BaseException:
        with suppress(OSError):
            snapshot.close()
        raise

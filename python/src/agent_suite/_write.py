"""Fresh local output, using verified snapshot/capture/native reader primitives."""
from __future__ import annotations

import binascii
import hashlib
import os
import shutil
import stat
import struct
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Protocol

from . import _oci_json as j
from ._capture import _directory_chunks
from ._content import Entry
from ._directory import Native, _fd
from ._edit import file_ref
from ._json import MAX_BYTES, canonical_bytes, digest_bytes
from ._literals import CHUNK_BYTES, LiteralSnapshot
from ._oci import _open_blob, _read_blob, load_oci_layout
from ._oci_io import read_regular
from ._paths import validate_link, validate_path

if TYPE_CHECKING:
    from ._package import Package


class _Readable(Protocol):
    def read(self, size: int = -1) -> bytes: ...


class _Writable(Protocol):
    def write(self, data: bytes, /) -> int: ...


def _chunks(file: _Readable) -> Iterator[bytes]:
    while chunk := file.read(CHUNK_BYTES):
        yield chunk


@contextmanager
def _bytes(package: Package) -> Iterator[LiteralSnapshot]:
    """Capture missing payloads only at explicit write time, and close on failure."""
    with LiteralSnapshot() as snapshot:
        missing = {}
        for entry in package._content.entries.values():
            if entry.kind != 'file':
                continue
            ref = file_ref(entry)
            if entry.data is not None:
                snapshot.reuse(ref, entry.data)
            elif entry.path in package._snapshot._ranges:
                snapshot.add(ref, package._snapshot.get(ref).iter_bytes())
            else:
                missing[entry.path] = ref
        if missing:
            if package._content.source_type == 'directory':
                native = Native()
                with _fd(native.open_root(package._source_path)) as root:
                    native.check(root, root=True)
                    for ref in missing.values():
                        with closing(_directory_chunks(native, root, ref)) as chunks:
                            snapshot.add(ref, chunks)
            else:
                load_oci_layout(package._source_path, literals=snapshot, references=missing,
                                artifact_digest=package._source_artifact_digest)
        snapshot.seal()
        for entry in package._content.entries.values():
            if entry.kind == 'file':
                snapshot.get(file_ref(entry))
        yield snapshot


def _parent_path(dest: str | os.PathLike[str]) -> Path:
    raw = os.fspath(dest)
    if not isinstance(raw, str) or not raw or '\x00' in raw:
        raise ValueError('destination must be a nonempty text path')
    path = Path(raw).absolute()
    # Native.open_root intentionally resolves root aliases for readers. Writers
    # instead require a trusted existing parent without symlink/reparse aliases.
    for parent in (path.parent, *path.parent.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_reparse_tag', 0) & 0x20000000:
            raise ValueError('destination parent must be an existing directory, not a link')
    return path.parent.resolve(strict=True) / path.name


def _remove_fresh(root: Path) -> None:
    # Only this invocation's new tree: never follow links or repair source ACLs.
    pending = [root]
    while pending:
        directory = pending.pop()
        info = directory.lstat()
        if stat.S_ISDIR(info.st_mode) and not getattr(info, 'st_reparse_tag', 0):
            directory.chmod(stat.S_IMODE(info.st_mode) | stat.S_IRWXU)
            pending.extend(directory.iterdir())
    shutil.rmtree(root)


@contextmanager
def _fresh(dest: str | os.PathLike[str]) -> Iterator[Path]:
    path = _parent_path(dest)
    native = Native()
    with _fd(native.open_root(path.parent)) as parent:
        native.check(parent, root=True)
        # mkdir is exclusive. Never remove anything unless this invocation made it.
        if os.name == 'posix':
            os.mkdir(path.name, 0o700, dir_fd=parent)
        else:
            from ._write_windows import create_directory
            create_directory(path, parent)
    try:
        with _fd(native.open_root(path)) as root:
            native.check(root)
        yield path
    except BaseException:
        # Cleanup must not mask the error that made this output incomplete.
        with suppress(OSError):
            _remove_fresh(path)
        raise


def _mkdir(path: Path, mode: int = 0o755) -> None:
    if os.name == 'posix':
        path.mkdir(mode=mode)
    else:
        from ._write_windows import create_directory
        native = Native()
        with _fd(native.open_root(path.parent)) as parent:
            create_directory(path, parent)


def _file(root: Path, relative: str, chunks: Iterable[bytes], mode: int = 0o644) -> None:
    relative = validate_path(relative)
    native = Native()
    with _fd(native.open_root(root)) as initial:
        native.check(initial)
        parent = os.dup(initial)
        try:
            pieces = relative.split('/')
            for piece in pieces[:-1]:
                child = native.open_child(parent, piece, True)
                try:
                    native.check(child)
                except BaseException:
                    os.close(child)
                    raise
                os.close(parent)
                parent = child
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | int(getattr(os, 'O_BINARY', 0))
            if os.name == 'posix':
                flags |= int(getattr(os, 'O_NOFOLLOW')) | int(getattr(os, 'O_CLOEXEC'))
                fd = os.open(pieces[-1], flags, mode, dir_fd=parent)
            else:
                from ._write_windows import create_file
                fd = create_file(root / relative, parent)
            with _fd(fd):
                if os.name == 'posix':
                    getattr(os, 'fchmod')(fd, mode)
                native.check(fd)
                for chunk in chunks:
                    remaining = memoryview(chunk)
                    while remaining:
                        count = os.write(fd, remaining)
                        if count is None or count <= 0 or count > len(remaining):
                            raise OSError('output short write')
                        remaining = remaining[count:]
        finally:
            os.close(parent)
    if os.name == 'nt':
        (root / relative).chmod(mode)


def _entries(package: Package) -> list[Entry]:
    entries = dict(package._content.entries)
    for entry in list(entries.values()):
        validate_path(entry.path)
        parent = entry.path.rpartition('/')[0]
        while parent:
            if parent in entries and entries[parent].kind != 'directory':
                raise ValueError(f'{entry.path}: content has a non-directory ancestor')
            entries.setdefault(parent, Entry(parent, kind='directory', mode=0o755))
            parent = parent.rpartition('/')[0]
        if entry.kind == 'symlink':
            validate_link(entry.path, entry.link_target)
        elif entry.kind == 'hardlink':
            validate_path(entry.link_target)
            target = entries.get(entry.link_target)
            if target is None or target.kind != 'file':
                raise ValueError(f'{entry.path}: hardlink target must be a regular file')
        elif entry.kind not in ('file', 'directory'):
            raise ValueError(f'{entry.path}: unsupported content kind')
    return sorted(entries.values(), key=lambda e: e.path)


def _directory(root: Path, entries: list[Entry], snapshot: LiteralSnapshot) -> None:
    for entry in entries:
        if entry.kind == 'directory':
            _mkdir(root / entry.path, 0o700)
    for entry in entries:
        if entry.kind == 'file':
            _file(root, entry.path, snapshot.get(file_ref(entry)).iter_bytes(), entry.mode)
    for entry in entries:
        if entry.kind == 'symlink':
            os.symlink(entry.link_target, root / entry.path)
        elif entry.kind == 'hardlink':
            os.link(root / entry.link_target, root / entry.path, follow_symlinks=False)
    # _entries rejects link ancestors. Finish all children before read-only modes.
    for entry in reversed(entries):
        if entry.kind == 'directory':
            (root / entry.path).chmod(entry.mode)


def _descriptor(media: str, digest: str, size: int) -> dict[str, Any]:
    return {'mediaType': media, 'digest': digest, 'size': size}


def _blob(root: Path, data: bytes) -> dict[str, Any]:
    digest = digest_bytes(data)
    _file(root, 'blobs/sha256/' + digest[7:], (data,))
    return _descriptor('', digest, len(data))


class _GzipStore:
    """Fixed gzip/DEFLATE STORE framing, independent of zlib and write chunking."""

    def __init__(self, file: _Writable) -> None:
        self._file = file
        self._pending = bytearray()
        self._crc = self._size = 0
        file.write(bytes.fromhex('1f8b08000000000000ff'))

    def _block(self, final: bool) -> None:
        size = len(self._pending)
        self._file.write(struct.pack('<BHH', int(final), size, size ^ 0xffff))
        self._file.write(bytes(self._pending))
        self._pending.clear()

    def write(self, data: bytes) -> int:
        self._crc = binascii.crc32(data, self._crc)
        self._size = (self._size + len(data)) & 0xffffffff
        remaining = memoryview(data)
        while remaining:
            count = min(65535-len(self._pending), len(remaining))
            self._pending.extend(remaining[:count])
            remaining = remaining[count:]
            if len(self._pending) == 65535:
                self._block(False)
        return len(data)

    def finish(self) -> None:
        self._block(True)
        self._file.write(struct.pack('<II', self._crc, self._size))


def _tar(file: BinaryIO | _GzipStore, entries: list[Entry], snapshot: LiteralSnapshot) -> None:
    # tarfile.close adds record padding rejected by our strict reader. Use its
    # standard PAX header encoder but emit only the normative two end blocks.
    ordered = [e for e in entries if e.kind != 'hardlink'] + [e for e in entries if e.kind == 'hardlink']
    kinds = {'file': tarfile.REGTYPE, 'directory': tarfile.DIRTYPE,
             'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE}
    for entry in ordered:
        info = tarfile.TarInfo(entry.path)
        info.type, info.mode = kinds[entry.kind], entry.mode
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ''
        info.linkname = entry.link_target
        info.size = entry.size if entry.kind == 'file' else 0
        file.write(info.tobuf(format=tarfile.PAX_FORMAT, encoding='utf-8', errors='strict'))
        if entry.kind == 'file':
            for chunk in snapshot.get(file_ref(entry)).iter_bytes():
                file.write(chunk)
            file.write(b'\x00' * (-entry.size % 512))
    file.write(b'\x00' * 1024)


def _new_oci(root: Path, entries: list[Entry], snapshot: LiteralSnapshot) -> None:
    _mkdir(root/'blobs')
    _mkdir(root/'blobs/sha256')
    with tempfile.TemporaryFile(mode='w+b') as layer:
        compressed = _GzipStore(layer)
        _tar(compressed, entries, snapshot)
        compressed.finish()
        size = layer.tell()
        layer.seek(0)
        sha = hashlib.sha256()
        for chunk in _chunks(layer):
            sha.update(chunk)
        digest = 'sha256:' + sha.hexdigest()
        layer.seek(0)
        _file(root, 'blobs/sha256/' + digest[7:], _chunks(layer))
    config = _blob(root, b'{}')
    config['mediaType'] = j.EMPTY_CONFIG
    manifest = canonical_bytes({'schemaVersion': 2, 'mediaType': j.MANIFEST, 'artifactType': j.ARTIFACT,
        'config': config, 'layers': [_descriptor(j.CONTENT, digest, size)]})
    selected = _blob(root, manifest)
    selected['mediaType'] = j.MANIFEST
    selected['artifactType'] = j.ARTIFACT
    _file(root, 'oci-layout', (b'{"imageLayoutVersion":"1.0.0"}',))
    _file(root, 'index.json', (canonical_bytes({'schemaVersion': 2, 'mediaType': j.INDEX,
                                              'manifests': [selected]}),))


def _copy_oci(package: Package, root: Path) -> None:
    source = package._source_path
    layout = read_regular(source/'oci-layout', MAX_BYTES)
    j.layout(layout)
    index = read_regular(source/'index.json', MAX_BYTES)
    descriptors = j.index(index)
    if len(descriptors) != 1 or descriptors[0].digest != package._source_artifact_digest:
        raise ValueError('source OCI artifact changed since loading')
    selected = descriptors[0]
    if selected.media_type != j.MANIFEST or selected.artifact_type not in ('', j.ARTIFACT):
        raise ValueError('source OCI descriptor is not an AgentSuite manifest')
    manifest = _read_blob(source, selected)
    config, layer = j.manifest(manifest)
    if _read_blob(source, config) != b'{}':
        raise ValueError('source OCI config must be exact bytes {}')
    _mkdir(root/'blobs')
    _mkdir(root/'blobs/sha256')
    # Verify original descriptors; never reserialize or recompress their bytes.
    for descriptor in (selected, config, layer):
        with _open_blob(source, descriptor) as blob:
            _file(root, 'blobs/sha256/' + descriptor.digest[7:], _chunks(blob))
    _file(root, 'oci-layout', (layout,))
    _file(root, 'index.json', (index,))


def write(package: Package, dest: str | os.PathLike[str], *, oci: bool) -> Path:
    from ._package import LoadError, Package
    diagnostics = package.validate()
    if diagnostics:
        raise LoadError(diagnostics)
    entries = _entries(package)
    # Return the caller's Path spelling while privately using an absolute root.
    result = Path(dest)
    try:
        with _fresh(dest) as root:
            if oci and package._content.source_type == 'oci-layout' and not package._edited:
                _copy_oci(package, root)
            else:
                with _bytes(package) as snapshot:
                    if oci:
                        _new_oci(root, entries, snapshot)
                    else:
                        _directory(root, entries, snapshot)
            # Output framing, all original pins and the complete graph must pass
            # the real public reader before success; never extract a tar layer.
            with Package(root) as loaded:
                if loaded.root_digest != package.root_digest or loaded.validate():
                    raise ValueError('written package identity or validation mismatch')
        return result
    except (OSError, ValueError) as error:
        raise ValueError(f'write {result}: {error}') from error

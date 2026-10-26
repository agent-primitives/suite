"""Private bundled payload checks, not composition or package validation."""
from __future__ import annotations

import posixpath
import re

from ._content import Content
from ._documents import _at, _DIGEST, _ENV, _require
from ._json import digest_bytes, variant_bytes
from ._models import Source
from ._paths import validate_link, validate_path
from ._record_decode import fail
from ._records import ToolProviderVariant


def _absolute(value: str) -> bool:
    # posixpath preserves a double-leading slash, while Go path.Clean does not.
    return value.startswith('/') and not value.startswith('//') and posixpath.normpath(value) == value


def _path(value: str, source: Source) -> None:
    try:
        validate_path(value)
    except ValueError as error:
        fail(source, 'variant.path', str(error))


def validate_variant(variant: ToolProviderVariant, content: Content) -> None:
    source = variant.source
    platform = variant.platform
    _require(platform.os == 'linux' and platform.architecture in ('amd64', 'arm64') and not platform.variant,
             _at(source, 'platform'), 'variant.platform', 'unsupported exact platform')
    _require(_absolute(variant.install_root), _at(source, 'installRoot'),
             'variant.path', 'installRoot must be normalized and absolute')
    _path(variant.payload_root, _at(source, 'payloadRoot'))
    _require(variant.entrypoint.startswith(variant.install_root+'/'), _at(source, 'entrypoint'),
             'variant.entrypoint', 'entrypoint must be below installRoot')
    _require(variant.runtime.abi in ('static', 'gnu', 'musl') and variant.runtime.cpu_baseline,
             variant.runtime.source, 'variant.runtime', 'unsupported ABI or missing CPU baseline')
    for name, values in (('searchPath', variant.search_path), ('writablePaths', variant.writable_paths),
                         ('runtime/requiredBasePaths', variant.runtime.required_base_paths)):
        seen = set()
        for i, value in enumerate(values):
            location = Source(source.file, source.pointer+'/'+name+'/'+str(i))
            _require(_absolute(value) and value not in seen, location, 'variant.path',
                     'absolute path list contains an invalid or duplicate path')
            seen.add(value)
    for i, argument in enumerate(variant.arguments):
        _require('${' not in argument and '$(' not in argument, _at(_at(source, 'arguments'), str(i)),
                 'variant.argument', 'arguments must not interpolate values')
    environment = set()
    for env in variant.environment:
        _require(_ENV.fullmatch(env.name) and env.name not in environment, _at(env.source, 'name'),
                 'variant.environment', 'environment name is invalid or duplicated')
        environment.add(env.name)
        _require((env.secret and env.delivery in ('env', 'file')) or (not env.secret and not env.delivery),
                 _at(env.source, 'delivery'), 'variant.environment', 'secret delivery does not match classification')
        _require(not env.name.startswith('LD_') and env.name not in ('PYTHONPATH', 'NODE_OPTIONS', 'BASH_ENV'),
                 _at(env.source, 'name'), 'variant.environment', 'environment can inject executable code')
    network = set()
    for access in variant.network:
        key = (access.scheme, access.host, access.port)
        _require(re.fullmatch(r'[a-z][a-z0-9+.-]*', access.scheme) and access.host
                 and 1 <= access.port <= 65535 and key not in network, access.source,
                 'variant.network', 'network access is invalid or duplicated')
        network.add(key)
    for name, descriptor in (('sbom', variant.sbom), ('provenance', variant.provenance)):
        if descriptor is not None:
            _require(descriptor.media_type and _DIGEST.fullmatch(descriptor.digest) and descriptor.size >= 0,
                     _at(source, name), 'variant.descriptor', 'invalid optional descriptor')
    _require(variant.files, _at(source, 'files'), 'variant.inventory', 'files must contain a complete inventory')
    inventory = {}
    for entry in variant.files:
        _path(entry.path, _at(entry.source, 'path'))
        _require(entry.path not in inventory, _at(entry.source, 'path'),
                 'variant.duplicate', 'duplicate inventory path')
        inventory[entry.path] = entry
        if entry.type == 'file':
            _require(entry.size >= 0 and _DIGEST.fullmatch(entry.digest) and not entry.link_target,
                     entry.source, 'variant.inventory', 'invalid file metadata')
        elif entry.type == 'directory':
            _require(entry.size == 0 and not entry.digest and not entry.link_target, entry.source,
                     'variant.inventory', 'directory has file or link metadata')
        elif entry.type in ('symlink', 'hardlink'):
            _require(entry.size == 0 and not entry.digest, entry.source, 'variant.inventory', 'link has file metadata')
            try:
                validate_link(entry.path, entry.link_target)
            except ValueError as error:
                fail(_at(entry.source, 'linkTarget'), 'variant.path', str(error))
        else:
            fail(_at(entry.source, 'type'), 'variant.inventory', 'unsupported inventory type')
        _require(0 <= entry.mode <= 0o777, _at(entry.source, 'mode'), 'variant.mode', 'invalid inventory mode')
        path = posixpath.join(variant.payload_root, entry.path)
        actual = content.entries.get(path)
        _require(actual is not None, entry.source, 'variant.missing', 'inventory path is absent from payload')
        try:
            content.bind_directory_mode(path, entry.mode)
        except ValueError as error:
            fail(_at(entry.source, 'mode'), 'variant.mode', str(error))
        actual = content.entries[path]
        _require((actual.kind, actual.mode, actual.uid, actual.gid, actual.size, actual.digest, actual.link_target)
                 == (entry.type, entry.mode, entry.uid, entry.gid, entry.size, entry.digest, entry.link_target),
                 entry.source, 'variant.metadata', 'inventory does not match payload metadata')
        _require(entry.uid == 0 and entry.gid == 0, entry.source, 'variant.owner', 'inventory must be root-owned')
        _require(entry.type not in ('file', 'hardlink') or entry.mode & 0o022 == 0,
                 _at(entry.source, 'mode'), 'variant.mode', 'inventory file is group or world writable')
    prefix = variant.payload_root+'/'
    for path, actual in content.entries.items():
        if path.startswith(prefix) and actual.kind != 'directory':
            _require(path[len(prefix):] in inventory, Source(path), 'variant.untracked', 'payload contains untracked path')
    relative = variant.entrypoint[len(variant.install_root)+1:]
    executable = inventory.get(relative)
    _require(executable is not None and executable.type == 'file' and executable.mode & 0o111,
             _at(source, 'entrypoint'), 'variant.entrypoint', 'entrypoint must identify an executable regular file')
    _require(digest_bytes(variant_bytes(variant.raw.value)) == variant.variant_digest, _at(source, 'variantDigest'),
             'variant.digest', 'variantDigest does not match original canonical metadata')

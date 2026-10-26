"""Private profile semantics beyond the complete owning schemas."""
from __future__ import annotations

import ipaddress
import re

from ._documents import _at, _DIGEST, _ENV, _IDENTIFIER, _require
from ._records import BuildProfile, RuntimeProfile
from ._variants import _absolute


def _port(value: str) -> bool:
    # Go permits arbitrarily zero-padded ports; Python int has a digit ceiling.
    digits = value.lstrip('0')
    return 1 <= len(digits) <= 5 and 1 <= int(digits) <= 65535


def _image_reference(value: str) -> bool:
    """Only extra Go semantics: the owning schema has already checked grammar."""
    authority, remainder = value.split('/', 1)
    repository = remainder.rsplit('@', 1)[0]
    if authority == 'index.docker.io' or (authority != 'localhost' and '.' not in authority and ':' not in authority):
        return False
    if authority == 'docker.io' and '/' not in repository:
        repository = 'library/'+repository
    if len(repository) > 255:
        return False
    if authority.startswith('['):
        host, _, suffix = authority[1:].partition(']')
        try:
            ipaddress.IPv6Address(host)
        except ValueError:
            return False
        return not suffix or _port(suffix[1:])
    host, separator, port = authority.partition(':')
    if separator and not _port(port):
        return False
    return len(host) <= 253 and all(1 <= len(label) <= 63
        and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', label) for label in host.split('.'))


def validate_runtime(profile: RuntimeProfile) -> None:
    # JSON Schema's $ can precede a final newline; Go's identity checks cannot.
    _require(_IDENTIFIER.fullmatch(profile.id) and _IDENTIFIER.fullmatch(profile.configuration_abi),
             profile.source, 'runtime.identity', 'invalid runtime identity or configuration ABI')
    for implementation in (profile.runtime, profile.harness, profile.renderer):
        _require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', implementation.id)
                 and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', implementation.version)
                 and _DIGEST.fullmatch(implementation.digest), implementation.source,
                 'runtime.identity', 'invalid implementation identity')


def validate_build(profile: BuildProfile) -> None:
    _require(_IDENTIFIER.fullmatch(profile.id), _at(profile.source, 'id'), 'build.identity', 'invalid build identity')
    for name, images in (('runtimeBase', profile.runtime_base), ('harness', profile.harness)):
        platforms = set()
        for image in images:
            _require(image.platform not in platforms, _at(image.source, 'platform'),
                     'build.platform', 'duplicate image platform')
            platforms.add(image.platform)
            _require(_DIGEST.fullmatch(image.image.digest) and _image_reference(image.image_ref)
                     and image.image_ref.endswith('@'+image.image.digest),
                     _at(image.source, 'imageRef'), 'build.image', 'invalid registry reference or stale image digest')
    if profile.execution is not None:
        execution = profile.execution
        _require(_absolute(execution.health_path) and not any(c in execution.health_path for c in '?#\\\r\n'),
                 _at(execution.source, 'healthPath'), 'execution.path', 'invalid HTTP health path')
        names, environments = set(), set()
        for item in execution.inputs:
            _require(_IDENTIFIER.fullmatch(item.name) and _ENV.fullmatch(item.environment), item.source,
                     'execution.identity', 'invalid execution input identity')
            _require(item.name not in names, _at(item.source, 'name'), 'execution.duplicate', 'duplicate input name')
            _require(item.environment not in environments, _at(item.source, 'environment'),
                     'execution.duplicate', 'duplicate input environment')
            names.add(item.name)
            environments.add(item.environment)

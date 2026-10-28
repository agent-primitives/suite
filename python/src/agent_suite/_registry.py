"""Digest-preserving publication of validated local OCI layouts."""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO, cast
from urllib.parse import parse_qs, quote, urlsplit, urlunsplit

import requests

from . import _oci_json as j
from ._json import MAX_BYTES, digest_bytes
from ._oci import _open_blob, _read_blob
from ._oci_io import read_regular
from ._package import Package
from ._registry_http import HTTP, location, origin as http_origin, read_response, require

_NAME = re.compile(r'[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*(?:/[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*)*')


class Registry:
    """Publish exact OCI bytes; credentials are explicitly keyed by HTTP origin."""

    def __init__(self, origin: str, *, credentials: Mapping[str, tuple[str, str]] | None = None,
                 timeout: float = 30.0):
        raw = origin if '://' in origin else 'https://' + origin
        self._origin = http_origin(raw)
        parsed = urlsplit(raw)
        if parsed.path not in ('', '/') or parsed.query:
            raise ValueError('registry address must name an origin')
        self._credentials = {}
        for key, pair in (credentials or {}).items():
            target = http_origin(key)
            if key.rstrip('/') != target or not isinstance(pair, tuple) or len(pair) != 2 or not all(isinstance(v, str) for v in pair):
                raise ValueError('registry credentials must be origin-keyed username/password pairs')
            self._credentials[target] = pair
        self._timeout = timeout

    def publish(self, layout: str | os.PathLike[str], repository: str) -> str:
        """Validate and snapshot before HTTP; return only a remotely verified reference."""
        if not isinstance(repository, str) or len(repository) > 255 or not _NAME.fullmatch(repository):
            raise ValueError('invalid OCI repository name')
        with ExitStack() as stack:
            blobs: list[tuple[j.Descriptor, BinaryIO]] = []
            root = Path(layout)
            with Package.load(root) as package:
                if package._content.source_type != 'oci-layout':
                    raise ValueError('registry publication requires a local OCI layout')
                selected = j.index(read_regular(root/'index.json', MAX_BYTES))
                if len(selected) != 1 or selected[0].digest != package.artifact_digest:
                    raise ValueError('OCI artifact changed before publication')
                manifest = _read_blob(root, selected[0])
                config, layer = j.manifest(manifest)
                for descriptor in (config, layer):
                    snapshot = cast(BinaryIO, stack.enter_context(tempfile.TemporaryFile()))
                    hasher = hashlib.sha256()
                    size = 0
                    with _open_blob(root, descriptor) as source:
                        while chunk := source.read(128 << 10):
                            snapshot.write(chunk)
                            hasher.update(chunk)
                            size += len(chunk)
                            if size > descriptor.size:
                                raise ValueError('OCI blob changed during publication snapshot')
                    if size != descriptor.size or 'sha256:' + hasher.hexdigest() != descriptor.digest:
                        raise ValueError('OCI blob changed during publication snapshot')
                    snapshot.seek(0)
                    blobs.append((descriptor, snapshot))
            http = HTTP(self._origin, self._credentials, self._timeout)
            stack.callback(http.close)
            base = self._origin + '/v2/' + repository
            try:
                for descriptor, snapshot in blobs:
                    with http.request('HEAD', base + '/blobs/' + descriptor.digest, 'blob check') as response:
                        if response.status_code == 200:
                            require(response, 200, 'blob check', descriptor.digest)
                            size_header = response.headers.get('Content-Length')
                            if size_header is not None and size_header != str(descriptor.size):
                                raise ValueError('registry blob size mismatch')
                            continue
                        require(response, 404, 'blob check')
                    with http.request('POST', base + '/blobs/uploads/', 'upload start') as response:
                        require(response, 202, 'upload start')
                        value = response.headers.get('Location', '')
                        if not value:
                            raise ValueError('registry upload location missing')
                        target = location(response.url, value)
                    parsed = urlsplit(target)
                    query = parse_qs(parsed.query)
                    if 'digest' in query and query['digest'] != [descriptor.digest]:
                        raise ValueError('registry upload location digest mismatch')
                    if 'digest' not in query:
                        target = urlunsplit(parsed._replace(query=parsed.query + ('&' if parsed.query else '') + 'digest=' + quote(descriptor.digest, safe='')))
                    fields = {'Content-Type': 'application/octet-stream', 'Content-Length': str(descriptor.size)}
                    with http.request('PUT', target, 'blob upload', body=snapshot, headers=fields) as response:
                        require(response, 201, 'blob upload', descriptor.digest)
                digest = digest_bytes(manifest)
                target = base + '/manifests/' + digest
                with http.request('PUT', target, 'manifest upload', body=manifest,
                                  headers={'Content-Type': j.MANIFEST}) as response:
                    require(response, 201, 'manifest upload', digest)
                with http.request('GET', target, 'manifest verification',
                                  headers={'Accept': j.MANIFEST, 'Accept-Encoding': 'identity'}) as response:
                    require(response, 200, 'manifest verification', digest)
                    if read_response(response) != manifest:
                        raise ValueError('registry manifest verification digest mismatch')
            except (requests.RequestException, UnicodeError):
                raise ValueError('registry publication request failed') from None
        return urlsplit(self._origin).netloc + '/' + repository + '@' + digest

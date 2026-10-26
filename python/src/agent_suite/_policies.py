"""Private authored policy validation; no resolution or enforcement."""
from __future__ import annotations

import ipaddress
import posixpath

from ._content import Content
from ._documents import Documents, _at, _pin_json, _require
from ._models import Source
from ._record_decode import read_document
from ._records import Loaded, PolicyV1, PolicyV2
from ._schema import Bundle

_V1 = "application/vnd.agentsuite.policy.v1+json"
_V2 = "application/vnd.agentsuite.policy.v2+json"


def _validate(policy: PolicyV1 | PolicyV2) -> None:
    capability = "filesystem/deny-write/v1" if isinstance(policy, PolicyV1) else "network/egress-allow/v1"
    _require(policy.required_capabilities == (capability,), _at(policy.source, "requiredCapabilities"),
             "policy.capabilities", "policy capabilities must be the exact profile singleton")
    if isinstance(policy, PolicyV1):
        _require(1 <= len(policy.deny_write_paths) <= 4096, _at(policy.source, "denyWritePaths"),
                 "policy.paths", "policy requires 1..4096 deny paths")
        for i, path in enumerate(policy.deny_write_paths):
            # POSIX normpath preserves leading //; Go path.Clean does not.
            _require(path.startswith("/") and not path.startswith("//") and path != "/"
                     and "\x00" not in path and posixpath.normpath(path) == path,
                     _at(_at(policy.source, "denyWritePaths"), str(i)),
                     "policy.path", "deny path must be clean, absolute, and not root")
        return
    endpoints = policy.network.egress_allow
    _require(len(endpoints) <= 4096, _at(policy.network.source, "egressAllow"),
             "policy.network", "policy permits at most 4096 endpoints")
    for endpoint in endpoints:
        try:
            address = str(ipaddress.IPv4Address(endpoint.address))
        except ipaddress.AddressValueError:
            address = ""
        _require(address == endpoint.address and bool(address), _at(endpoint.source, "address"),
                 "policy.address", "network address must be a canonical IPv4 literal")
        _require(endpoint.protocol == "TCP", _at(endpoint.source, "protocol"),
                 "policy.protocol", "network protocol must be TCP")
        _require(1 <= endpoint.port <= 65535, _at(endpoint.source, "port"),
                 "policy.port", "network port must be in 1..65535")


def read_policies(content: Content, documents: Documents, bundle: Bundle) -> dict[str, Loaded[PolicyV1 | PolicyV2]]:
    """Resolve each owner's pinned, schema-checked, ordinary authored policy."""
    result: dict[str, Loaded[PolicyV1 | PolicyV2]] = {}
    files = set()
    for agent in documents.agents:
        ref = agent.record.policy
        if ref is None:
            continue
        _require(ref.path == f"policies/{agent.record.id}.json", _at(ref.source, "path"),
                 "policy.owner", "policy path must match its owning agent")
        media = ref.descriptor.media_type
        _require(media in {_V1, _V2}, _at(ref.source, "descriptor"),
                 "policy.media_type", "unsupported policy media type")
        kind: type[PolicyV1 | PolicyV2] = PolicyV1 if media == _V1 else PolicyV2
        loaded = read_document(_pin_json(content, ref, media), kind, bundle)
        _validate(loaded.record)
        result[agent.record.id] = loaded
        files.add(ref.path)
    for path, entry in content.entries.items():
        if path != "policies" and not path.startswith("policies/"):
            continue
        if path == "policies" and entry.kind == "directory":
            continue
        _require(entry.kind == "file" and path in files, Source(path),
                 "policy.namespace", "orphaned or nonregular policy path")
    return result

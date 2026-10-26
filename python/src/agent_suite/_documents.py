"""Private document/pin/declaration prerequisites, never verified graph state."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from ._content import Content, Entry
from ._json import canonical_bytes, decode, digest_bytes
from ._models import Document, Source
from ._paths import validate_path
from ._record_decode import DocumentError, fail, read_document
from ._records import (
    Agent, Catalog, CompositionRef, Extension, FileRef, Loaded, ManifestRef,
    Suite, ToolProvider, ToolProviderCompositionRef,
)
from ._schema import Bundle

_PREFIX = "application/vnd.agentsuite."
_AGENT = _PREFIX + "agent.v1+json"
_PROVIDER = _PREFIX + "tool.provider.v1+json"
_CATALOG = _PREFIX + "tool.provider.catalog.v1+json"
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?")
_CAPABILITY = re.compile(r"[a-z0-9][a-z0-9.-]{0,127}")
_ENV = re.compile(r"[A-Z_][A-Z0-9_]*")
_HEADER = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,128}")
_SECRET_KEY = re.compile(r"[A-Za-z0-9._-]{1,253}")
_DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
_RESERVED_HEADERS = {"accept", "connection", "content-length", "content-type", "host",
                     "last-event-id", "mcp-protocol-version", "mcp-session-id", "transfer-encoding"}
Reference = FileRef | ManifestRef | CompositionRef | ToolProviderCompositionRef


def _at(source: Source, key: str) -> Source:
    return Source(source.file, source.pointer + "/" + key.replace("~", "~0").replace("/", "~1"))


def _require(condition: object, source: Source, code: str, message: str) -> None:
    if not condition:
        fail(source, code, message)


def _unique(keys: Iterable[tuple[str, Source]]) -> None:
    seen = set()
    for key, source in keys:
        _require(key not in seen, source, "declaration.duplicate", "duplicate declaration key")
        seen.add(key)


def _extensions(values: tuple[Extension, ...]) -> None:
    _unique((v.name, _at(v.source, "name")) for v in values)
    for value in values:
        _require(_CAPABILITY.fullmatch(value.name), _at(value.source, "name"),
                 "declaration.extension", "extension name is invalid")
        _require(not value.critical, _at(value.source, "critical"),
                 "declaration.critical", "unknown critical extension is unsupported")
        _require(not value.digest or _DIGEST.fullmatch(value.digest), _at(value.source, "digest"),
                 "declaration.digest", "extension digest is invalid")


def validate_declarations(record: Suite | Agent | Catalog | ToolProvider) -> None:
    """Only local declaration rules; no inventory, closure or runtime qualification."""
    if isinstance(record, Catalog):
        _require(record.schema_version == "1.0.0-draft" and record.media_type == _CATALOG,
                 record.source, "document.header", "unsupported catalog header")
        return
    _extensions(record.extensions)
    if isinstance(record, Suite):
        _require(_IDENTIFIER.fullmatch(record.name), _at(record.source, "name"),
                 "declaration.identity", "suite name is invalid")
        return
    _require(_IDENTIFIER.fullmatch(record.id), _at(record.source, "id"),
             "declaration.identity", "document id is invalid")
    if isinstance(record, Agent):
        model = record.model
        env = model.endpoint_env
        _require((not env or _ENV.fullmatch(env))
                 and not (env.startswith("LD_") or env in {"PYTHONPATH", "NODE_OPTIONS", "BASH_ENV"}),
                 _at(model.source, "endpointEnv"), "declaration.env", "model endpointEnv is invalid")
        if model.capabilities is not None:
            _require(model.protocol == "openai-compatible", _at(model.source, "protocol"),
                     "declaration.model", "capability-based inference needs openai-compatible protocol")
            cap = model.capabilities
            _require(cap.output_tokens <= cap.context_tokens, _at(cap.source, "outputTokens"),
                     "declaration.model", "output tokens must fit context")
        _unique((name, _at(model.source, "secretRefs")) for name in model.secret_refs)
        for name in model.secret_refs:
            _require(_IDENTIFIER.fullmatch(name), _at(model.source, "secretRefs"),
                     "declaration.identity", "model secret reference is invalid")
        _unique((p.id + "@" + p.version, p.source) for p in record.tool_providers)
        for requirement in record.tool_providers:
            _require(_IDENTIFIER.fullmatch(requirement.id) and _VERSION.fullmatch(requirement.version),
                     requirement.source, "declaration.identity", "provider requirement needs an exact identity")
        _unique((i.agent, _at(i.source, "agent")) for i in record.invokes)
        for invoke in record.invokes:
            _require(_IDENTIFIER.fullmatch(invoke.agent) and invoke.agent != record.id, _at(invoke.source, "agent"),
                     "declaration.invoke", "an agent must not invoke itself")
        return
    _require(_VERSION.fullmatch(record.version), _at(record.source, "version"),
             "declaration.version", "provider version is invalid")
    _unique((tool.name, _at(tool.source, "name")) for tool in record.tools)
    for tool in record.tools:
        _require(_IDENTIFIER.fullmatch(tool.name), _at(tool.source, "name"),
                 "declaration.identity", "tool name is invalid")
        if tool.delegated_authorization is not None:
            _require(tool.effect and tool.approval, _at(tool.source, "delegatedAuthorization"),
                     "declaration.authorization", "delegated authorization needs effect and approval")
            auth = tool.delegated_authorization
            _require(_IDENTIFIER.fullmatch(auth.service) and _CAPABILITY.fullmatch(auth.scope)
                     and _IDENTIFIER.fullmatch(auth.credential.binding_ref), auth.source,
                     "declaration.authorization", "delegated authorization identity is invalid")
    if record.remote is not None:
        remote = record.remote
        _unique((h.name.lower(), _at(h.source, "name")) for h in remote.headers)
        _unique((n.destination_ref, _at(n.source, "destinationRef")) for n in remote.network)
        _require(_IDENTIFIER.fullmatch(remote.endpoint_ref), _at(remote.source, "endpointRef"),
                 "declaration.identity", "remote endpoint reference is invalid")
        for network in remote.network:
            _require(_IDENTIFIER.fullmatch(network.destination_ref), _at(network.source, "destinationRef"),
                     "declaration.identity", "network destination reference is invalid")
        for header in remote.headers:
            _require(_IDENTIFIER.fullmatch(header.secret_ref.name), _at(header.secret_ref.source, "name"),
                     "declaration.identity", "header secret reference is invalid")
            _require(_SECRET_KEY.fullmatch(header.secret_ref.key), _at(header.secret_ref.source, "key"),
                     "declaration.identity", "header secret key is invalid")
            _require(_HEADER.fullmatch(header.name) and header.name.lower() not in _RESERVED_HEADERS, _at(header.source, "name"),
                     "declaration.header", "header is transport-managed")


def pin_literal(content: Content, ref: Reference, media_type: str) -> Entry:
    """Match streamed entry identity, even when literal bytes were not retained."""
    source = _at(ref.source, "descriptor")
    _require(ref.descriptor.media_type == media_type, source, "pin.media_type", "reference media type mismatch")
    try:
        path = validate_path(ref.path)
    except ValueError as error:
        fail(_at(ref.source, "path"), "pin.path", str(error))
    entry = content.entries.get(path)
    _require(entry is not None and entry.kind == "file", _at(ref.source, "path"),
             "pin.file", "referenced content must be a regular file")
    assert entry is not None
    _require(entry.size == ref.descriptor.size, source, "pin.size", "referenced file size mismatch")
    _require(entry.digest == ref.descriptor.digest, source, "pin.digest", "referenced file digest mismatch")
    return entry


def _pin_json(content: Content, ref: Reference, media_type: str) -> Document:
    pin_literal(content, ref, media_type)
    try:
        data = content.data(ref.path)
        value = decode(data)
        _require(canonical_bytes(value) == data, Source(ref.path), "pin.canonical",
                 "pinned manifest must be stored as canonical JSON")
        _require(len(data) == ref.descriptor.size and digest_bytes(data) == ref.descriptor.digest,
                 _at(ref.source, "descriptor"), "pin.digest", "manifest bytes do not match descriptor")
        _require(isinstance(value, dict), Source(ref.path), "document.type", "expected manifest object")
        return Document(data, Source(ref.path))
    except DocumentError:
        raise
    except ValueError as error:
        fail(Source(ref.path), "document.json", str(error))


def pin_manifest(content: Content, ref: Reference, media_type: str) -> Document:
    document = _pin_json(content, ref, media_type)
    value = document.value
    _require(value.get("schemaVersion") == "1.0.0-draft" and value.get("mediaType") == media_type,
             document.source, "document.header", "unsupported manifest header")
    return document


@dataclass(frozen=True)
class Documents:
    suite: Loaded[Suite]
    catalog: Loaded[Catalog]
    agents: tuple[Loaded[Agent], ...]
    providers: tuple[Loaded[ToolProvider], ...]
    raw_manifests: tuple[Document, ...]


def read_documents(content: Content, bundle: Bundle) -> Documents:
    """Collect private prerequisites; successful return is NOT graph validation."""
    try:
        document = Document.from_bytes(content.data("agentsuite.json"), Source("agentsuite.json"))
    except ValueError as error:
        fail(Source("agentsuite.json"), "document.json", str(error))
    suite = read_document(document, Suite, bundle)
    validate_declarations(suite.record)
    s = suite.record
    catalog = read_document(pin_manifest(content, s.tool_provider_catalog, _CATALOG), Catalog, bundle)
    validate_declarations(catalog.record)
    _unique((r.id, r.source) for r in s.agents)
    _unique((r.path, _at(r.source, "path")) for r in s.agents)
    agents = []
    for ref in s.agents:
        loaded = read_document(pin_manifest(content, ref, _AGENT), Agent, bundle)
        _require(loaded.record.id == ref.id, ref.source, "document.identity", "agent reference identity mismatch")
        validate_declarations(loaded.record)
        agent = loaded.record
        pin_literal(content, agent.instructions, "text/markdown; charset=utf-8")
        for evaluation in agent.evals:
            pin_manifest(content, evaluation, _PREFIX + "eval.index.v1+json")
        if agent.policy is not None:
            # Agent schema limits media type to v1/v2; policy has its own envelope.
            _pin_json(content, agent.policy, agent.policy.descriptor.media_type)
        agents.append(loaded)
    refs = catalog.record.tool_providers
    _unique((r.id + "@" + r.version, r.source) for r in refs)
    providers = []
    for ref in refs:
        _require(_IDENTIFIER.fullmatch(ref.id) and _VERSION.fullmatch(ref.version), ref.source,
                 "declaration.identity", "provider reference needs an exact identity")
        provider = read_document(pin_manifest(content, ref, _PROVIDER), ToolProvider, bundle)
        p = provider.record
        _require((p.id, p.version) == (ref.id, ref.version), ref.source,
                 "document.identity", "provider reference identity mismatch")
        validate_declarations(p)
        for tool in p.tools:
            pin_literal(content, tool.input_schema, "application/schema+json")
            if tool.output_schema is not None:
                pin_literal(content, tool.output_schema, "application/schema+json")
        providers.append(provider)
    raw_manifests = []
    checked: dict[tuple[str, str, bytes | None], Document] = {}
    for group, media in ((s.compositions, "composition"), (s.build_profiles, "build.profile"),
                        (s.tool_provider_compositions, "tool.provider.composition"),
                        (s.runtime_profiles, "runtime.profile")):
        for other in group:
            media_type = _PREFIX + media + ".v1+json"
            # Each reference is checked; only successful byte/envelope work is reused.
            entry = pin_literal(content, other, media_type)
            key = (other.path, media_type, entry.data)
            if key not in checked:
                checked[key] = pin_manifest(content, other, media_type)
            raw_manifests.append(checked[key])
    return Documents(suite, catalog, tuple(agents), tuple(providers), tuple(raw_manifests))

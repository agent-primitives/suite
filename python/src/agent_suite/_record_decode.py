"""Explicit schema-first private record decoding; no declaration/graph validation."""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, NoReturn, TypeVar, cast

from ._json import Number
from ._models import Descriptor, Diagnostic, Document, Platform, Source
from ._records import (
    Agent, AgentInvoke, BrokeredCredential, Catalog, CompositionRef,
    DelegatedAuthorization, Extension, FileRef, InferenceRequirements, Loaded,
    ManifestRef, ModelRequirement, RawFragment, RemoteHeader,
    RemoteNetworkRequirement, RemoteTimeouts, RemoteToolProvider, SecretKeyRef,
    Suite, Tool, ToolProvider, ToolProviderCompositionRef, ToolProviderRequirement,
)
from ._schema import Bundle

T = TypeVar("T")


class DocumentError(ValueError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("; ".join(f"{d.source.file}{d.source.pointer}: {d.message}" for d in self.diagnostics))


def fail(source: Source, code: str, message: str) -> NoReturn:
    raise DocumentError((Diagnostic(source, code, message),))


class _Node:
    """Small located field accessor; record construction remains explicit below."""

    def __init__(self, document: Document, value: Any, path: tuple[str | int, ...] = ()) -> None:
        self.document, self.value, self.path = document, value, path
        self.source = RawFragment(document, path).source

    def closed(self, fields: str) -> None:
        if not isinstance(self.value, dict):
            fail(self.source, "document.type", "expected object")
        unknown = self.value.keys() - set(fields.split())
        if unknown:
            fail(self.field(sorted(unknown)[0]).source, "document.unknown", "unknown field")

    def field(self, name: str, default: Any = None) -> _Node:
        return _Node(self.document, self.value.get(name, default), self.path + (name,))

    def string(self) -> str:
        if not isinstance(self.value, str):
            fail(self.source, "document.type", "expected string")
        return self.value

    def text(self, name: str) -> str:
        return self.field(name, "").string()

    def boolean(self) -> bool:
        if not isinstance(self.value, bool):
            fail(self.source, "document.type", "expected boolean")
        return self.value

    def integer(self, name: str) -> int:
        node = self.field(name)
        value = node.value
        if not isinstance(value, Number) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", value.lexeme):
            fail(node.source, "document.integer", "expected integer lexeme")
        integer = int(value.lexeme)
        if not -(1 << 63) <= integer < (1 << 63):
            fail(node.source, "document.integer", "integer outside int64")
        return integer

    def array(self, name: str, convert: Callable[[_Node], T], *, nullable: bool = False) -> tuple[T, ...]:
        node = self.field(name, [])
        if node.value is None and nullable:
            return ()
        if not isinstance(node.value, list):
            fail(node.source, "document.type", "expected array")
        return tuple(convert(_Node(self.document, item, node.path + (i,)))
                     for i, item in enumerate(node.value))

    def optional(self, name: str, convert: Callable[[_Node], T]) -> T | None:
        return convert(self.field(name)) if name in self.value else None

    def primitive(self, name: str, kind: type[Descriptor] | type[Platform]) -> Any:
        node = self.field(name)
        if kind is Descriptor:
            node.closed("mediaType digest size annotations")
            node.integer("size")
        try:
            return kind.from_value(node.value)
        except ValueError as error:
            fail(node.source, "document.type", str(error))


def _manifest(n: _Node) -> ManifestRef:
    n.closed("id version path descriptor")
    return ManifestRef(n.text("id"), n.text("version"), n.text("path"),
                       n.primitive("descriptor", Descriptor), source=n.source)


def _file(n: _Node) -> FileRef:
    n.closed("path descriptor")
    return FileRef(n.text("path"), n.primitive("descriptor", Descriptor), source=n.source)


def _composition(n: _Node) -> CompositionRef:
    n.closed("agent runtimeProfile platform path descriptor")
    return CompositionRef(n.text("agent"), n.text("runtimeProfile"), n.primitive("platform", Platform),
                          n.text("path"), n.primitive("descriptor", Descriptor), source=n.source)


def _provider_composition(n: _Node) -> ToolProviderCompositionRef:
    n.closed("id version platform path descriptor")
    return ToolProviderCompositionRef(n.text("id"), n.text("version"), n.primitive("platform", Platform),
                                      n.text("path"), n.primitive("descriptor", Descriptor), source=n.source)


def _extension(n: _Node) -> Extension:
    # Agent's schema leaves items open; Go still decodes closed Extension values.
    # Missing scalar fields default to zero, but explicit nulls are invalid.
    n.closed("name critical digest")
    return Extension(n.field("name", "").string(), n.field("critical", False).boolean(),
                     n.field("digest", "").string(), source=n.source)


def _suite(n: _Node) -> Suite:
    n.closed("schemaVersion mediaType name agents toolProviderCatalog toolProviderCompositions compositions "
             "buildProfiles runtimeProfiles capabilities extensions")
    return Suite(n.text("schemaVersion"), n.text("mediaType"), n.text("name"),
                 n.array("agents", _manifest), _manifest(n.field("toolProviderCatalog")),
                 n.array("toolProviderCompositions", _provider_composition),
                 n.array("compositions", _composition), n.array("buildProfiles", _manifest),
                 n.array("runtimeProfiles", _manifest), n.array("capabilities", _Node.string),
                 n.array("extensions", _extension), source=n.source)


def _inference(n: _Node) -> InferenceRequirements:
    n.closed("api contextTokens outputTokens streaming toolCalling")
    return InferenceRequirements(n.text("api"), n.integer("contextTokens"), n.integer("outputTokens"),
                                 n.field("streaming").boolean(), n.field("toolCalling").boolean(), source=n.source)


def _model(n: _Node) -> ModelRequirement:
    n.closed("protocol model capabilities endpointEnv secretRefs")
    return ModelRequirement(n.text("protocol"), n.text("model"), n.optional("capabilities", _inference),
                            n.text("endpointEnv"), n.array("secretRefs", _Node.string), source=n.source)


def _requirement(n: _Node) -> ToolProviderRequirement:
    n.closed("id version executionMode")
    return ToolProviderRequirement(n.text("id"), n.text("version"), n.text("executionMode"), source=n.source)


def _invoke(n: _Node) -> AgentInvoke:
    n.closed("agent maxConcurrent maxDepth")
    return AgentInvoke(n.text("agent"), n.integer("maxConcurrent"), n.integer("maxDepth"), source=n.source)


def _agent(n: _Node) -> Agent:
    n.closed("schemaVersion mediaType id description instructions model toolProviders invokes evals policy extensions")
    return Agent(n.text("schemaVersion"), n.text("mediaType"), n.text("id"), n.text("description"),
                 _file(n.field("instructions")), _model(n.field("model")),
                 n.array("toolProviders", _requirement), n.array("invokes", _invoke),
                 n.array("evals", _file), n.optional("policy", _file), n.array("extensions", _extension),
                 source=n.source)


def _catalog(n: _Node) -> Catalog:
    n.closed("schemaVersion mediaType toolProviders")
    for name, expected in (("schemaVersion", "1.0.0-draft"),
                           ("mediaType", "application/vnd.agentsuite.tool.provider.catalog.v1+json")):
        if n.text(name) != expected:
            fail(n.field(name).source, "document.envelope", "unsupported catalog envelope")
    return Catalog(n.text("schemaVersion"), n.text("mediaType"),
                   n.array("toolProviders", _manifest, nullable=True), source=n.source)


def _credential(n: _Node) -> BrokeredCredential:
    n.closed("resolution bindingRef")
    return BrokeredCredential(n.text("resolution"), n.text("bindingRef"), source=n.source)


def _delegated(n: _Node) -> DelegatedAuthorization:
    n.closed("service scope credential")
    return DelegatedAuthorization(n.text("service"), n.text("scope"),
                                  _credential(n.field("credential")), source=n.source)


def _tool(n: _Node) -> Tool:
    n.closed("name description inputSchema outputSchema effects effect approval delegatedAuthorization")
    return Tool(n.text("name"), n.text("description"), _file(n.field("inputSchema")),
                n.optional("outputSchema", _file), n.array("effects", _Node.string),
                n.text("effect"), n.text("approval"), n.optional("delegatedAuthorization", _delegated),
                source=n.source)


def _secret(n: _Node) -> SecretKeyRef:
    n.closed("name key")
    return SecretKeyRef(n.text("name"), n.text("key"), source=n.source)


def _header(n: _Node) -> RemoteHeader:
    n.closed("name secretRef")
    return RemoteHeader(n.text("name"), _secret(n.field("secretRef")), source=n.source)


def _network(n: _Node) -> RemoteNetworkRequirement:
    n.closed("destinationRef")
    return RemoteNetworkRequirement(n.text("destinationRef"), source=n.source)


def _timeouts(n: _Node) -> RemoteTimeouts:
    n.closed("connectMilliseconds requestMilliseconds")
    return RemoteTimeouts(n.integer("connectMilliseconds"), n.integer("requestMilliseconds"), source=n.source)


def _remote(n: _Node) -> RemoteToolProvider:
    n.closed("transport endpointRef headers network timeouts cancellation connection")
    return RemoteToolProvider(n.text("transport"), n.text("endpointRef"), n.array("headers", _header),
                              n.array("network", _network), _timeouts(n.field("timeouts")),
                              n.text("cancellation"), n.text("connection"), source=n.source)


def _provider(n: _Node) -> ToolProvider:
    n.closed("schemaVersion mediaType id version retained protocol revision tools variants remote extensions")
    return ToolProvider(n.text("schemaVersion"), n.text("mediaType"), n.text("id"), n.text("version"),
                        n.optional("retained", _Node.boolean), n.text("protocol"), n.text("revision"),
                        n.array("tools", _tool), n.array("variants", lambda v: RawFragment(v.document, v.path)),
                        n.optional("remote", _remote), n.array("extensions", _extension), source=n.source)


def read_document(document: Document, kind: type[T], bundle: Bundle) -> Loaded[T]:
    try:
        value = document.value
    except ValueError as error:
        fail(document.source, "document.json", str(error))
    if kind is Suite:
        schema = "suite.schema.json"
    elif kind is Agent:
        schema = "agent.schema.json"
    elif kind is ToolProvider:
        schema = "tool-provider.schema.json"
    elif kind is Catalog:
        schema = None
    else:
        raise TypeError("unsupported private document kind")
    if schema is not None:
        diagnostics = bundle.validate(schema, value, document.source)
        if diagnostics:
            raise DocumentError(tuple(diagnostics))
    node = _Node(document, value)
    if kind is Suite:
        record: object = _suite(node)
    elif kind is Agent:
        record = _agent(node)
    elif kind is ToolProvider:
        record = _provider(node)
    else:
        record = _catalog(node)
    return Loaded(document, cast(T, record))

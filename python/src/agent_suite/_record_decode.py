"""Explicit schema-first private record decoding; no declaration/graph validation."""
from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any, NoReturn, TypeVar, cast

from ._json import Number
from ._models import Descriptor, Diagnostic, Document, Platform, Source
from ._records import (
    Agent, AgentInvoke, BrokeredCredential, BuildProfile, Catalog, Composition, CompositionRef,
    DelegatedAuthorization, EnvironmentName, EvaluationAssertion, EvaluationCase, EvaluationIndex,
    EvaluationLimits, ExecutionContract, ExecutionInput, Extension, FileRef,
    Implementation, InferenceRequirements, InventoryEntry, Loaded, ManifestRef, ModelRequirement,
    NetworkAccess, PlatformImage, PolicyEndpoint, PolicyNetwork, PolicyV1, PolicyV2, RawFragment,
    RemoteHeader, RemoteNetworkRequirement, RemoteTimeouts,
    RemoteToolProvider, ResolvedToolProvider, RuntimeProfile, RuntimeRequirement, SecretKeyRef, Suite,
    Tool, ToolProvider, ToolProviderComposition, ToolProviderCompositionRef, ToolProviderDependency,
    ToolProviderRequirement, ToolProviderVariant,
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


def _environment(n: _Node) -> EnvironmentName:
    n.closed("name required secret delivery")
    return EnvironmentName(
        name=n.text("name"),
        required=n.field("required", False).boolean(),
        secret=n.field("secret", False).boolean(),
        delivery=n.text("delivery"),
        source=n.source,
    )


def _network_access(n: _Node) -> NetworkAccess:
    n.closed("scheme host port")
    return NetworkAccess(
        scheme=n.text("scheme"),
        host=n.text("host"),
        port=n.integer("port"),
        source=n.source,
    )


def _runtime_requirement(n: _Node) -> RuntimeRequirement:
    n.closed("abi abiVersion cpuBaseline requiredBasePaths")
    return RuntimeRequirement(
        abi=n.text("abi"),
        abi_version=n.text("abiVersion"),
        cpu_baseline=n.text("cpuBaseline"),
        required_base_paths=n.array("requiredBasePaths", _Node.string),
        source=n.source,
    )


def _inventory(n: _Node) -> InventoryEntry:
    n.closed("path type mode uid gid size digest linkTarget component")
    mode = n.integer("mode")
    if not 0 <= mode < (1 << 32):
        fail(n.field("mode").source, "document.integer", "integer outside uint32")
    return InventoryEntry(
        path=n.text("path"),
        type=n.text("type"),
        mode=mode,
        uid=n.integer("uid"),
        gid=n.integer("gid"),
        # The full schema requires size for files; other kinds default to zero.
        size=n.integer("size") if "size" in n.value else 0,
        digest=n.text("digest"),
        link_target=n.text("linkTarget"),
        component=n.text("component"),
        source=n.source,
    )


def _dependency(n: _Node) -> ToolProviderDependency:
    n.closed("id version variantDigest")
    return ToolProviderDependency(
        id=n.text("id"),
        version=n.text("version"),
        variant_digest=n.text("variantDigest"),
        source=n.source,
    )


def _variant(n: _Node) -> ToolProviderVariant:
    n.closed("platform variantDigest installRoot relocatable payloadRoot entrypoint arguments searchPath "
             "environment writablePaths network runtime files dependencies sbom provenance")
    return ToolProviderVariant(
        platform=n.primitive("platform", Platform),
        variant_digest=n.text("variantDigest"),
        install_root=n.text("installRoot"),
        relocatable=n.field("relocatable", False).boolean(),
        payload_root=n.text("payloadRoot"),
        entrypoint=n.text("entrypoint"),
        arguments=n.array("arguments", _Node.string),
        search_path=n.array("searchPath", _Node.string),
        writable_paths=n.array("writablePaths", _Node.string),
        environment=n.array("environment", _environment),
        network=n.array("network", _network_access),
        runtime=_runtime_requirement(n.field("runtime")),
        files=n.array("files", _inventory),
        dependencies=n.array("dependencies", _dependency),
        sbom=n.primitive("sbom", Descriptor) if "sbom" in n.value else None,
        provenance=n.primitive("provenance", Descriptor) if "provenance" in n.value else None,
        # Defaults are views only: identity must retain the original authored tree.
        raw=RawFragment(n.document, n.path),
        source=n.source,
    )


def _provider(n: _Node) -> ToolProvider:
    n.closed("schemaVersion mediaType id version retained protocol revision tools variants remote extensions")
    return ToolProvider(n.text("schemaVersion"), n.text("mediaType"), n.text("id"), n.text("version"),
                        n.optional("retained", _Node.boolean), n.text("protocol"), n.text("revision"),
                        n.array("tools", _tool), n.array("variants", _variant),
                        n.optional("remote", _remote), n.array("extensions", _extension), source=n.source)


def _execution_input(n: _Node) -> ExecutionInput:
    n.closed("name environment secret")
    return ExecutionInput(n.text("name"), n.text("environment"), n.field("secret").boolean(),
                          source=n.source)


def _execution(n: _Node) -> ExecutionContract:
    n.closed("configuration kind protocol port healthPath inputs")
    return ExecutionContract(
        configuration=n.text("configuration"),
        kind=n.text("kind"),
        protocol=n.text("protocol"),
        port=n.integer("port"),
        health_path=n.text("healthPath"),
        inputs=n.array("inputs", _execution_input),
        source=n.source,
    )


def _platform_image(n: _Node) -> PlatformImage:
    n.closed("platform imageRef image")
    return PlatformImage(n.primitive("platform", Platform), n.text("imageRef"),
                         n.primitive("image", Descriptor), source=n.source)


def _build_profile(n: _Node) -> BuildProfile:
    n.closed("schemaVersion mediaType id runtimeBase harness sourceEpoch execution")
    return BuildProfile(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        id=n.text("id"),
        runtime_base=n.array("runtimeBase", _platform_image),
        harness=n.array("harness", _platform_image),
        source_epoch=n.integer("sourceEpoch"),
        execution=n.optional("execution", _execution),
        source=n.source,
    )


def _implementation(n: _Node) -> Implementation:
    n.closed("id version digest")
    return Implementation(n.text("id"), n.text("version"), n.text("digest"), source=n.source)


def _runtime_profile(n: _Node) -> RuntimeProfile:
    n.closed("schemaVersion mediaType id runtime harness renderer configurationABI imageRequired")
    return RuntimeProfile(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        id=n.text("id"),
        runtime=_implementation(n.field("runtime")),
        harness=_implementation(n.field("harness")),
        renderer=_implementation(n.field("renderer")),
        configuration_abi=n.text("configurationABI"),
        image_required=n.field("imageRequired").boolean(),
        source=n.source,
    )


def _resolved_provider(n: _Node) -> ResolvedToolProvider:
    n.closed("id version manifestDigest variantDigest executionMode")
    return ResolvedToolProvider(
        id=n.text("id"),
        version=n.text("version"),
        manifest_digest=n.text("manifestDigest"),
        variant_digest=n.text("variantDigest"),
        execution_mode=n.text("executionMode"),
        source=n.source,
    )


def _composition_document(n: _Node) -> Composition:
    n.closed("schemaVersion mediaType agent platform buildProfile toolProviders runtimeProfile")
    return Composition(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        agent=n.text("agent"),
        platform=n.primitive("platform", Platform),
        build_profile=n.text("buildProfile"),
        tool_providers=n.array("toolProviders", _resolved_provider),
        runtime_profile=n.text("runtimeProfile"),
        source=n.source,
    )


def _provider_composition_document(n: _Node) -> ToolProviderComposition:
    n.closed("schemaVersion mediaType id version manifestDigest platform variantDigest buildProfile")
    return ToolProviderComposition(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        id=n.text("id"),
        version=n.text("version"),
        manifest_digest=n.text("manifestDigest"),
        platform=n.primitive("platform", Platform),
        variant_digest=n.text("variantDigest"),
        build_profile=n.text("buildProfile"),
        source=n.source,
    )


def _evaluation_limits(n: _Node) -> EvaluationLimits:
    n.closed("maxCases maxCaseBytes")
    return EvaluationLimits(n.integer("maxCases"), n.integer("maxCaseBytes"), source=n.source)


def _evaluation_index(n: _Node) -> EvaluationIndex:
    n.closed("schemaVersion mediaType agent cases limits")
    return EvaluationIndex(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        agent=n.text("agent"),
        cases=n.array("cases", _file),
        limits=_evaluation_limits(n.field("limits")),
        source=n.source,
    )


def _optional_integer(n: _Node, name: str) -> int | None:
    return n.integer(name) if name in n.value else None


def _evaluation_assertion(n: _Node) -> EvaluationAssertion:
    n.closed("id type critical value pattern tool rubric minScore judgeModel judgeVersion")
    # The owning schema selects operands, including explicit noncritical unknown kinds.
    return EvaluationAssertion(
        id=n.text("id"),
        kind=n.text("type"),
        critical=n.optional("critical", _Node.boolean),
        value=n.optional("value", _Node.string),
        pattern=n.optional("pattern", _Node.string),
        tool=n.optional("tool", _Node.string),
        rubric=n.optional("rubric", _Node.string),
        min_score=_optional_integer(n, "minScore"),
        judge_model=n.optional("judgeModel", _Node.string),
        judge_version=n.optional("judgeVersion", _Node.string),
        source=n.source,
    )


def _evaluation_case(n: _Node) -> EvaluationCase:
    n.closed("schemaVersion mediaType id input runs minPasses assertions")
    return EvaluationCase(
        schema_version=n.text("schemaVersion"),
        media_type=n.text("mediaType"),
        id=n.text("id"),
        input=n.text("input"),
        runs=_optional_integer(n, "runs"),
        min_passes=_optional_integer(n, "minPasses"),
        assertions=n.array("assertions", _evaluation_assertion),
        source=n.source,
    )


def _policy_v1(n: _Node) -> PolicyV1:
    # No standalone v1 schema: retain its closed, filesystem-only wire contract.
    n.closed("version denyWritePaths requiredCapabilities")
    version = n.field("version").string()
    if version != "agentsuite.policy/v1":
        fail(n.field("version").source, "document.envelope", "unsupported policy version")
    for name in ("denyWritePaths", "requiredCapabilities"):
        if not isinstance(n.field(name).value, list):
            fail(n.field(name).source, "document.type", "expected array")
    return PolicyV1(
        version=version,
        deny_write_paths=n.array("denyWritePaths", _Node.string),
        required_capabilities=n.array("requiredCapabilities", _Node.string),
        source=n.source,
    )


def _policy_endpoint(n: _Node) -> PolicyEndpoint:
    n.closed("address protocol port")
    port = n.field("port")
    value = port.value
    if not isinstance(value, Number) or not 1 <= value <= 65535:
        fail(port.source, "document.integer", "expected integral port in 1..65535")
    candidate = int(value)
    # Compare the original decimal exactly, not its possibly rounded binary64.
    # Only the bounded candidate becomes an int: long compensated lexemes need
    # neither huge integer conversion nor a process-wide digit-limit change.
    if Decimal(value.lexeme) != Decimal(candidate):
        fail(port.source, "document.integer", "expected integral port in 1..65535")
    return PolicyEndpoint(n.text("address"), n.text("protocol"), candidate, source=n.source)


def _policy_network(n: _Node) -> PolicyNetwork:
    n.closed("egressAllow")
    return PolicyNetwork(n.array("egressAllow", _policy_endpoint), source=n.source)


def _policy_v2(n: _Node) -> PolicyV2:
    n.closed("version network requiredCapabilities")
    return PolicyV2(
        version=n.text("version"),
        network=_policy_network(n.field("network")),
        required_capabilities=n.array("requiredCapabilities", _Node.string),
        source=n.source,
    )


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
    elif kind is BuildProfile:
        schema = "build-profile.schema.json"
    elif kind is RuntimeProfile:
        schema = "runtime-profile.schema.json"
    elif kind is Composition:
        schema = "composition.schema.json"
    elif kind is ToolProviderComposition:
        schema = "tool-provider-composition.schema.json"
    elif kind is EvaluationIndex:
        schema = "eval-index.schema.json"
    elif kind is EvaluationCase:
        schema = "eval-case.schema.json"
    elif kind is PolicyV2:
        schema = "policy-v2.schema.json"
    elif kind is Catalog or kind is PolicyV1:
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
    elif kind is BuildProfile:
        record = _build_profile(node)
    elif kind is RuntimeProfile:
        record = _runtime_profile(node)
    elif kind is Composition:
        record = _composition_document(node)
    elif kind is ToolProviderComposition:
        record = _provider_composition_document(node)
    elif kind is EvaluationIndex:
        record = _evaluation_index(node)
    elif kind is EvaluationCase:
        record = _evaluation_case(node)
    elif kind is PolicyV1:
        record = _policy_v1(node)
    elif kind is PolicyV2:
        record = _policy_v2(node)
    else:
        record = _catalog(node)
    return Loaded(document, cast(T, record))

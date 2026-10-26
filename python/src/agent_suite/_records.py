"""Private immutable authored records, not verified package or graph state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from ._models import Descriptor, Document, Platform, Source

T = TypeVar("T")


@dataclass(frozen=True, kw_only=True)
class Located:
    source: Source


@dataclass(frozen=True)
class Loaded(Generic[T]):
    document: Document
    record: T


@dataclass(frozen=True)
class RawFragment:
    document: Document
    path: tuple[str | int, ...]

    @property
    def source(self) -> Source:
        pointer = self.document.source.pointer + "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1") for part in self.path
        )
        return Source(self.document.source.file, pointer)

    @property
    def value(self) -> Any:
        value: Any = self.document.value
        for part in self.path:
            value = value[part]
        return value


@dataclass(frozen=True)
class ManifestRef(Located):
    id: str
    version: str
    path: str
    descriptor: Descriptor


@dataclass(frozen=True)
class FileRef(Located):
    path: str
    descriptor: Descriptor


@dataclass(frozen=True)
class CompositionRef(Located):
    agent: str
    runtime_profile: str
    platform: Platform
    path: str
    descriptor: Descriptor


@dataclass(frozen=True)
class ToolProviderCompositionRef(Located):
    id: str
    version: str
    platform: Platform
    path: str
    descriptor: Descriptor


@dataclass(frozen=True)
class Extension(Located):
    name: str
    critical: bool = False
    digest: str = ""


@dataclass(frozen=True)
class Suite(Located):
    schema_version: str
    media_type: str
    name: str
    agents: tuple[ManifestRef, ...]
    tool_provider_catalog: ManifestRef
    tool_provider_compositions: tuple[ToolProviderCompositionRef, ...]
    compositions: tuple[CompositionRef, ...]
    build_profiles: tuple[ManifestRef, ...]
    runtime_profiles: tuple[ManifestRef, ...]
    capabilities: tuple[str, ...]
    extensions: tuple[Extension, ...]


@dataclass(frozen=True)
class ExecutionInput(Located):
    name: str
    environment: str
    secret: bool


@dataclass(frozen=True)
class ExecutionContract(Located):
    configuration: str
    kind: str
    protocol: str
    port: int
    health_path: str
    inputs: tuple[ExecutionInput, ...]


@dataclass(frozen=True)
class PlatformImage(Located):
    platform: Platform
    image_ref: str
    image: Descriptor


@dataclass(frozen=True)
class BuildProfile(Located):
    schema_version: str
    media_type: str
    id: str
    runtime_base: tuple[PlatformImage, ...]
    harness: tuple[PlatformImage, ...]
    source_epoch: int
    execution: ExecutionContract | None


@dataclass(frozen=True)
class Implementation(Located):
    id: str
    version: str
    digest: str


@dataclass(frozen=True)
class RuntimeProfile(Located):
    schema_version: str
    media_type: str
    id: str
    runtime: Implementation
    harness: Implementation
    renderer: Implementation
    configuration_abi: str
    image_required: bool


@dataclass(frozen=True)
class ResolvedToolProvider(Located):
    id: str
    version: str
    manifest_digest: str
    variant_digest: str
    execution_mode: str


@dataclass(frozen=True)
class Composition(Located):
    schema_version: str
    media_type: str
    agent: str
    platform: Platform
    build_profile: str
    tool_providers: tuple[ResolvedToolProvider, ...]
    runtime_profile: str


@dataclass(frozen=True)
class ToolProviderComposition(Located):
    schema_version: str
    media_type: str
    id: str
    version: str
    manifest_digest: str
    platform: Platform
    variant_digest: str
    build_profile: str


@dataclass(frozen=True)
class InferenceRequirements(Located):
    api: str
    context_tokens: int
    output_tokens: int
    streaming: bool
    tool_calling: bool


@dataclass(frozen=True)
class ModelRequirement(Located):
    protocol: str
    model: str
    capabilities: InferenceRequirements | None
    endpoint_env: str
    secret_refs: tuple[str, ...]


@dataclass(frozen=True)
class ToolProviderRequirement(Located):
    id: str
    version: str
    execution_mode: str


@dataclass(frozen=True)
class AgentInvoke(Located):
    agent: str
    max_concurrent: int
    max_depth: int


@dataclass(frozen=True)
class Agent(Located):
    schema_version: str
    media_type: str
    id: str
    description: str
    instructions: FileRef
    model: ModelRequirement
    tool_providers: tuple[ToolProviderRequirement, ...]
    invokes: tuple[AgentInvoke, ...]
    evals: tuple[FileRef, ...]
    policy: FileRef | None
    extensions: tuple[Extension, ...]


@dataclass(frozen=True)
class Catalog(Located):
    schema_version: str
    media_type: str
    tool_providers: tuple[ManifestRef, ...]


@dataclass(frozen=True)
class BrokeredCredential(Located):
    resolution: str
    binding_ref: str


@dataclass(frozen=True)
class DelegatedAuthorization(Located):
    service: str
    scope: str
    credential: BrokeredCredential


@dataclass(frozen=True)
class Tool(Located):
    name: str
    description: str
    input_schema: FileRef
    output_schema: FileRef | None
    effects: tuple[str, ...]
    effect: str
    approval: str
    delegated_authorization: DelegatedAuthorization | None


@dataclass(frozen=True)
class SecretKeyRef(Located):
    name: str
    key: str


@dataclass(frozen=True)
class RemoteHeader(Located):
    name: str
    secret_ref: SecretKeyRef


@dataclass(frozen=True)
class RemoteNetworkRequirement(Located):
    destination_ref: str


@dataclass(frozen=True)
class RemoteTimeouts(Located):
    connect_milliseconds: int
    request_milliseconds: int


@dataclass(frozen=True)
class RemoteToolProvider(Located):
    transport: str
    endpoint_ref: str
    headers: tuple[RemoteHeader, ...]
    network: tuple[RemoteNetworkRequirement, ...]
    timeouts: RemoteTimeouts
    cancellation: str
    connection: str


@dataclass(frozen=True)
class EnvironmentName(Located):
    name: str
    required: bool
    secret: bool
    delivery: str


@dataclass(frozen=True)
class NetworkAccess(Located):
    scheme: str
    host: str
    port: int


@dataclass(frozen=True)
class RuntimeRequirement(Located):
    abi: str
    abi_version: str
    cpu_baseline: str
    required_base_paths: tuple[str, ...]


@dataclass(frozen=True)
class InventoryEntry(Located):
    path: str
    type: str
    mode: int
    uid: int
    gid: int
    size: int
    digest: str
    link_target: str
    component: str


@dataclass(frozen=True)
class ToolProviderDependency(Located):
    id: str
    version: str
    variant_digest: str


@dataclass(frozen=True)
class ToolProviderVariant(Located):
    platform: Platform
    variant_digest: str
    install_root: str
    relocatable: bool
    payload_root: str
    entrypoint: str
    arguments: tuple[str, ...]
    search_path: tuple[str, ...]
    writable_paths: tuple[str, ...]
    environment: tuple[EnvironmentName, ...]
    network: tuple[NetworkAccess, ...]
    runtime: RuntimeRequirement
    files: tuple[InventoryEntry, ...]
    dependencies: tuple[ToolProviderDependency, ...]
    sbom: Descriptor | None
    provenance: Descriptor | None
    raw: RawFragment


@dataclass(frozen=True)
class ToolProvider(Located):
    schema_version: str
    media_type: str
    id: str
    version: str
    retained: bool | None
    protocol: str
    revision: str
    tools: tuple[Tool, ...]
    variants: tuple[ToolProviderVariant, ...]
    remote: RemoteToolProvider | None
    extensions: tuple[Extension, ...]


@dataclass(frozen=True)
class EvaluationLimits(Located):
    max_cases: int
    max_case_bytes: int


@dataclass(frozen=True)
class EvaluationIndex(Located):
    schema_version: str
    media_type: str
    agent: str
    cases: tuple[FileRef, ...]
    limits: EvaluationLimits


@dataclass(frozen=True)
class EvaluationAssertion(Located):
    id: str
    kind: str
    critical: bool | None
    value: str | None
    pattern: str | None
    tool: str | None
    rubric: str | None
    min_score: int | None
    judge_model: str | None
    judge_version: str | None


@dataclass(frozen=True)
class EvaluationCase(Located):
    schema_version: str
    media_type: str
    id: str
    input: str
    runs: int | None
    min_passes: int | None
    assertions: tuple[EvaluationAssertion, ...]


@dataclass(frozen=True)
class PolicyV1(Located):
    version: str
    deny_write_paths: tuple[str, ...]
    required_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class PolicyEndpoint(Located):
    address: str
    protocol: str
    port: int


@dataclass(frozen=True)
class PolicyNetwork(Located):
    egress_allow: tuple[PolicyEndpoint, ...]


@dataclass(frozen=True)
class PolicyV2(Located):
    version: str
    network: PolicyNetwork
    required_capabilities: tuple[str, ...]

"""Private composition graph prerequisites; policy/evaluation semantics are pending."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TypeVar

from ._bundles import add_variant_destinations, bundle_closure, exact_variant, validate_bundles
from ._content import Content
from ._documents import Documents, _at, _require, read_documents
from ._json import digest_bytes
from ._models import Document, Platform, Source
from ._profiles import validate_build, validate_runtime
from ._record_decode import read_document
from ._records import (
    BuildProfile, Composition, CompositionRef, InventoryEntry, Loaded, ManifestRef,
    RuntimeProfile, ToolProvider, ToolProviderComposition, ToolProviderCompositionRef,
)
from ._schema import Bundle

T = TypeVar('T')
Reference = ManifestRef | CompositionRef | ToolProviderCompositionRef


@dataclass(frozen=True)
class GraphParts:
    documents: Documents
    build_profiles: tuple[Loaded[BuildProfile], ...]
    runtime_profiles: tuple[Loaded[RuntimeProfile], ...]
    compositions: tuple[Loaded[Composition], ...]
    tool_provider_compositions: tuple[Loaded[ToolProviderComposition], ...]


def _typed(refs: Iterable[Reference], kind: type[T], raw: Mapping[str, Document], bundle: Bundle) -> tuple[Loaded[T], ...]:
    # read_documents has already checked EVERY reference, even for repeated paths.
    return tuple(read_document(raw[ref.path], kind, bundle) for ref in refs)


def _supports(profile: BuildProfile, platform: Platform, *, harness: bool) -> bool:
    return any(i.platform == platform for i in profile.runtime_base) and (
        not harness or any(i.platform == platform for i in profile.harness))


def _install(key: str, platform: Platform, digest: str, source: Source,
             providers: Mapping[str, ToolProvider], destinations: dict[str, InventoryEntry]) -> None:
    _require(key in providers, source, 'graph.provider', 'selected provider is missing')
    variant = exact_variant(providers[key].variants, platform, source)
    _require(variant.variant_digest == digest, _at(source, 'variantDigest'), 'graph.variant', 'selected variant digest is stale')
    for selected in bundle_closure(key, variant, providers):
        add_variant_destinations(destinations, selected.variant)


def read_graph(content: Content, bundle: Bundle) -> GraphParts:
    """No public success or verified root: stored policies/evaluations are NOT validated."""
    documents = read_documents(content, bundle)
    suite = documents.suite.record
    raw = {document.source.file: document for document in documents.raw_manifests}
    builds = _typed(suite.build_profiles, BuildProfile, raw, bundle)
    runtimes = _typed(suite.runtime_profiles, RuntimeProfile, raw, bundle)
    compositions = _typed(suite.compositions, Composition, raw, bundle)
    standalone = _typed(suite.tool_provider_compositions, ToolProviderComposition, raw, bundle)
    providers = {p.record.id+'@'+p.record.version:p.record for p in documents.providers}
    digests = {p.record.id+'@'+p.record.version:digest_bytes(p.document.data) for p in documents.providers}
    agents = {a.record.id:a.record for a in documents.agents}
    validate_bundles(content, providers)
    build_map = {}
    for ref, loaded in zip(suite.build_profiles, builds):
        profile = loaded.record
        _require(ref.id == profile.id, ref.source, 'graph.identity', 'build profile reference identity mismatch')
        _require(ref.id not in build_map, ref.source, 'graph.duplicate', 'duplicate build profile')
        validate_build(profile)
        build_map[ref.id] = profile
    runtime_map = {}
    for ref, loaded_runtime in zip(suite.runtime_profiles, runtimes):
        validate_runtime(loaded_runtime.record)
        _require(ref.id == loaded_runtime.record.id, ref.source, 'graph.identity', 'runtime reference identity mismatch')
        _require(ref.id not in runtime_map, ref.source, 'graph.duplicate', 'duplicate runtime profile')
        runtime_map[ref.id] = loaded_runtime.record
    standalone_keys = set()
    referenced = {r.id+'@'+r.version for a in agents.values() for r in a.tool_providers}
    referenced.update(d.id+'@'+d.version for p in providers.values() for v in p.variants for d in v.dependencies)
    for provider_ref, loaded_provider in zip(suite.tool_provider_compositions, standalone):
        c = loaded_provider.record
        _require((provider_ref.id, provider_ref.version, provider_ref.platform) == (c.id, c.version, c.platform),
                 provider_ref.source, 'graph.identity', 'provider composition reference identity mismatch')
        provider_selection = (c.id, c.version, c.platform)
        _require(provider_selection not in standalone_keys, provider_ref.source,
                 'graph.duplicate', 'duplicate provider composition')
        standalone_keys.add(provider_selection)
        provider_key = c.id+'@'+c.version
        _require(provider_key in digests and digests[provider_key] == c.manifest_digest,
                 _at(c.source, 'manifestDigest'), 'graph.manifest', 'provider manifest is missing or stale')
        _require(c.build_profile in build_map and _supports(build_map[c.build_profile], c.platform, harness=False),
                 _at(c.source, 'buildProfile'), 'graph.platform', 'provider build profile does not support platform')
        _install(provider_key, c.platform, c.variant_digest, c.source, providers, {})
        referenced.add(provider_key)
    selections = set()
    profiled: dict[tuple[str, Platform], bool] = {}
    composed_agents = set()
    for composition_ref, loaded_composition in zip(suite.compositions, compositions):
        composition = loaded_composition.record
        _require((composition_ref.agent, composition_ref.platform, composition_ref.runtime_profile) == (
                 composition.agent, composition.platform, composition.runtime_profile), composition_ref.source,
                 'graph.identity', 'composition reference identity mismatch')
        pair = (composition.agent, composition.platform)
        selector = bool(composition.runtime_profile)
        _require(pair not in profiled or profiled[pair] == selector, composition_ref.source,
                 'graph.selection', 'legacy and runtime-profile selections cannot be mixed')
        profiled[pair] = selector
        selection = (*pair, composition.runtime_profile)
        _require(selection not in selections, composition_ref.source, 'graph.duplicate', 'duplicate composition')
        selections.add(selection)
        _require(composition.build_profile in build_map and _supports(build_map[composition.build_profile],
                 composition.platform, harness=True), _at(composition.source, 'buildProfile'),
                 'graph.platform', 'agent build profile does not support platform')
        profile = build_map[composition.build_profile]
        if composition.runtime_profile:
            _require(composition.runtime_profile in runtime_map, _at(composition.source, 'runtimeProfile'),
                     'graph.runtime', 'unknown runtime profile')
            runtime = runtime_map[composition.runtime_profile]
            _require(all(i.image.digest == runtime.harness.digest for i in profile.harness
                         if i.platform == composition.platform), _at(composition.source, 'runtimeProfile'),
                     'graph.runtime', 'runtime profile harness digest mismatch')
        _require(composition.agent in agents, _at(composition.source, 'agent'), 'graph.agent', 'unknown agent')
        composed_agents.add(composition.agent)
        requirements = {r.id+'@'+r.version:r for r in agents[composition.agent].tool_providers}
        _require(len(requirements) == len(composition.tool_providers), _at(composition.source, 'toolProviders'),
                 'graph.resolution', 'composition must resolve each requirement exactly once')
        previous: tuple[str, str] | None = None
        destinations: dict[str, InventoryEntry] = {}
        for resolved in composition.tool_providers:
            identity = (resolved.id, resolved.version)
            _require(previous is None or previous < identity, resolved.source,
                     'graph.resolution', 'resolved providers must be sorted and unique')
            previous = identity
            provider_key = resolved.id+'@'+resolved.version
            _require(provider_key in requirements and provider_key in providers, resolved.source,
                     'graph.provider', 'missing or undeclared provider resolution')
            _require(resolved.manifest_digest == digests[provider_key]
                     and resolved.execution_mode == requirements[provider_key].execution_mode,
                     resolved.source, 'graph.manifest', 'stale provider manifest or execution mode')
            _install(provider_key, composition.platform, resolved.variant_digest, resolved.source, providers, destinations)
    for agent in agents.values():
        _require(agent.id in composed_agents, agent.source, 'graph.composition', 'agent has no platform composition')
        for invoke in agent.invokes:
            _require(invoke.agent in agents, _at(invoke.source, 'agent'), 'graph.invoke', 'unknown invoked agent')
    for key, provider in providers.items():
        _require(key in referenced or provider.retained is True, _at(provider.source, 'retained'),
                 'graph.retention', 'unreferenced provider must explicitly be retained')
    capabilities = ('bundled-stdio-mcp',) if any(p.variants for p in providers.values()) else ()
    _require(suite.capabilities == capabilities, _at(suite.source, 'capabilities'),
             'graph.capabilities', 'capabilities must exactly match sorted derived capabilities')
    return GraphParts(documents, builds, runtimes, compositions, standalone)

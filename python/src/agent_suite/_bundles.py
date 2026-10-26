"""Private dependency/installation primitives; callers choose coinstalled sets."""
from __future__ import annotations

import posixpath
from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from ._content import Content
from ._documents import _at, _DIGEST, _IDENTIFIER, _require, _VERSION
from ._models import Platform, Source
from ._records import InventoryEntry, ToolProvider, ToolProviderDependency, ToolProviderVariant
from ._variants import validate_variant


@dataclass(frozen=True)
class SelectedBundle:
    provider_key: str
    variant: ToolProviderVariant


@dataclass
class _Visit:
    key: str
    variant: ToolProviderVariant
    remaining: Iterator[ToolProviderDependency]
    seen: set[str]


def exact_variant(variants: tuple[ToolProviderVariant, ...], platform: Platform, source: Source) -> ToolProviderVariant:
    matches = [variant for variant in variants if variant.platform == platform]
    _require(len(matches) == 1, source, 'bundle.selection', 'dependency must select exactly one matching platform')
    return matches[0]


def bundle_closure(root_key: str, root: ToolProviderVariant,
                   providers: Mapping[str, ToolProvider]) -> tuple[SelectedBundle, ...]:
    """Authored-order DFS without imposing Python's process recursion ceiling."""
    closure = [SelectedBundle(root_key, root)]
    active = {(root_key, root.variant_digest)}
    visited: set[tuple[str, str]] = set()
    stack = [_Visit(root_key, root, iter(root.dependencies), set())]
    while stack:
        frame = stack[-1]
        dependency = next(frame.remaining, None)
        if dependency is None:
            identity = (frame.key, frame.variant.variant_digest)
            active.remove(identity)
            visited.add(identity)
            stack.pop()
            continue
        key = dependency.id+'@'+dependency.version
        _require(key != frame.key and key not in frame.seen and _IDENTIFIER.fullmatch(dependency.id)
                 and _VERSION.fullmatch(dependency.version) and _DIGEST.fullmatch(dependency.variant_digest),
                 dependency.source, 'bundle.dependency', 'invalid or duplicate dependency')
        frame.seen.add(key)
        _require(key in providers, dependency.source, 'bundle.missing', 'dependency provider is missing')
        selected = exact_variant(providers[key].variants, frame.variant.platform, dependency.source)
        _require(selected.variant_digest == dependency.variant_digest, _at(dependency.source, 'variantDigest'),
                 'bundle.selection', 'dependency variant pin is stale')
        identity = (key, selected.variant_digest)
        _require(identity not in active, dependency.source, 'bundle.cycle', 'transitive dependency cycle')
        if identity not in visited:
            active.add(identity)
            closure.append(SelectedBundle(key, selected))
            stack.append(_Visit(key, selected, iter(selected.dependencies), set()))
    return tuple(closure)


def _same_entry(a: InventoryEntry, b: InventoryEntry) -> bool:
    return (a.type, a.mode, a.uid, a.gid, a.size, a.digest, a.link_target) == (
        b.type, b.mode, b.uid, b.gid, b.size, b.digest, b.link_target)


def add_variant_destinations(destinations: dict[str, InventoryEntry], variant: ToolProviderVariant) -> None:
    for entry in variant.files:
        destination = posixpath.normpath(posixpath.join(variant.install_root, entry.path))
        previous = destinations.get(destination)
        _require(previous is None or _same_entry(previous, entry), entry.source,
                 'bundle.collision', 'non-identical destination collision')
        destinations[destination] = entry


def validate_bundles(content: Content, providers: Mapping[str, ToolProvider]) -> None:
    """Validate every variant and edge, never aggregate unselected destinations."""
    for provider in providers.values():
        platforms = set()
        for variant in provider.variants:
            _require(variant.platform not in platforms, _at(variant.source, 'platform'),
                     'variant.duplicate', 'duplicate platform variant')
            platforms.add(variant.platform)
            validate_variant(variant, content)
    for key, provider in providers.items():
        for variant in provider.variants:
            bundle_closure(key, variant, providers)

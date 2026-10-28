"""Transactional, copy-on-write instruction editing; not general graph repair."""
from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ._casefold import fold_case
from ._content import Content, Entry, MAX_CONTENT_BYTES, MAX_ENTRIES, add_retained, retains
from ._evaluations import read_evaluations
from ._graph import read_graph
from ._json import Number, canonical_bytes, decode, digest_bytes
from ._literals import LiteralSnapshot
from ._models import Descriptor, Source
from ._policies import read_policies
from ._records import FileRef

if TYPE_CHECKING:
    from ._package import Package


def file_ref(entry: Entry) -> FileRef:
    """A private byte-source pin; it does not assert a format media type."""
    return FileRef(entry.path, Descriptor('', entry.digest, entry.size), source=Source(entry.path))


def _authored(value: Any) -> str:
    # The unpinned Suite may contain valid noncanonical number spellings.
    # Preserve these rather than round-tripping Number through Python float.
    if isinstance(value, Number):
        return value.lexeme
    if isinstance(value, dict):
        return '{' + ','.join(json.dumps(k, ensure_ascii=False)+':'+_authored(v)
                              for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ','.join(_authored(v) for v in value) + ']'
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def _replace_bytes(content: Content, path: str, data: bytes) -> None:
    content.entries[path] = replace(content.entries[path], data=data, size=len(data), digest=digest_bytes(data))


def set_instructions(package: Package, agent_id: str, content: str | bytes) -> None:
    from ._package import AgentView, LiteralView, LoadError, ToolView, _valid_regex
    diagnostics = package.validate()  # Never repair a stale original ancestor.
    if diagnostics:
        raise LoadError(diagnostics)
    if not isinstance(agent_id, str):
        raise TypeError('agent_id must be a string')
    if agent_id not in package.agents:
        raise KeyError(agent_id)
    if not isinstance(content, (str, bytes)):
        raise TypeError('instructions must be str or bytes')
    body = content.encode('utf-8', 'strict') if isinstance(content, str) else content
    previous = package.agents[agent_id]
    old = package._content
    replacement = Content()
    replacement.source_type = old.source_type
    for entry in old.entries.values():
        replacement.add(entry)
    # Always COW, including when a literal is also an executable/schema payload.
    # Probe collisions deterministically; never overwrite any existing entry.
    stem = 'instruction-' + agent_id + '-' + digest_bytes(body)[7:23]
    path = stem + '.md'
    suffix = 0
    # OCI files can imply a parent directory without an explicit entry.
    reserved = {fold_case(name.partition('/')[0]) for name in replacement.entries}
    while fold_case(path) in reserved:
        suffix += 1
        path = stem + '-' + str(suffix) + '.md'
    replacement.add(Entry(path, size=len(body), digest=digest_bytes(body), data=body))
    created = package._created_instruction_paths
    old_path = previous.instructions.reference.path
    # Fresh paths had no original incoming pins; this typed API only repoints
    # the chosen Agent, so no variant, other Agent or payload can gain a pin.
    # Original files never enter this set and are never garbage-collected.
    if old_path in created:
        del replacement.entries[old_path]
        del replacement._folded[fold_case(old_path)]
        created = created - {old_path}
    created = created | {path}
    agent = previous.document.value
    agent['instructions']['path'] = path
    agent['instructions']['descriptor'].update(size=len(body), digest=digest_bytes(body))
    agent_bytes = canonical_bytes(agent)
    _replace_bytes(replacement, previous.source.file, agent_bytes)
    suite = package.suite.document.value
    for ref in suite['agents']:
        if ref['id'] == agent_id:
            ref['descriptor'].update(size=len(agent_bytes), digest=digest_bytes(agent_bytes))
    suite_bytes = _authored(suite).encode('utf-8')
    decode(suite_bytes)  # Apply the same document limits before publishing.
    _replace_bytes(replacement, 'agentsuite.json', suite_bytes)
    if len(replacement.entries) > MAX_ENTRIES or sum(
            e.size for e in replacement.entries.values() if e.kind == 'file') > MAX_CONTENT_BYTES:
        raise ValueError('edited content exceeds package format bounds')
    retained = 0
    for entry in replacement.entries.values():
        if entry.kind == 'file' and retains(entry.path, entry.size):
            retained = add_retained(retained, entry.size)
    snapshot = LiteralSnapshot()
    try:
        # Keep original literals after source removal, not retired SDK edits.
        for captured in package._snapshot._ranges:
            if captured not in replacement.entries:
                continue
            ref = file_ref(old.entries[captured])
            data = old.entries[captured].data
            if data is not None:
                snapshot.reuse(ref, data)
            else:
                snapshot.add(ref, package._snapshot.get(ref).iter_bytes())
        snapshot.reuse(file_ref(replacement.entries[path]), body)
        snapshot.seal()
        parts = read_graph(replacement, package._bundle)
        read_policies(replacement, parts.documents, package._bundle)
        read_evaluations(replacement, parts.documents, package._bundle, _valid_regex)
        agents = {}
        for loaded in parts.documents.agents:
            original = package.agents[loaded.record.id]
            ref = loaded.record.instructions
            agents[loaded.record.id] = AgentView(loaded.document, loaded.record,
                LiteralView(ref, snapshot.get(ref)), original.policy, original.evaluations)
        providers = {}
        for key, original_provider in package.tool_providers.items():
            tools = tuple(ToolView(tool.declaration,
                LiteralView(tool.input_schema.reference, snapshot.get(tool.input_schema.reference)),
                LiteralView(tool.output_schema.reference, snapshot.get(tool.output_schema.reference))
                if tool.output_schema is not None else None) for tool in original_provider.tools)
            providers[key] = replace(original_provider, tools=tools)
        state = {'_content': replacement, '_parts': parts, '_snapshot': snapshot,
                 'suite': parts.documents.suite, 'agents': MappingProxyType(agents),
                 'tool_providers': MappingProxyType(providers), '_edited': True,
                 '_created_instruction_paths': created,
                 'root_digest': digest_bytes(canonical_bytes(parts.documents.suite.document.value)),
                 'artifact_digest': None}
    except BaseException:
        snapshot.close()
        raise
    old_snapshot = package._snapshot
    for attribute, value in state.items():
        object.__setattr__(package, attribute, value)
    # Old handles deliberately become stale, avoiding retained spool chains.
    # Reclamation cannot turn a committed edit into a reported transaction failure.
    with suppress(OSError):
        old_snapshot.close()
